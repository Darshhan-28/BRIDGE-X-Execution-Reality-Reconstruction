"""Human review service: queue, gated actions, schedule-update records, audit.

Rules:
- Only approved proposals create schedule updates — and updates are
  records only; the activities table is never silently overwritten.
- Gate PROPOSE + valid verification: clean approve.
- Anything else (REVIEW / UNMATCHED / verification errors): approval,
  remap-to-invalid-target and re-decisions require explicit human
  override (force=true) with a written reason, else 422/409.
- Every consequential action writes an audit event with actor, action,
  IDs, before/after values, timestamp and reason.
"""
import json
from datetime import datetime, timezone

from .models import (
    Activity,
    AuditEvent,
    FieldReport,
    MatchCandidate,
    ReviewDecision,
    ScheduleUpdate,
    VerificationResult,
)


class ReviewError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def audit(db, actor: str, action: str, report_code: str, activity_codes: list[str],
          before: dict, after: dict, reason: str) -> AuditEvent:
    rec = AuditEvent(
        timestamp=now(), actor=actor or "planner", action=action,
        report_code=report_code, activity_codes=json.dumps(activity_codes),
        before_json=json.dumps(before), after_json=json.dumps(after),
        reason=reason or "",
    )
    db.add(rec)
    return rec


def snapshot(activity: Activity | None) -> dict:
    if not activity:
        return {}
    return {"code": activity.code, "status": activity.status, "progress": activity.progress,
            "actual_start": activity.actual_start, "actual_finish": activity.actual_finish}


def after_values(ev, activity: Activity | None, proposal: str) -> tuple[str, dict]:
    """Map a proposal to (update_type, after-values). Record only."""
    if proposal == "propose_complete" and activity:
        return ("complete", {"code": activity.code, "status": "Complete", "progress": 100.0,
                             "actual_start": activity.actual_start or ev.event_date or "",
                             "actual_finish": ev.event_date or ""})
    if proposal == "propose_progress" and activity:
        return ("progress", {"code": activity.code, "status": "In Progress",
                             "progress": float(ev.progress_pct or 0),
                             "actual_start": activity.actual_start or ev.event_date or ""})
    if proposal == "propose_new_activity":
        return ("new_activity", {"proposed_name": f"Unplanned: {(ev.evidence_text or '')[:80]}",
                                 "discipline": ev.discipline or "", "location": ev.location or "",
                                 "event_date": ev.event_date or "", "status": "Proposed"})
    return ("info", {"acknowledged": True, "no_state_change": True,
                     "event_type": ev.event_type or ""})


def latest_verification(db, report_code: str) -> tuple[VerificationResult | None, dict]:
    row = db.query(VerificationResult).filter(
        VerificationResult.report_code == report_code).order_by(VerificationResult.id.desc()).first()
    if not row:
        return None, {}
    try:
        return row, json.loads(row.result_json)
    except Exception:
        return row, {}


def stored_event(db, report_code: str):
    row = db.query(MatchCandidate).filter(MatchCandidate.report_code == report_code).first()
    if not row:
        return None
    from .llm.base import FieldEvent

    try:
        return FieldEvent(**json.loads(row.event_json))
    except Exception:
        return None


def stored_candidates(db, report_code: str) -> list[dict]:
    rows = db.query(MatchCandidate).filter(
        MatchCandidate.report_code == report_code).order_by(MatchCandidate.rank).all()
    return [{"activity_code": r.activity_code, "rank": r.rank, "score": r.score,
             "signals": json.loads(r.signals_json), "why": json.loads(r.why_json)} for r in rows]


def get_decision(db, report_code: str) -> ReviewDecision | None:
    return db.query(ReviewDecision).filter(ReviewDecision.report_code == report_code).first()


def _check_redecide(db, report_code: str, force: bool):
    d = get_decision(db, report_code)
    if d and d.decision != "pending" and not force:
        raise ReviewError(409, f"{report_code} already decided ({d.decision}); use force=true to re-decide.")


def set_decision(db, report_code: str, decision: str, target: str, actor: str, reason: str):
    d = get_decision(db, report_code)
    if not d:
        d = ReviewDecision(report_code=report_code)
        db.add(d)
    d.decision, d.target_activity, d.actor, d.reason, d.created_at = (
        decision, target, actor or "planner", reason or "", now())


def bucket_for(verification: dict, granularity_type: str) -> str:
    errs = " ".join(verification.get("errors", "") if isinstance(verification.get("errors"), str)
                    else verification.get("errors", []))
    if "ontradiction" in errs or "uplicate" in errs:
        return "CONFLICT"
    gate = (verification.get("gate") or {}).get("decision", "")
    if gate == "UNMATCHED" or granularity_type == "NEW_UNPLANNED":
        return "UNMATCHED"
    if gate == "PROPOSE":
        return "HIGH"
    if verification.get("valid"):
        return "MEDIUM"
    return "LOW"


