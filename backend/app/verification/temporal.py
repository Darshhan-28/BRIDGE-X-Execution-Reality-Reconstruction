"""Temporal validation: date order, future claims, actual-start consistency."""
from datetime import date

from ..ingestion import normalize_date


def _d(s: str):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def check_temporal(ev, activity, proposal: str) -> dict:
    warnings, errors, reasons = [], [], []
    ed = _d(ev.event_date)
    if not ed:
        errors.append(f"Event date '{ev.event_date}' missing/unparseable; cannot verify timing.")
        return {"warnings": warnings, "errors": errors, "reasons": reasons}
    today = date.today()
    if proposal in ("propose_complete", "propose_progress") and ed > today:
        errors.append(f"Future event reported as done: {ed} > today {today}.")
    else:
        reasons.append(f"Event date {ed} is not in the future.")
    astart = _d(activity.actual_start or "")
    if astart and ed < astart:
        errors.append(f"Event {ed} predates actual start {astart} of {activity.code}.")
    elif astart:
        reasons.append(f"Event {ed} on/after actual start {astart}.")
    afin = _d(activity.actual_finish or "")
    if astart and afin and afin < astart:
        warnings.append(f"Stored data issue: {activity.code} finish {afin} < start {astart}.")
    # Cross-check any explicit date mention surviving normalization.
    norm = normalize_date(ev.event_date)
    if norm != ev.event_date:
        warnings.append(f"Event date '{ev.event_date}' normalized to '{norm}'.")
    return {"warnings": warnings, "errors": errors, "reasons": reasons}
