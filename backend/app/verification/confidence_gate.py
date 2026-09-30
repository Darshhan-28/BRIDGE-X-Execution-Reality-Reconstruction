"""Confidence gate: scores propose nothing by themselves.

HIGH (top >= 85 and margin >= 15)      -> PROPOSE
MEDIUM (60-85, or margin < 15)         -> REVIEW
LOW (top < 60)                         -> UNMATCHED
Any verification error                 -> REVIEW (forced, overrides PROPOSE)

Thresholds come from config.py and are adjustable without code changes.
"""


def decide(top_score: float, margin: float, has_errors: bool, settings) -> dict:
    reasons = []
    if has_errors:
        return {
            "decision": "REVIEW",
            "tier": "MEDIUM",
            "margin": margin,
            "forced": True,
            "reasons": ["Verification errors present; automatic proposal blocked, planner must review."],
        }
    if top_score < settings.MEDIUM_THRESHOLD:
        reasons.append(f"Top {top_score} below {settings.MEDIUM_THRESHOLD}: low confidence.")
        return {"decision": "UNMATCHED", "tier": "LOW", "margin": margin, "forced": False, "reasons": reasons}
    if top_score >= settings.HIGH_THRESHOLD and margin >= settings.MIN_MARGIN:
        reasons.append(f"Top {top_score} >= {settings.HIGH_THRESHOLD} with margin {margin} >= {settings.MIN_MARGIN}.")
        return {"decision": "PROPOSE", "tier": "HIGH", "margin": margin, "forced": False, "reasons": reasons}
    if margin < settings.MIN_MARGIN:
        reasons.append(f"Margin {margin} < {settings.MIN_MARGIN}: ambiguous top candidates.")
    else:
        reasons.append(f"Top {top_score} in review band {settings.MEDIUM_THRESHOLD}-{settings.HIGH_THRESHOLD}.")
    return {"decision": "REVIEW", "tier": "MEDIUM", "margin": margin, "forced": False, "reasons": reasons}
