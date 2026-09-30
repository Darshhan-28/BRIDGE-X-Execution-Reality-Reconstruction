"""Dependency validation: FS predecessors must be complete before completion."""
from .state_machine import is_finished


def predecessors(code: str, db) -> list[str]:
    from ..models import ActivityRelationship

    return [r.from_code for r in db.query(ActivityRelationship).filter(
        ActivityRelationship.to_code == code).all()]


def check_dependencies(ev, activity, proposal: str, db) -> dict:
    warnings, errors, reasons = [], [], []
    if proposal not in ("propose_complete", "propose_progress"):
        reasons.append("Informational link; dependency order not enforced.")
        return {"warnings": warnings, "errors": errors, "reasons": reasons}
    from ..models import Activity

    preds = predecessors(activity.code, db)
    if not preds:
        reasons.append(f"{activity.code} has no predecessors; order trivially satisfied.")
        return {"warnings": warnings, "errors": errors, "reasons": reasons}
    blocked = []
    for p in preds:
        pa = db.query(Activity).filter(Activity.code == p).first()
        if not pa:
            warnings.append(f"Predecessor {p} not found in schedule.")
            continue
        if not is_finished(pa):
            blocked.append(f"{p} ({pa.status})")
    if blocked and proposal == "propose_complete":
        errors.append(
            f"Schedule dependency inconsistency: {activity.code} reported complete "
            f"but predecessor(s) not completed: {', '.join(blocked)}."
        )
    elif blocked:
        warnings.append(
            f"Early progress: predecessor(s) not completed: {', '.join(blocked)}."
        )
    else:
        reasons.append(f"All {len(preds)} predecessor(s) completed.")
    return {"warnings": warnings, "errors": errors, "reasons": reasons}
