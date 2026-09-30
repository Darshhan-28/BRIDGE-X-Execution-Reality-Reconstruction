"""Duplicate detection: identical normalized claims across reports.

Compares the candidate report's normalized text against all other stored
field reports. Exact normalized duplicates are errors (same claim filed
twice); nothing is merged or overwritten here — planner decides in Phase 8.
"""
import re


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def check_duplicates(ev, candidates: list[dict], proposal: str, db, report_code: str) -> dict:
    from ..models import FieldReport

    warnings, errors, reasons = [], [], []
    mine = ""
    if report_code:
        mine_rec = db.query(FieldReport).filter(FieldReport.report_code == report_code).first()
        mine = normalize(mine_rec.raw_text) if mine_rec else normalize(ev.evidence_text)
    else:
        mine = normalize(ev.evidence_text)
    if not mine:
        warnings.append("Empty claim text; duplicate check skipped.")
        return {"warnings": warnings, "errors": errors, "reasons": reasons}
    dupes = []
    for r in db.query(FieldReport).all():
        if report_code and r.report_code == report_code:
            continue
        if normalize(r.raw_text) == mine:
            dupes.append(r.report_code)
    if dupes:
        errors.append(
            f"Duplicate claim: identical report text already filed as {', '.join(sorted(dupes))}; "
            "possible double-counting, merge evidence instead of updating twice."
        )
    else:
        reasons.append("No identical duplicate claim found.")
    return {"warnings": warnings, "errors": errors, "reasons": reasons}
