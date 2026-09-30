"""P15: Execution Graph Intelligence — contextual, read-only, deterministic.

Builds a local execution neighborhood from the EXISTING schedule data
(activity_relationships, WBS, activity states, stored field events).
No duplicate schedule data, no LLM, no graph database, no writes, no
scheduling decisions. P7 verification remains authoritative; this layer
only explains context and may reference stored verification results.

Safety: the graph NEVER changes status/dates/relationships, approves
reviews, or bypasses gates. It returns evidence + reasons only.
"""
import json

from .models import Activity, ActivityRelationship, VerificationResult

MAX_DEPTH = 2
FINISHED = ("Complete",)


def is_finished(a) -> bool:
    return (a.status or "") in FINISHED or (a.progress or 0) >= 100


def node(a, rel_type: str = "", via: str = "", level: int = 1,
         direction: str = "") -> dict:
    return {
        "code": a.code, "name": a.name, "status": a.status or "Not Started",
        "progress": a.progress or 0.0,
        "planned_start": a.planned_start or "", "planned_finish": a.planned_finish or "",
        "actual_start": a.actual_start or "", "actual_finish": a.actual_finish or "",
        "rel_type": rel_type, "via": via, "level": level, "direction": direction,
    }


def _by_code(db, code: str):
    return db.query(Activity).filter(Activity.code == code).first()


def _pred_edges(db, code: str):
    return db.query(ActivityRelationship).filter(
        ActivityRelationship.to_code == code).order_by(ActivityRelationship.from_code).all()


def _succ_edges(db, code: str):
    return db.query(ActivityRelationship).filter(
        ActivityRelationship.from_code == code).order_by(ActivityRelationship.to_code).all()


def neighborhood(db, code: str, depth: int = 1) -> dict:
    """Local execution neighborhood. Raises LookupError for unknown codes."""
    depth = max(1, min(int(depth or 1), MAX_DEPTH))
    root = _by_code(db, code)
    if not root:
        raise LookupError(f"Activity {code} not found.")
    preds, succs, second = [], [], []
    for e in _pred_edges(db, code):
        pa = _by_code(db, e.from_code)
        if pa:
            preds.append(node(pa, e.rel_type or "FS", direction="pred"))
    for e in _succ_edges(db, code):
        sa = _by_code(db, e.to_code)
        if sa:
            succs.append(node(sa, e.rel_type or "FS", direction="succ"))
    if depth >= 2:
        for p in preds:
            for e in _pred_edges(db, p["code"]):
                pa = _by_code(db, e.from_code)
                if pa and pa.code != code:
                    second.append(node(pa, e.rel_type or "FS", via=p["code"],
                                       level=2, direction="pred"))
        for s in succs:
            for e in _succ_edges(db, s["code"]):
                sa = _by_code(db, e.to_code)
                if sa and sa.code != code:
                    second.append(node(sa, e.rel_type or "FS", via=s["code"],
                                       level=2, direction="succ"))
    # Backbone: longest deterministic strip (first pred <- ... <- self -> first succ ...)
    back, seen = [], {code}
    cur = preds[0]["code"] if preds else None
    trail = []
    while cur and cur not in seen and len(trail) < depth:
        seen.add(cur)
        ca = _by_code(db, cur)
        if not ca:
            break
        trail.append(node(ca, "FS", level=1, direction="pred"))
        nxt = _pred_edges(db, cur)
        cur = nxt[0].from_code if nxt else None
    back.extend(reversed(trail))
    back.append(node(root, "", level=0, direction="self"))
    cur = succs[0]["code"] if succs else None
    fwd, n = [], 0
    while cur and cur not in seen and n < depth:
        seen.add(cur)
        n += 1
        ca = _by_code(db, cur)
        if not ca:
            break
        fwd.append(node(ca, "FS", level=1, direction="succ"))
        nxt = _succ_edges(db, cur)
        cur = nxt[0].to_code if nxt else None
    back.extend(fwd)
    return {"activity": node(root, "", level=0, direction="self"),
            "predecessors": preds, "successors": succs,
            "second_level": second, "backbone": back, "depth": depth}


def _evidence(codes, db) -> dict:
    ev = {}
    for c in codes:
        a = _by_code(db, c)
        if a:
            ev[c] = {"status": a.status or "Not Started",
                     "planned_finish": a.planned_finish or "",
                     "actual_start": a.actual_start or "",
                     "actual_finish": a.actual_finish or ""}
    return ev


