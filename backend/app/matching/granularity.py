"""Granularity resolver: one event rarely equals one activity.

Resolves ONE_TO_ONE / ONE_TO_MANY / PARTIAL / NEW_UNPLANNED from the
Phase-4 FieldEvent plus Phase-5 ranked candidates. Deterministic, no LLM.

Core safety rule: a broad report (e.g. "R204 piping completed") must
NEVER auto-complete an activity group. Coarse evidence plus a candidate
cluster means insufficient evidence and mandatory planner review.
"""
from .scorer import UNMATCHED_FLOOR

MARGIN_ONE_TO_ONE = 5.0   # min top1-top2 gap to pick a single activity
CLUSTER_MARGIN = 8.0      # band around top1 that forms a candidate group
HIGH_SAFE = 75.0          # top score that can carry a single pick alone
GROUP_CAP = 6             # max activities listed in a ONE_TO_MANY group

TYPES = ("ONE_TO_ONE", "ONE_TO_MANY", "PARTIAL", "NEW_UNPLANNED")


def _evidence_specific(ev) -> tuple[bool, list[str]]:
    """Specific = action + object + location (a pick needs a site)."""
    notes = []
    has_action = bool((ev.action or "").strip())
    has_object = bool((ev.object or "").strip())
    has_loc = bool((ev.location or "").strip())
    if not has_action:
        notes.append("no action detected")
    if not has_object:
        notes.append("no object detected")
    if not has_loc:
        notes.append("no location detected")
    return (has_action and has_object and has_loc, notes)


def resolve_granularity(ev, candidates: list[dict], unmatched: bool, match_reason: str = "") -> dict:
    """Classify the event->activity shape. Pure function, no I/O."""
    if unmatched or not candidates:
        refs = [c["activity_code"] for c in (candidates or [])[:3]]
        return {
            "type": "NEW_UNPLANNED",
            "activity_codes": [],
            "reference_ids": refs,
            "proposed_progress": None,
            "proposed_action": "propose_new_activity",
            "insufficient_evidence": True,
            "reason": (
                "No schedule activity above the retrieval floor; "
                f"treated as a new/unplanned event. {match_reason}".strip()
            ),
            "details": ["No confident schedule link; planner decides: new activity or ignore."],
        }

    top = candidates[0]
    second = candidates[1]["score"] if len(candidates) > 1 else 0.0
    margin = round(top["score"] - second, 1)

    # PARTIAL: report carries an explicit sub-100% progress value.
    pct = ev.progress_pct
    if ev.event_type == "progress" and pct is not None and pct < 100:
        return {
            "type": "PARTIAL",
            "activity_codes": [top["activity_code"]],
            "reference_ids": [],
            "proposed_progress": float(pct),
            "proposed_action": "propose_progress",
            "insufficient_evidence": False,
            "reason": (
                f"Report states {pct}% (not completion); propose a progress "
                f"update on {top['activity_code']} only, never completion."
            ),
            "details": [f"Progress signal {pct}% attributed to top candidate {top['activity_code']} ({top['score']})."],
        }

    specific, gaps = _evidence_specific(ev)
    cluster = [c["activity_code"] for c in candidates
               if top["score"] - c["score"] <= CLUSTER_MARGIN][:GROUP_CAP]

    # ONE_TO_MANY: coarse evidence + a real cluster -> never auto-complete.
    if not specific and len(cluster) >= 2:
        return {
            "type": "ONE_TO_MANY",
            "activity_codes": cluster,
            "reference_ids": [],
            "proposed_progress": None,
            "proposed_action": "planner_review",
            "insufficient_evidence": True,
            "reason": (
                "Broad report covering an activity group "
                f"({', '.join(gaps)}); evidence insufficient to complete any "
                "single activity. Group must NOT be auto-completed."
            ),
            "details": [
                f"{len(cluster)} candidate activities within {CLUSTER_MARGIN} pts of top ({top['score']}).",
                f"Top margin only {margin} pts — unsafe to pick one.",
                "Planner action: split the report across activities or request clarification.",
            ],
        }

    # ONE_TO_ONE: specific evidence with a decisive or high-safe top pick.
    if specific and (margin >= MARGIN_ONE_TO_ONE or top["score"] >= HIGH_SAFE):
        complete = ev.event_type == "completion"
        return {
            "type": "ONE_TO_ONE",
            "activity_codes": [top["activity_code"]],
            "reference_ids": [c["activity_code"] for c in candidates[1:3]],
            "proposed_progress": 100.0 if complete else None,
            "proposed_action": "propose_complete" if complete else "planner_review",
            "insufficient_evidence": False,
            "reason": (
                f"Specific evidence (action '{ev.action}', object '{ev.object}') "
                f"with a decisive top pick {top['activity_code']} ({top['score']}, margin {margin})."
                + ("" if complete else " Informational link only — no completion claimed.")
            ),
            "details": [f"Top pick margin {margin} pts over runner-up."],
        }

    # Fallback: specific-looking but indecisive -> treat as group review.
    group = [c["activity_code"] for c in candidates[:GROUP_CAP]]
    return {
        "type": "ONE_TO_MANY",
        "activity_codes": group,
        "reference_ids": [],
        "proposed_progress": None,
        "proposed_action": "planner_review",
        "insufficient_evidence": True,
        "reason": (
            f"Top pick {top['activity_code']} ({top['score']}) indecisive "
            f"(margin {margin}); evidence insufficient for a single activity. "
            "Group must NOT be auto-completed."
        ),
        "details": [f"Margin {margin} below {MARGIN_ONE_TO_ONE} and top below {HIGH_SAFE}."],
    }