def build_queue(db, bucket: str = "") -> list[dict]:
    from .matching.granularity import resolve_granularity

    codes = [c for (c,) in db.query(MatchCandidate.report_code).distinct().order_by(
        MatchCandidate.report_code).all()]
    items = []
    for code in codes:
        cands = stored_candidates(db, code)
        ev = stored_event(db, code)
        _, res = latest_verification(db, code)
        if not ev or not res:
            continue
        from .matching.scorer import UNMATCHED_FLOOR

        unmatched = not cands or cands[0]["score"] < UNMATCHED_FLOOR
        gran = resolve_granularity(ev, cands, unmatched)
        verification = res
        b = bucket_for(verification, gran["type"])
        d = get_decision(db, code)
        margin = round(cands[0]["score"] - (cands[1]["score"] if len(cands) > 1 else 0.0), 1)
        items.append({
            "report_code": code,
            "bucket": b,
            "gate": verification.get("gate", {}),
            "granularity_type": gran["type"],
            "top_activity": cands[0]["activity_code"] if cands else "",
            "top_score": cands[0]["score"] if cands else 0.0,
            "margin": margin,
            "event_type": ev.event_type,
            "event_date": ev.event_date,
            "verification_valid": bool(verification.get("valid")),
            "verification_errors": verification.get("errors", []),
            "decision": {"state": d.decision if d else "pending",
                         "target": d.target_activity if d else "",
                         "actor": d.actor if d else "", "reason": d.reason if d else ""},
        })
    if bucket:
        items = [i for i in items if i["bucket"] == bucket.upper()]
    order = {"CONFLICT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNMATCHED": 4}
    items.sort(key=lambda i: (order.get(i["bucket"], 9), i["report_code"]))
    return items


def do_approve(db, report_code: str, actor: str, reason: str, force: bool) -> dict:
    _, res = latest_verification(db, report_code)
    if not res:
        raise ReviewError(422, f"{report_code}: no verification found; run POST /api/matching/run first.")
    _check_redecide(db, report_code, force)
    target = res.get("target") or ""
    if not target:
        raise ReviewError(422, f"{report_code}: no schedule target; use mark-new or merge instead.")
    gate = res.get("gate", {})
    valid = bool(res.get("valid"))
    override = not (valid and gate.get("decision") == "PROPOSE")
    if override and not (force and (reason or "").strip()):
        raise ReviewError(422, f"{report_code}: gate={gate.get('decision')}, valid={valid}; "
                               "approval needs explicit human override (force=true + reason).")
    activity = db.query(Activity).filter(Activity.code == target).first()
    if not activity:
        raise ReviewError(404, f"Target activity {target} not found.")
    ev = stored_event(db, report_code)
    utype, after = after_values(ev, activity, res.get("proposal", ""))
    before = snapshot(activity)
    upd = ScheduleUpdate(
        report_code=report_code, activity_code=target, update_type=utype,
        gate_decision=gate.get("decision", ""), proposal=res.get("proposal", ""),
        before_json=json.dumps(before), after_json=json.dumps(after),
        status="approved", actor=actor or "planner", reason=reason or "",
        forced=int(bool(override)), created_at=now())
    db.add(upd)
    db.flush()
    from .memory import learn_from_approval

    learned = learn_from_approval(db, ev, activity, report_code, actor or "planner", now())
    set_decision(db, report_code, "approved", target, actor, reason)
    audit(db, actor, "approve", report_code, [target],
          {"before": before, "gate": gate.get("decision"), "valid": valid},
          {"update_id": upd.id, "after": after, "forced": bool(override),
           "vocabulary_learned": learned}, reason)
    db.commit()
    return {"update_id": upd.id, "forced": bool(override), "after": after,
            "vocabulary_learned": learned}


def do_reject(db, report_code: str, actor: str, reason: str, force: bool) -> dict:
    if not (reason or "").strip():
        raise ReviewError(422, "Rejection requires a reason.")
    _, res = latest_verification(db, report_code)
    if not res:
        raise ReviewError(422, f"{report_code}: no verification found; run POST /api/matching/run first.")
    _check_redecide(db, report_code, force)
    set_decision(db, report_code, "rejected", res.get("target") or "", actor, reason)
    audit(db, actor, "reject", report_code, [res.get("target") or ""],
          {"state": "pending_review"}, {"state": "rejected"}, reason)
    db.commit()
    return {"report_code": report_code, "decision": "rejected"}


