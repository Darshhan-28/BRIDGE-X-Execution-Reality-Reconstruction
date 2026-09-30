"""State-machine validation: only legal status transitions may be proposed.

States: Not Started -> In Progress -> Complete (forward only).
A completion/progress proposal against Complete is an error (duplicate).
Anything else is a legal forward transition; verification never applies it.
"""


def is_finished(activity) -> bool:
    return (activity.status or "") == "Complete" or (activity.progress or 0) >= 100


def check_state(ev, activity, proposal: str) -> dict:
    warnings, errors, reasons = [], [], []
    status = activity.status or "Not Started"
    if status == "Complete" and proposal in ("propose_complete", "propose_progress"):
        errors.append(
            f"{activity.code} is already 100% Complete; "
            f"another {'completion' if proposal == 'propose_complete' else 'progress'} claim is invalid."
        )
    elif proposal == "propose_complete":
        reasons.append(f"Transition {status} -> Complete is legal (proposal only, not applied).")
    elif proposal == "propose_progress":
        if status == "Not Started":
            warnings.append(f"First progress on {activity.code} (Not Started -> In Progress).")
        else:
            reasons.append(f"Progress update on {status} activity is legal.")
    else:
        reasons.append(f"No state transition proposed ({proposal}); state untouched.")
    return {"warnings": warnings, "errors": errors, "reasons": reasons}
