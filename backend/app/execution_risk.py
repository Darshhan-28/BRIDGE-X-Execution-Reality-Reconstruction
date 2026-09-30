"""P16: Explainable Execution Risk Intelligence — advisory only, read-only.

Answers "which execution items need attention, and what evidence caused
the signal?" using ONLY evidence already present in BRIDGE-X: schedule
variance, activity/overdue states, P15 graph warnings, P7 verification
errors, unmatched reports, conflict rows, and synthetic history
aggregates. No new tables; everything is derived live.

This is NOT machine learning and NOT prediction: no probabilities, no
"X% chance of delay", no failed classifications. Output is a small
explainable priority (ATTENTION / WATCH / NORMAL) with exact evidence.

Advisory means advisory. This module NEVER modifies activities, dates,
relationships, reviews, gates, verification, or schedule updates —
it performs SELECTs only.
"""
import json
from datetime import date

from .execution_graph import analyze as graph_analyze
from .models import (
    Activity,
    Conflict,
    ExecutionHistory,
    FieldReport,
    MatchCandidate,
    Project,
    VerificationResult,
    WbsNode,
)

# Bounded evidence weights for attention priority. Explainable tally,
# not a model: score = sum of present-signal weights, capped at 10.
W = {
    "VERIFICATION_CONFLICT": 3,
    "CONTRADICTION": 3,
    "DEPENDENCY_RISK": 2,
    "SCHEDULE_VARIANCE": 2,
    "UNMATCHED_EXECUTION": 1,
    "REPEATED_EXECUTION_ISSUE": 1,
}
MAX_SCORE = 10
ATTENTION_AT = 4
WATCH_AT = 2
REPEATED_OVERRUN_DAYS = 1.0  # discipline overrun above this supports REPEATED signal


def _d(s: str):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def project_activities(db, project_code: str) -> list:
    """Activities scoped to one project via WBS. Raises LookupError if unknown."""
    proj = db.query(Project).filter(Project.code == project_code).first()
    if not proj:
        raise LookupError(f"Project {project_code} not found.")
    wbs = {w.code for w in db.query(WbsNode).filter(WbsNode.project_id == proj.id).all()}
    return db.query(Activity).filter(Activity.wbs_code.in_(wbs)).order_by(Activity.code).all()


def _latest_review(db, activity_code: str):
    return db.query(VerificationResult).filter(
        VerificationResult.target_activity == activity_code).order_by(
        VerificationResult.id.desc()).first()


def _variance_signal(a) -> dict | None:
    """SCHEDULE_VARIANCE from planned vs actual/overdue evidence only."""
    ps, pf = _d(a.planned_start or ""), _d(a.planned_finish or "")
    fas, faf = _d(a.actual_start or ""), _d(a.actual_finish or "")
    today = date.today()
    if pf and faf and faf > pf:
        late = (faf - pf).days
        return {"signal": "SCHEDULE_VARIANCE",
                "reason": f"Finished {faf} vs planned {pf}: +{late}d behind plan.",
                "variance_days": late,
                "evidence": {"planned_finish": a.planned_finish, "actual_finish": a.actual_finish}}
    if pf and (a.status or "") != "Complete" and pf < today:
        overdue = (today - pf).days
        return {"signal": "SCHEDULE_VARIANCE",
                "reason": f"{overdue}d past planned finish {pf}, still {a.status}.",
                "variance_days": overdue,
                "evidence": {"planned_finish": a.planned_finish, "status": a.status,
                             "actual_start": a.actual_start or ""}}
    if ps and fas and fas > ps and (a.status or "") == "Not Started":
        return None  # late start alone is not a variance signal without progress evidence
    return None


def _dependency_signals(db, code: str) -> list[dict]:
    """DEPENDENCY_RISK reused from P15 structural graph warnings (no duplication)."""
    out = []
    try:
        g = graph_analyze(db, code)
    except LookupError:
        return out
    for w in g.get("warnings", []):
        if w.get("kind") in ("blocked_chain", "successor_ahead"):
            out.append({"signal": "DEPENDENCY_RISK",
                        "reason": w.get("message", ""),
                        "variance_days": None,
                        "evidence": {"graph_kind": w.get("kind"), "rel_type": w.get("rel_type", "FS"),
                                     "activities": w.get("activities", []),
                                     "detail": w.get("evidence", {})}})
    return out


