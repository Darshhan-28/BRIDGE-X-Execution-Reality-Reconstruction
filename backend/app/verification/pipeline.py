"""Verification pipeline: deterministic checks + confidence gate.

Never calls the LLM, never applies schedule updates. Every warning and
error preserves its evidence and reason for the audit trail.
"""
from ..config import settings
from .confidence_gate import decide
from .contradictions import check_contradictions
from .dependencies import check_dependencies
from .duplicates import check_duplicates
from .state_machine import check_state
from .temporal import check_temporal
from .variance import compute_variance


def _merge(*checks: dict) -> dict:
    warnings, errors, reasons = [], [], []
    for c in checks:
        warnings += c.get("warnings", [])
        errors += c.get("errors", [])
        reasons += c.get("reasons", [])
    return {"warnings": warnings, "errors": errors, "reasons": reasons,
            "valid": not errors}


def verify_proposal(ev, granularity: dict, candidates: list[dict], db, report_code: str = "") -> dict:
    gtype = granularity.get("type", "NEW_UNPLANNED")
    proposal = granularity.get("proposed_action", "planner_review")
    top_score = candidates[0]["score"] if candidates else 0.0
    margin = round(top_score - (candidates[1]["score"] if len(candidates) > 1 else 0.0), 1)

    if gtype in ("ONE_TO_MANY", "NEW_UNPLANNED"):
        note = ("Group proposal held for planner split; per-activity verification after split."
                if gtype == "ONE_TO_MANY" else
                "Unplanned event; nothing to verify against schedule.")
        merged = {"warnings": [note], "errors": [], "reasons": [note], "valid": True}
        per_activity, variance = {}, {}
    else:
        from ..models import Activity

        code = (granularity.get("activity_codes") or [None])[0]
        activity = db.query(Activity).filter(Activity.code == code).first() if code else None
        if not activity:
            merged = {"warnings": [], "errors": [f"Target activity {code} not found."],
                      "reasons": [], "valid": False}
            per_activity, variance = {}, {}
        else:
            t = check_temporal(ev, activity, proposal)
            d = check_dependencies(ev, activity, proposal, db)
            s = check_state(ev, activity, proposal)
            dup = check_duplicates(ev, candidates, proposal, db, report_code)
            con = check_contradictions(ev, activity.code, proposal, db, report_code)
            merged = _merge(t, d, s, dup, con)
            variance = compute_variance(ev, activity, proposal)
            merged["reasons"] += variance.get("details", [])
            per_activity = {
                "temporal": t, "dependencies": d, "state": s,
                "duplicates": dup, "contradictions": con,
            }

    gate = decide(top_score, margin, not merged["valid"], settings)
    # Granularity already routes groups/unplanned to review; keep gate honest.
    if gtype in ("ONE_TO_MANY", "NEW_UNPLANNED") and gate["decision"] == "PROPOSE":
        gate = {"decision": "REVIEW", "tier": "MEDIUM", "margin": margin,
                "forced": True,
                "reasons": [f"{gtype}: group/unplanned proposals always need a planner."]}
    return {
        "target": (granularity.get("activity_codes") or [None])[0],
        "proposal": proposal,
        "valid": merged["valid"],
        "warnings": merged["warnings"],
        "errors": merged["errors"],
        "reasons": merged["reasons"],
        "checks": per_activity,
        "variance": variance,
        "gate": gate,
    }
