"""Time Agent tools: database-grounded facts, zero invention.

Every tool returns {"facts": {...}, "citations": [...]} where citations
carry report_id / activity_id evidence. Tools are read-only; the LLM
composer (if any) only ever sees their JSON output.
"""
import json
from datetime import date

from .models import (
    Activity,
    Conflict,
    FieldReport,
    MatchCandidate,
    VerificationResult,
)


def _act(a: Activity) -> dict:
    return {"activity_id": a.code, "name": a.name, "discipline": a.discipline,
            "location": a.location, "status": a.status, "progress": a.progress,
            "planned": f"{a.planned_start}->{a.planned_finish}",
            "actual": f"{a.actual_start or '-'}->{a.actual_finish or '-'}"}


def _cite_activity(a: Activity, label: str) -> dict:
    return {"type": "activity", "id": a.code, "label": label}


def _cite_report(code: str, label: str) -> dict:
    return {"type": "report", "id": code, "label": label}


def activities_started_on(db, day: str) -> dict:
    rows = db.query(Activity).filter(Activity.actual_start == day).order_by(Activity.code).all()
    return {
        "facts": {"date": day, "count": len(rows), "activities": [_act(a) for a in rows]},
        "citations": [_cite_activity(a, f"{a.code} started {day}") for a in rows],
    }


def activities_completed_on(db, day: str) -> dict:
    rows = db.query(Activity).filter(Activity.actual_finish == day).order_by(Activity.code).all()
    return {
        "facts": {"date": day, "count": len(rows), "activities": [_act(a) for a in rows]},
        "citations": [_cite_activity(a, f"{a.code} finished {day}") for a in rows],
    }


def delayed_activities(db, location: str = "") -> dict:
    today = date.today().isoformat()
    q = db.query(Activity).filter(Activity.status != "Complete",
                                  Activity.planned_finish < today)
    if location:
        q = q.filter(Activity.location == location)
    rows = q.order_by(Activity.planned_finish).all()
    facts = []
    for a in rows:
        try:
            overdue = (date.fromisoformat(today) - date.fromisoformat(a.planned_finish)).days
        except ValueError:
            overdue = 0
        facts.append({**_act(a), "days_overdue": overdue})
    scope = f" at {location}" if location else ""
    return {
        "facts": {"count": len(rows), "location": location or "all", "activities": facts},
        "citations": [_cite_activity(a, f"{a.code} overdue{scope}") for a in rows],
    }


def unmatched_reports(db) -> dict:
    cats = db.query(FieldReport).filter(FieldReport.category == "unmatched").all()
    gated = [r for (r,) in db.query(VerificationResult.report_code).filter(
        VerificationResult.decision == "UNMATCHED").distinct().all()]
    seen, items, cites = set(), [], []
    for r in cats:
        seen.add(r.report_code)
        items.append({"report_id": r.report_code, "text": r.raw_text[:120],
                      "date": r.report_date, "why": "no schedule relevance (category)"})
        cites.append(_cite_report(r.report_code, "unmatched category"))
    for code in gated:
        if code in seen:
            continue
        r = db.query(FieldReport).filter(FieldReport.report_code == code).first()
        items.append({"report_id": code, "text": (r.raw_text[:120] if r else ""),
                      "date": r.report_date if r else "", "why": "below retrieval floor"})
        cites.append(_cite_report(code, "below retrieval floor"))
    return {"facts": {"count": len(items), "reports": items}, "citations": cites}


def explain_link(db, report_code: str) -> dict:
    rows = db.query(MatchCandidate).filter(
        MatchCandidate.report_code == report_code).order_by(MatchCandidate.rank).all()
    if not rows:
        return {"facts": {"report_id": report_code, "error": "no match run found; run POST /api/matching/run first."},
                "citations": []}
    ev = json.loads(rows[0].event_json)
    cands = [{"activity_id": r.activity_code, "rank": r.rank, "score": r.score,
              "why": json.loads(r.why_json)} for r in rows]
    vrow = db.query(VerificationResult).filter(
        VerificationResult.report_code == report_code).order_by(
        VerificationResult.id.desc()).first()
    verification = json.loads(vrow.result_json) if vrow else {}
    top = cands[0]
    margin = round(top["score"] - (cands[1]["score"] if len(cands) > 1 else 0.0), 1)
    facts = {"report_id": report_code, "event": ev, "top_activity": top["activity_id"],
             "top_score": top["score"], "margin": margin, "candidates": cands,
             "gate": verification.get("gate", {}), "granularity": verification.get("proposal", ""),
             "verification_errors": verification.get("errors", []),
             "verification_reasons": verification.get("reasons", [])[:6]}
    cites = [_cite_report(report_code, "source evidence"),
             {"type": "activity", "id": top["activity_id"], "label": f"linked {top['activity_id']} @ {top['score']}"}]
    return {"facts": facts, "citations": cites}


def conflicts(db) -> dict:
    rows = db.query(Conflict).all()
    facts = [{"type": r.conflict_type, "evidence_a": r.evidence_a, "evidence_b": r.evidence_b,
              "reason": r.reason, "suggested_action": r.suggested_action} for r in rows]
    cites = []
    for r in rows:
        cites.append(_cite_report(r.evidence_a, f"{r.conflict_type} evidence A"))
        cites.append(_cite_report(r.evidence_b, f"{r.conflict_type} evidence B"))
    return {"facts": {"count": len(rows), "conflicts": facts}, "citations": cites}


def activity_status(db, code: str) -> dict:
    a = db.query(Activity).filter(Activity.code == code).first()
    if not a:
        return {"facts": {"activity_id": code, "error": "activity not found."}, "citations": []}
    from .verification.dependencies import predecessors

    preds = predecessors(code, db)
    pred_states = []
    for p in preds:
        pa = db.query(Activity).filter(Activity.code == p).first()
        pred_states.append({"activity_id": p, "status": pa.status if pa else "missing"})
    vrow = db.query(VerificationResult).filter(
        VerificationResult.target_activity == code).order_by(
        VerificationResult.id.desc()).first()
    latest = {}
    if vrow:
        try:
            full = json.loads(vrow.result_json)
            latest = {"report": vrow.report_code, "decision": vrow.decision,
                      "errors": full.get("errors", [])}
        except Exception:
            latest = {}
    facts = {"activity": _act(a), "predecessors": pred_states, "latest_review": latest}
    cites = [_cite_activity(a, f"status of {a.code}")]
    cites += [{"type": "activity", "id": p["activity_id"], "label": f"predecessor {p['activity_id']}"}
              for p in pred_states]
    return {"facts": facts, "citations": cites}


TOOLS = {
    "activities_started_on": activities_started_on,
    "activities_completed_on": activities_completed_on,
    "delayed_activities": delayed_activities,
    "unmatched_reports": unmatched_reports,
    "explain_link": explain_link,
    "conflicts": conflicts,
    "activity_status": activity_status,
}