def _verification_signal(db, code: str) -> dict | None:
    """VERIFICATION_CONFLICT from the stored P7 result (referenced, not re-run)."""
    row = _latest_review(db, code)
    if not row or bool(row.valid):
        return None
    try:
        full = json.loads(row.result_json)
        errors = full.get("errors", [])
    except Exception:
        errors = []
    return {"signal": "VERIFICATION_CONFLICT",
            "reason": f"P7 verification failed for {code}: " + (
                "; ".join(errors[:2]) if errors else "see verification result."),
            "variance_days": None,
            "evidence": {"report": row.report_code, "proposal": row.proposal,
                         "decision": row.decision, "errors": errors[:3]}}


def _contradiction_signal(db, code: str) -> dict | None:
    """CONTRADICTION when a conflict row names this activity as evidence."""
    hits = []
    for r in db.query(Conflict).all():
        if r.evidence_a == code or r.evidence_b == code:
            hits.append(r)
    if not hits:
        return None
    r = hits[0]
    return {"signal": "CONTRADICTION",
            "reason": f"Conflicting execution evidence: {r.evidence_a} vs {r.evidence_b} ({r.conflict_type}).",
            "variance_days": None,
            "evidence": {"conflict_type": r.conflict_type, "evidence_a": r.evidence_a,
                         "evidence_b": r.evidence_b, "reason": r.reason[:200]}}


def _unmatched_links(db) -> dict:
    """Reports whose stored top-1 link fell below the gate (UNMATCHED decision)."""
    out = {}
    for v in db.query(VerificationResult).filter(VerificationResult.decision == "UNMATCHED").all():
        if v.target_activity:
            out.setdefault(v.target_activity, []).append(v.report_code)
    return out


def _repeated_signal(db, a, has_timing_issue: bool) -> dict | None:
    """REPEATED_EXECUTION_ISSUE only when synthetic aggregates support it."""
    if not has_timing_issue:
        return None
    pats = []
    for h in db.query(ExecutionHistory).filter(ExecutionHistory.discipline == a.discipline).all():
        over = round((h.avg_actual_days or 0) - (h.avg_planned_days or 0), 1)
        if over > REPEATED_OVERRUN_DAYS:
            pats.append({"pattern": h.pattern, "overrun_days": over,
                         "executions": h.executions, "synthetic": True})
    if not pats:
        return None
    pats.sort(key=lambda p: p["overrun_days"], reverse=True)
    top = pats[0]
    return {"signal": "REPEATED_EXECUTION_ISSUE",
            "reason": (f"{a.discipline} work historically overruns "
                       f"(e.g. '{top['pattern']}' +{top['overrun_days']}d over {top['executions']} runs, synthetic)."),
            "variance_days": None,
            "evidence": {"patterns": pats[:2], "synthetic": True}}


def _prioritize(signals: list[dict]) -> tuple[str, int, list[str]]:
    kinds = {s["signal"] for s in signals}
    score = min(MAX_SCORE, sum(W.get(k, 0) for k in kinds))
    notes = [f"evidence score {score} from: " + ", ".join(
        f"{k} (+{W.get(k, 0)})" for k in sorted(kinds))]
    if "VERIFICATION_CONFLICT" in kinds or "CONTRADICTION" in kinds:
        return "ATTENTION", score, notes + ["automatic ATTENTION: failed verification or contradiction present."]
    if score >= ATTENTION_AT:
        return "ATTENTION", score, notes + [f"score >= {ATTENTION_AT} attention threshold."]
    if score >= WATCH_AT:
        return "WATCH", score, notes + [f"score >= {WATCH_AT} watch threshold."]
    return "NORMAL", score, notes + ["no concerning evidence; routine monitoring only."]


