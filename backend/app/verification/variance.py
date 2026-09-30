"""Planned-vs-actual variance: how far is this claim from plan? Informational."""
from datetime import date


def _d(s: str):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def compute_variance(ev, activity, proposal: str) -> dict:
    ps, pf = _d(activity.planned_start or ""), _d(activity.planned_finish or "")
    out = {"planned_duration_days": None, "finish_variance_days": None,
           "elapsed_to_claim_days": None, "verdict": "n/a", "details": []}
    if ps and pf:
        out["planned_duration_days"] = (pf - ps).days
        out["details"].append(f"Planned {ps} -> {pf} ({out['planned_duration_days']}d).")
    ed = _d(ev.event_date)
    if proposal == "propose_complete" and pf and ed:
        out["finish_variance_days"] = (ed - pf).days
        v = out["finish_variance_days"]
        out["verdict"] = "behind plan" if v > 0 else ("ahead of plan" if v < 0 else "on plan")
        out["details"].append(f"Claimed finish {ed} vs planned {pf}: {v:+d}d ({out['verdict']}).")
    astart = _d(activity.actual_start or "")
    if astart and ed:
        out["elapsed_to_claim_days"] = (ed - astart).days
        out["details"].append(f"{out['elapsed_to_claim_days']}d from actual start {astart} to claim.")
    return out
