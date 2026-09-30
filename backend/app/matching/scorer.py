"""Weighted contextual scorer with per-signal explainability.

score = 100 * sum(w_i * signal_i), weights from config.py:
semantic + lexical + discipline + location + object + size/tag + WBS + state.
Every candidate carries its signals plus a WHY list so evaluators see
the reasons, never just a number. No LLM involved.

P14: human-approved project vocabulary adds a SEPARATE bounded bonus
(base_score kept intact; score = base + vocab_bonus, cap +5.0).
Ranking, floor, granularity and gate consume the decision score through
unchanged paths — vocabulary flows through the gates, never around them.
"""
from .fingerprint import Fingerprint

UNMATCHED_FLOOR = 45.0  # verified: ambiguous cluster ~52, best genuine-miss ~39


def _wbs_match(ev_fp: Fingerprint, afp: Fingerprint) -> float:
    """WBS/context proxy: same discipline+location group as the activity."""
    if not ev_fp.discipline and not ev_fp.location:
        return 0.0
    d = 1.0 if (ev_fp.discipline and ev_fp.discipline == afp.discipline) else 0.0
    loc = 1.0 if (ev_fp.location and ev_fp.location == afp.location) else 0.0
    if ev_fp.discipline and ev_fp.location:
        return 1.0 if (d and loc) else (0.5 if (d or loc) else 0.0)
    return d or loc


def _state_compat(event_type: str, status: str) -> tuple[float, str]:
    st = (status or "").lower()
    if event_type == "completion":
        if st == "complete":
            return 0.2, "already complete — possible duplicate"
        return 1.0, "schedule state allows completion"
    if event_type in ("progress", "start"):
        if st == "complete":
            return 0.3, "already complete — progress on closed activity is odd"
        return 1.0, "schedule state allows progress"
    return 0.6, "unclear event type — state neutral"


def score_candidate(ev_fp: Fingerprint, afp: Fingerprint, activity, sim: dict, weights: dict) -> dict:
    disc = 1.0 if (ev_fp.discipline and ev_fp.discipline == afp.discipline) else 0.0
    loc = 1.0 if (ev_fp.location and ev_fp.location == afp.location) else 0.0
    obj = 1.0 if (ev_fp.object and ev_fp.object == afp.object) else 0.0
    size = 0.0
    size_note = ""
    if ev_fp.size and afp.size and ev_fp.size == afp.size:
        size = 1.0
        size_note = f"size {ev_fp.size}"
    elif ev_fp.tag and afp.tag and ev_fp.tag == afp.tag:
        size = 1.0
        size_note = f"tag {ev_fp.tag}"
    wbs = _wbs_match(ev_fp, afp)
    state, state_note = _state_compat(getattr(activity, "_event_type", ""), activity.status)

    signals = {
        "semantic": sim["tfidf"],
        "lexical": sim["lexical"],
        "discipline": disc,
        "location": loc,
        "object": obj,
        "size_tag": size,
        "wbs": wbs,
        "state": state,
    }
    score = round(100 * sum(weights[k] * signals[k] for k in signals), 1)

    why = []
    why.append(f"{'✓' if disc else '✗'} {afp.disp_discipline} discipline (report {ev_fp.disp_discipline})")
    why.append(f"{'✓' if loc else '✗'} {afp.disp_location} location (report {ev_fp.disp_location})")
    why.append(f"{'✓' if obj else '✗'} object: report {ev_fp.raw_object or '?'} vs {afp.raw_object or '?'}")
    why.append(f"{'✓' if size else '✗'} size/tag" + (f": {size_note}" if size_note else f" (report {ev_fp.size or ev_fp.tag or '?'})"))
    why.append(f"{'✓' if wbs >= 1.0 else ('~' if wbs > 0 else '✗')} WBS context (score {wbs})")
    why.append(f"{'✓' if state >= 1.0 else ('~' if state > 0.3 else '✗')} schedule state: {state_note}")
    why.append(f"~ text similarity: TF-IDF {sim['tfidf']}, fuzzy {sim['lexical']}")
    return {"signals": signals, "score": score, "why": why}


def weights_from_settings(settings) -> dict:
    return {
        "semantic": settings.W_SEMANTIC,
        "lexical": settings.W_LEXICAL,
        "discipline": settings.W_DISCIPLINE,
        "location": settings.W_LOCATION,
        "object": settings.W_OBJECT,
        "size_tag": settings.W_SIZE_TAG,
        "wbs": settings.W_WBS,
        "state": settings.W_STATE,
    }


def match_event(ev, activities: list, top_k: int = 3, db=None,
                project: str = "BRX-DEMO-01") -> dict:
    """Full pipeline: fingerprint -> retrieve -> score -> top-k. Offline, deterministic.

    db=None preserves exact P5 behavior (no vocabulary bonus). Passing a
    session loads active approved vocabulary for `project` and applies it
    as bounded additive evidence (see vocabulary_boost).
    """
    from ..config import settings
    from .candidate_retrieval import build_index, retrieve
    from .fingerprint import fingerprint_from_activity, fingerprint_from_event

    weights = weights_from_settings(settings)
    ev_fp = fingerprint_from_event(ev)
    act_fps = [(a.code, fingerprint_from_activity(a)) for a in activities]
    by_code = {a.code: a for a in activities}
    vectorizer, matrix, codes = build_index(act_fps)
    pre = retrieve(ev_fp, act_fps, vectorizer, matrix, codes, top_n=10)

    ranked = []
    for p in pre:
        a = by_code[p["activity_code"]]
        a._event_type = ev.event_type  # transient, for the state signal
        afp = dict(act_fps)[p["activity_code"]]
        s = score_candidate(ev_fp, afp, a, p, weights)
        ranked.append({
            "activity_code": p["activity_code"],
            "activity_name": a.name,
            "score": s["score"],
            "base_score": s["score"],
            "vocab_bonus": 0.0,
            "vocab_hits": [],
            "signals": s["signals"],
            "why": s["why"],
            "afp": afp,
        })
    if db is not None:
        from ..memory import load_active_vocabulary
        from .vocabulary_boost import apply_vocab_boost

        apply_vocab_boost(ev, ev_fp, ranked, load_active_vocabulary(db, project))
    else:
        for c in ranked:
            del c["afp"]
    ranked.sort(key=lambda d: d["score"], reverse=True)
    top = ranked[:top_k]
    for i, c in enumerate(top, 1):
        c["rank"] = i
    unmatched = not top or top[0]["score"] < UNMATCHED_FLOOR
    reason = ""
    if unmatched:
        reason = (
            "No activity passed the retrieval filters; genuinely unmatched input."
            if not top else
            f"Top score {top[0]['score']} below floor {UNMATCHED_FLOOR}; human investigation required."
        )
    from .granularity import resolve_granularity

    return {
        "candidates": top,
        "unmatched": unmatched,
        "reason": reason,
        "granularity": resolve_granularity(ev, top, unmatched, reason),
    }