def assess_activity(db, a, unmatched_map: dict | None = None) -> dict:
    """Full risk item for one activity. Read-only."""
    signals: list[dict] = []
    var = _variance_signal(a)
    if var:
        signals.append(var)
    signals.extend(_dependency_signals(db, a.code))
    ver = _verification_signal(db, a.code)
    if ver:
        signals.append(ver)
    con = _contradiction_signal(db, a.code)
    if con:
        signals.append(con)
    if unmatched_map and a.code in unmatched_map:
        reps = unmatched_map[a.code]
        signals.append({"signal": "UNMATCHED_EXECUTION",
                        "reason": f"Field evidence could not be confidently linked: {', '.join(reps)}.",
                        "variance_days": None,
                        "evidence": {"reports": reps}})
    rep = _repeated_signal(db, a, var is not None)
    if rep:
        signals.append(rep)
    priority, score, notes = _prioritize(signals)
    return {
        "subject_type": "activity",
        "subject_id": a.code,
        "activity_code": a.code,
        "name": a.name,
        "status": a.status or "Not Started",
        "discipline": a.discipline or "",
        "location": a.location or "",
        "planned_start": a.planned_start or "",
        "planned_finish": a.planned_finish or "",
        "actual_start": a.actual_start or "",
        "actual_finish": a.actual_finish or "",
        "priority": priority,
        "attention_score": score,
        "signals": [s["signal"] for s in signals],
        "reasons": [s["reason"] for s in signals] + notes,
        "signal_details": signals,
    }


def unlinked_items(db) -> list[dict]:
    """Evidence-level attention items not attached to any activity."""
    items = []
    for r in db.query(FieldReport).filter(FieldReport.category == "unmatched").order_by(
            FieldReport.report_code).all():
        items.append({
            "subject_type": "report", "subject_id": r.report_code,
            "name": (r.raw_text or "")[:120], "status": "Unlinked",
            "discipline": r.discipline or "", "location": r.location or "",
            "planned_start": "", "planned_finish": "", "actual_start": "", "actual_finish": "",
            "priority": "WATCH", "attention_score": W["UNMATCHED_EXECUTION"],
            "signals": ["UNMATCHED_EXECUTION"],
            "reasons": [f"No schedule relevance; held for investigation (filed {r.report_date}).",
                        f"evidence score {W['UNMATCHED_EXECUTION']}; unlinked evidence defaults to WATCH."],
            "signal_details": [{"signal": "UNMATCHED_EXECUTION",
                                "reason": "Field evidence could not be confidently linked to a schedule activity.",
                                "variance_days": None,
                                "evidence": {"report": r.report_code, "date": r.report_date}}],
        })
    for c in db.query(Conflict).order_by(Conflict.id).all():
        items.append({
            "subject_type": "conflict", "subject_id": c.evidence_a,
            "name": f"{c.conflict_type}: {c.evidence_a} vs {c.evidence_b}",
            "status": "Disputed", "discipline": "", "location": "",
            "planned_start": "", "planned_finish": "", "actual_start": "", "actual_finish": "",
            "priority": "ATTENTION", "attention_score": W["CONTRADICTION"],
            "signals": ["CONTRADICTION"],
            "reasons": [c.reason,
                        "automatic ATTENTION: conflicting execution evidence present."],
            "signal_details": [{"signal": "CONTRADICTION", "reason": c.reason,
                                "variance_days": None,
                                "evidence": {"conflict_type": c.conflict_type,
                                             "evidence_a": c.evidence_a, "evidence_b": c.evidence_b,
                                             "suggested_action": c.suggested_action}}],
        })
    return items


def project_risk(db, project_code: str, level: str = "") -> dict:
    """Whole-project attention board, derived live. Raises LookupError if unknown."""
    acts = project_activities(db, project_code)
    umap = _unmatched_links(db)
    items = [assess_activity(db, a, umap) for a in acts]
    items += unlinked_items(db)
    if level:
        items = [i for i in items if i["priority"] == level.upper()]
    by_priority: dict[str, int] = {}
    by_signal: dict[str, int] = {}
    for i in items:
        by_priority[i["priority"]] = by_priority.get(i["priority"], 0) + 1
        for s in i["signals"]:
            by_signal[s] = by_signal.get(s, 0) + 1
    order = {"ATTENTION": 0, "WATCH": 1, "NORMAL": 2}
    items.sort(key=lambda i: (order.get(i["priority"], 9), -i["attention_score"], i["subject_id"]))
    return {"project_code": project_code, "item_count": len(items),
            "summary": {"by_priority": by_priority, "by_signal": by_signal},
            "items": items,
            "note": "Advisory only: derived from stored BRIDGE-X evidence; not a prediction. "
                    "Execution-history figures are synthetic demonstration data."}