def do_remap(db, report_code: str, activity_code: str, actor: str, reason: str, force: bool) -> dict:
    from .verification.pipeline import verify_proposal

    if not (reason or "").strip():
        raise ReviewError(422, "Remap requires a reason (why is the new target correct?).")
    _, res = latest_verification(db, report_code)
    if not res:
        raise ReviewError(422, f"{report_code}: no verification found; run POST /api/matching/run first.")
    _check_redecide(db, report_code, force)
    activity = db.query(Activity).filter(Activity.code == activity_code).first()
    if not activity:
        raise ReviewError(404, f"Activity {activity_code} not found.")
    ev = stored_event(db, report_code)
    if ev.event_type == "completion":
        proposal = "propose_complete"
    elif ev.event_type == "progress" and (ev.progress_pct or 0) < 100:
        proposal = "propose_progress"
    else:
        proposal = "planner_review"
    gran = {"type": "ONE_TO_ONE", "activity_codes": [activity_code], "proposed_action": proposal}
    verification = verify_proposal(ev, gran, stored_candidates(db, report_code), db, report_code)
    if not verification["valid"] and not force:
        raise ReviewError(422, f"Remap target {activity_code} fails verification "
                               f"({'; '.join(verification['errors'])[:200]}); use force=true to override.")
    utype, after = after_values(ev, activity, proposal)
    before = snapshot(activity)
    upd = ScheduleUpdate(
        report_code=report_code, activity_code=activity_code, update_type=utype,
        gate_decision=verification["gate"]["decision"], proposal=proposal,
        before_json=json.dumps(before), after_json=json.dumps(after),
        status="approved", actor=actor or "planner", reason=reason,
        forced=int(not verification["valid"]), created_at=now())
    db.add(upd)
    db.flush()
    from .memory import learn_from_approval

    learned = learn_from_approval(db, ev, activity, report_code, actor or "planner", now())
    set_decision(db, report_code, "remapped", activity_code, actor, reason)
    audit(db, actor, "remap", report_code, [res.get("target") or "", activity_code],
          {"before": before, "original_target": res.get("target"), "verification": verification["gate"]},
          {"update_id": upd.id, "after": after, "vocabulary_learned": learned}, reason)
    db.commit()
    return {"update_id": upd.id, "target": activity_code, "verification": verification,
            "vocabulary_learned": learned}


def do_mark_new(db, report_code: str, actor: str, reason: str, activity_name: str = "") -> dict:
    _, res = latest_verification(db, report_code)
    if not res:
        raise ReviewError(422, f"{report_code}: no verification found; run POST /api/matching/run first.")
    if not (reason or "").strip():
        raise ReviewError(422, "Mark-new requires a reason (why is this unplanned work?).")
    _check_redecide(db, report_code, False)
    ev = stored_event(db, report_code)
    if activity_name.strip():
        ev.evidence_text = activity_name.strip()  # planner-supplied working title
    utype, after = after_values(ev, None, "propose_new_activity")
    upd = ScheduleUpdate(
        report_code=report_code, activity_code="", update_type=utype,
        gate_decision=(res.get("gate") or {}).get("decision", ""), proposal="propose_new_activity",
        before_json=json.dumps({}), after_json=json.dumps(after),
        status="approved", actor=actor or "planner", reason=reason,
        forced=0, created_at=now())
    db.add(upd)
    db.flush()
    set_decision(db, report_code, "marked_new", "", actor, reason)
    audit(db, actor, "mark_new", report_code, [], {"state": "pending_review"},
          {"update_id": upd.id, "proposed": after}, reason)
    db.commit()
    return {"update_id": upd.id, "proposed": after}


def do_merge(db, report_code: str, into_report_code: str, actor: str, reason: str) -> dict:
    if not (reason or "").strip():
        raise ReviewError(422, "Merge requires a reason (why is this the same claim?).")
    _, res = latest_verification(db, report_code)
    _, into_res = latest_verification(db, into_report_code)
    if not res:
        raise ReviewError(422, f"{report_code}: no verification found; run POST /api/matching/run first.")
    if not into_res:
        raise ReviewError(422, f"{into_report_code}: no verification found; run POST /api/matching/run first.")
    _check_redecide(db, report_code, False)
    target = into_res.get("target") or ""
    attached_to = None
    upd = db.query(ScheduleUpdate).filter(
        ScheduleUpdate.report_code == into_report_code,
        ScheduleUpdate.status == "approved").order_by(ScheduleUpdate.id.desc()).first()
    if upd:
        try:
            after = json.loads(upd.after_json)
        except Exception:
            after = {}
        merged = after.get("merged_evidence", [])
        if report_code not in merged:
            merged.append(report_code)
        after["merged_evidence"] = merged
        upd.after_json = json.dumps(after)
        attached_to = upd.id
    set_decision(db, report_code, "merged", target, actor, f"merged into {into_report_code}: {reason}")
    audit(db, actor, "merge", report_code, [target],
          {"state": "pending_review", "into": into_report_code},
          {"state": "merged", "attached_to_update": attached_to}, reason)
    db.commit()
    return {"report_code": report_code, "merged_into": into_report_code, "attached_to_update": attached_to}
