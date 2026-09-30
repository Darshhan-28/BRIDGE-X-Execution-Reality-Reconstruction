"""Contradiction detection: conflicting claims about the same activity.

Uses the system's own stored links (match_candidates top-1 per report)
plus extracted events: a completion claim contradicted by a later
start / not-started status, or two different completion dates for the
same activity, is an error with both evidences cited.
"""
import json


def _links(db, activity_code: str, exclude: str) -> list[tuple[str, dict]]:
    """Other reports whose stored top-1 candidate is this activity."""
    from ..models import MatchCandidate

    out = []
    for r in db.query(MatchCandidate).filter(MatchCandidate.activity_code == activity_code).all():
        if r.report_code == exclude or r.rank != 1:
            continue
        try:
            out.append((r.report_code, json.loads(r.event_json)))
        except Exception:
            continue
    return out


def check_contradictions(ev, activity_code: str, proposal: str, db, report_code: str) -> dict:
    warnings, errors, reasons = [], [], []
    mine_type, mine_date = ev.event_type, ev.event_date or ""
    hits = []
    for code, other in _links(db, activity_code, report_code or ""):
        otype, odate = other.get("event_type", ""), other.get("date", other.get("event_date", ""))
        if mine_type == "completion" and otype in ("start", "status") and odate and mine_date and odate > mine_date:
            hits.append(f"{code} claims {otype} on {odate} after completion {mine_date}")
        elif otype == "completion" and mine_type in ("start", "status") and odate and mine_date and mine_date > odate:
            hits.append(f"{code} claims completion on {odate} before this {mine_type} {mine_date}")
        elif mine_type == "completion" and otype == "completion" and odate and mine_date and odate != mine_date:
            hits.append(f"{code} claims completion on a different date {odate} vs {mine_date}")
    if hits:
        errors.append(
            f"Contradiction on {activity_code}: " + "; ".join(hits) + ". Planner must reconcile evidence."
        )
    else:
        reasons.append(f"No contradicting claims found for {activity_code}.")
    return {"warnings": warnings, "errors": errors, "reasons": reasons}