def describe_event(ev) -> str:
    bits = []
    for p in [ev.action or "", ev.object or "", ev.size or ""]:
        if p and (not bits or p.lower() != bits[-1].lower()):
            bits.append(p)
    what = " ".join(bits) or "reported work"
    return f"{what} {ev.event_type or ''}".strip()


def analyze(db, code: str, ev=None, proposal: str = "", depth: int = 1) -> dict:
    """Neighborhood + deterministic execution-context checks.

    ev/proposal are optional: without an event only stored-state checks
    (successor-ahead, blocked chain, isolation) run. Every warning names
    activity codes, relationship type and status/date evidence.
    """
    nb = neighborhood(db, code, depth)
    warnings, reasons = [], []
    preds = nb["predecessors"]
    succs = nb["successors"]
    me = nb["activity"]

    # --- stored-state checks (no event needed) ---
    ahead = [s for s in succs
             if s["actual_finish"] or s["status"] in FINISHED]
    if ahead and me["status"] not in FINISHED:
        codes = [me["code"]] + [s["code"] for s in ahead]
        warnings.append({
            "kind": "successor_ahead",
            "activities": codes,
            "rel_type": "FS",
            "evidence": _evidence(codes, db),
            "message": (f"{', '.join(s['code'] for s in ahead)} already finished "
                        f"while {me['code']} is {me['status']}; execution order looks inverted."),
        })
    chain_blocked = [p for p in preds if p["status"] == "Not Started"]
    chain_blocked += [s for s in nb["second_level"]
                      if s["direction"] == "pred" and s["status"] == "Not Started"
                      and s["code"] not in {p["code"] for p in chain_blocked}]
    if chain_blocked:
        codes = [me["code"]] + [p["code"] for p in chain_blocked]
        warnings.append({
            "kind": "blocked_chain",
            "activities": codes,
            "rel_type": "FS",
            "evidence": _evidence(codes, db),
            "message": (f"Dependency chain into {me['code']} contains "
                        f"{len(chain_blocked)} not-started predecessor(s): "
                        + ", ".join(f"{p['code']} ({p['status']})" for p in chain_blocked) + "."),
        })
    if not preds and not succs:
        reasons.append(f"{me['code']} has no predecessor/successor links; isolated in the schedule graph.")

    # --- event-context checks (reported vs expected order) ---
    if ev is not None:
        what = describe_event(ev)
        if proposal == "propose_complete":
            for p in preds:
                if p["status"] not in FINISHED:
                    warnings.append({
                        "kind": "blocked_predecessor",
                        "activities": [me["code"], p["code"]],
                        "rel_type": "FS",
                        "evidence": _evidence([me["code"], p["code"]], db),
                        "message": (f"Reported: {what} -> {me['code']}; "
                                    f"Required predecessor: {p['code']}; "
                                    f"Current predecessor state: {p['status']}; "
                                    f"Result: Dependency sequence conflict -> REVIEW."),
                    })
            if not chain_blocked:
                reasons.append(f"All {len(preds)} predecessor(s) of {me['code']} completed; reported completion fits the chain.")
        elif proposal == "propose_progress" or (ev.event_type or "") == "start":
            for p in preds:
                if p["status"] not in FINISHED:
                    warnings.append({
                        "kind": "early_start",
                        "activities": [me["code"], p["code"]],
                        "rel_type": "FS",
                        "evidence": _evidence([me["code"], p["code"]], db),
                        "message": (f"Reported: {what} -> {me['code']} started while "
                                    f"required predecessor {p['code']} is {p['status']}; "
                                    f"early start vs FS sequence -> REVIEW."),
                    })
            if not chain_blocked:
                reasons.append(f"Predecessors of {me['code']} completed; reported start fits the chain.")
        else:
            reasons.append("Informational link only; no sequence claim to check against the chain.")

    latest = db.query(VerificationResult).filter(
        VerificationResult.target_activity == code).order_by(
        VerificationResult.id.desc()).first()
    latest_review = None
    if latest:
        try:
            full = json.loads(latest.result_json)
            latest_review = {"report": latest.report_code, "decision": latest.decision,
                             "valid": bool(full.get("valid")),
                             "errors": full.get("errors", [])[:3]}
        except Exception:
            latest_review = {"report": latest.report_code, "decision": latest.decision}
    return {**nb, "warnings": warnings, "reasons": reasons, "latest_review": latest_review}
