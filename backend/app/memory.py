"""Project memory: vocabulary learning + execution-pattern analysis.

Vocabulary is learned ONLY from explicit human approvals (approve/remap)
or planner-curated POSTs — never from raw LLM output or unreviewed
matches. Each mapping carries approval counts and source-report evidence
so planners can audit what the project "learned".

Execution history in this prototype is synthetic and always labeled so;
it must never be presented as real project data.
"""
import json
from datetime import date, datetime, timezone

from .models import Activity, ExecutionHistory, ProjectVocabulary

SYNTHETIC_NOTE = "Synthetic demonstration data — not real project data."
PROJECT_CODE = "BRX-DEMO-01"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm_term(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _record(db, term: str, ctype: str, cvalue: str, discipline: str,
            report_code: str, actor: str, now: str) -> ProjectVocabulary | None:
    term = _norm_term(term)
    cvalue = (cvalue or "").strip()
    if not term or not cvalue:
        return None
    row = db.query(ProjectVocabulary).filter(
        ProjectVocabulary.project_code == PROJECT_CODE,
        ProjectVocabulary.term == term,
        ProjectVocabulary.canonical_type == ctype,
        ProjectVocabulary.canonical_value == cvalue).first()
    if not row:
        row = ProjectVocabulary(
            project_code=PROJECT_CODE, term=term, canonical_type=ctype,
            canonical_value=cvalue, discipline=discipline or "",
            approval_count=0, source_reports="[]",
            first_approved_by=actor or "planner")
        db.add(row)
        db.flush()
    try:
        sources = json.loads(row.source_reports)
    except Exception:
        sources = []
    if report_code and report_code not in sources:
        sources.append(report_code)
    row.source_reports = json.dumps(sources)
    row.approval_count = (row.approval_count or 0) + 1
    row.last_approved_by = actor or "planner"
    row.last_approved_at = now
    if not row.discipline and discipline:
        row.discipline = discipline
    return row


def learn_from_approval(db, ev, activity: Activity, report_code: str, actor: str, now: str) -> list[dict]:
    """Derive vocabulary mappings from one human-approved mapping.

    Learns object/phrase mappings when field wording differs from the
    canonical schedule term; action mappings only as reinforcement when
    they already agree (a forced remap to a different action must not
    teach a false equivalence).
    """
    learned = []
    raw_obj = _norm_term(ev.object)
    canon_obj = _norm_term(activity.object)
    if raw_obj and raw_obj != canon_obj:
        r = _record(db, raw_obj, "object", canon_obj, activity.discipline, report_code, actor, now)
        if r:
            learned.append({"term": r.term, "canonical_type": "object", "canonical_value": r.canonical_value})
    raw_act = _norm_term(ev.action)
    canon_act = _norm_term(activity.action)
    if raw_act and raw_act == canon_act:
        r = _record(db, raw_act, "action", canon_act, activity.discipline, report_code, actor, now)
        if r:
            learned.append({"term": r.term, "canonical_type": "action", "canonical_value": r.canonical_value})
    phrase = _norm_term(f"{ev.action} {ev.object}")
    if phrase and phrase not in (raw_obj, raw_act):
        r = _record(db, phrase, "phrase", activity.code, activity.discipline, report_code, actor, now)
        if r:
            learned.append({"term": r.term, "canonical_type": "phrase", "canonical_value": r.canonical_value})
    return learned


def add_curated_term(db, term: str, ctype: str, cvalue: str, discipline: str,
                     actor: str, now: str) -> ProjectVocabulary:
    """Planner-curated vocabulary entry (explicit human action)."""
    if ctype not in ("object", "action", "phrase"):
        raise ValueError("canonical_type must be object, action or phrase.")
    row = _record(db, term, ctype, cvalue, discipline, "", actor or "planner", now)
    if not row:
        raise ValueError("term and canonical_value must not be blank.")
    db.commit()
    return row


def list_vocabulary(db, discipline: str = "", term: str = "") -> list[dict]:
    q = db.query(ProjectVocabulary).filter(ProjectVocabulary.project_code == PROJECT_CODE)
    if discipline:
        q = q.filter(ProjectVocabulary.discipline == discipline)
    if term:
        q = q.filter(ProjectVocabulary.term.like(f"%{_norm_term(term)}%"))
    out = []
    for r in q.order_by(ProjectVocabulary.approval_count.desc(), ProjectVocabulary.term).all():
        try:
            sources = json.loads(r.source_reports)
        except Exception:
            sources = []
        out.append({"term": r.term, "canonical_type": r.canonical_type,
                    "canonical_value": r.canonical_value, "discipline": r.discipline,
                    "approval_count": r.approval_count, "source_reports": sources,
                    "first_approved_by": r.first_approved_by,
                    "last_approved_by": r.last_approved_by,
                    "last_approved_at": r.last_approved_at})
    return out


def lookup_term(db, term: str, ctype: str = "") -> list[dict]:
    """Find learned mappings for a field phrase (P11 Linker assist)."""
    q = db.query(ProjectVocabulary).filter(
        ProjectVocabulary.project_code == PROJECT_CODE,
        ProjectVocabulary.term == _norm_term(term))
    if ctype:
        q = q.filter(ProjectVocabulary.canonical_type == ctype)
    return [{"term": r.term, "canonical_type": r.canonical_type,
             "canonical_value": r.canonical_value, "approval_count": r.approval_count}
            for r in q.all()]


def load_active_vocabulary(db, project_code: str = PROJECT_CODE) -> list[dict]:
    """P14: vocabulary eligible to influence matching.

    Only rows that are active, human-approved (approval_count > 0) and
    belong to the requesting project. Learning paths (approve/remap/
    curated POST) are the sole writers, so presence here already implies
    explicit human origin; this loader additionally enforces the
    active/approved/project gates at read time.
    """
    rows = db.query(ProjectVocabulary).filter(
        ProjectVocabulary.project_code == project_code).all()
    out = []
    for r in rows:
        if (r.approval_count or 0) <= 0:
            continue
        if (r.is_active if r.is_active is not None else 1) != 1:
            continue
        try:
            sources = json.loads(r.source_reports)
        except Exception:
            sources = []
        out.append({"term": r.term, "canonical_type": r.canonical_type,
                    "canonical_value": r.canonical_value, "discipline": r.discipline or "",
                    "approval_count": r.approval_count, "source_reports": sources})
    return out


def execution_patterns(db) -> dict:
    """Aggregates over synthetic history + live schedule delays."""
    rows = db.query(ExecutionHistory).all()
    patterns = []
    for h in rows:
        over = round((h.avg_actual_days or 0) - (h.avg_planned_days or 0), 1)
        base = h.avg_planned_days or 0
        patterns.append({
            "pattern": h.pattern, "discipline": h.discipline,
            "executions": h.executions,
            "avg_planned_days": h.avg_planned_days,
            "avg_actual_days": h.avg_actual_days,
            "overrun_days": over,
            "overrun_pct": round(100 * over / base, 1) if base else 0.0,
            "common_issues": [s.strip() for s in (h.common_issues or "").split(";") if s.strip()],
            "synthetic": True,
        })
    by_disc: dict[str, dict] = {}
    for p in patterns:
        d = by_disc.setdefault(p["discipline"], {"executions": 0, "planned": 0.0, "actual": 0.0, "issues": []})
        d["executions"] += p["executions"]
        d["planned"] += p["avg_planned_days"] * p["executions"]
        d["actual"] += p["avg_actual_days"] * p["executions"]
        for i in p["common_issues"]:
            if i not in d["issues"]:
                d["issues"].append(i)
    disciplines = {}
    for disc, d in by_disc.items():
        n = d["executions"] or 1
        over = round(d["actual"] / n - d["planned"] / n, 1)
        disciplines[disc] = {
            "executions": d["executions"],
            "avg_planned_days": round(d["planned"] / n, 1),
            "avg_actual_days": round(d["actual"] / n, 1),
            "avg_overrun_days": over,
            "common_issues": d["issues"][:5],
            "synthetic": True,
        }
    today = date.today().isoformat()
    delayed = []
    for a in db.query(Activity).all():
        if (a.status or "") != "Complete" and (a.planned_finish or "") < today:
            try:
                overdue = (date.fromisoformat(today) - date.fromisoformat(a.planned_finish)).days
            except ValueError:
                overdue = 0
            delayed.append({"code": a.code, "name": a.name, "discipline": a.discipline,
                            "status": a.status, "planned_finish": a.planned_finish,
                            "days_overdue": overdue})
    delayed.sort(key=lambda x: x["days_overdue"], reverse=True)
    delay_by_disc: dict[str, int] = {}
    for x in delayed:
        delay_by_disc[x["discipline"]] = delay_by_disc.get(x["discipline"], 0) + 1
    return {
        "synthetic": True,
        "note": SYNTHETIC_NOTE,
        "patterns": patterns,
        "by_discipline": disciplines,
        "delayed_activities": delayed,
        "delays_by_discipline": delay_by_disc,
        "vocabulary_size": db.query(ProjectVocabulary).filter(
            ProjectVocabulary.project_code == PROJECT_CODE).count(),
    }
