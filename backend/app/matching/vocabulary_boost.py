"""P14: learned project vocabulary as bounded additive matching evidence.

Design contract (frozen P5/P7 behavior preserved):
- The 8-signal weighted base score is computed EXACTLY as before and kept
  as `base_score` for audit. Vocabulary never alters signals or weights.
- Learned mappings contribute a SEPARATE bounded bonus:
  object hit +2.0, action hit +1.5, phrase->activity hit +3.0,
  capped at +5.0 per candidate. `score = base_score + vocab_bonus`.
- Ranking, floor, margin, granularity and gate consume the decision
  `score` through their UNCHANGED code paths — vocabulary flows THROUGH
  the gates, never around them.
- Only rows from `load_active_vocabulary` (active, approval_count > 0,
  correct project) can fire. No LLM, no unreviewed data involved.
- Every hit carries provenance (approval count + source reports) and is
  rendered into WHY, so evaluators see exactly what the memory added.
"""
from .fingerprint import Fingerprint

VOCAB_W_OBJECT = 2.0
VOCAB_W_ACTION = 1.5
VOCAB_W_PHRASE = 3.0
VOCAB_MAX_BONUS = 5.0
MAX_SOURCES_SHOWN = 3


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def event_phrase(ev) -> str:
    return _norm(f"{ev.action or ''} {ev.object or ''}")


def hits_for_candidate(ev, ev_fp: Fingerprint, code: str, afp: Fingerprint,
                       vocab: list[dict]) -> list[dict]:
    """Learned-mapping hits for one candidate, with provenance."""
    hits = []
    raw_obj, raw_act = _norm(ev.object), _norm(ev.action)
    phrase = event_phrase(ev)
    for row in vocab:
        ctype = row.get("canonical_type", "")
        term = _norm(row.get("term", ""))
        value = (row.get("canonical_value", "") or "").strip()
        if not term or not value:
            continue
        weight = 0.0
        if ctype == "object" and raw_obj and term == raw_obj \
                and value.lower() == (afp.object or ""):
            weight = VOCAB_W_OBJECT
        elif ctype == "action" and raw_act and term == raw_act \
                and value.lower() == (afp.action or ""):
            weight = VOCAB_W_ACTION
        elif ctype == "phrase" and phrase and term == phrase and value == code:
            weight = VOCAB_W_PHRASE
        if weight > 0:
            hits.append({
                "term": term,
                "canonical_type": ctype,
                "canonical_value": value,
                "weight": weight,
                "approval_count": row.get("approval_count", 0),
                "source_reports": list(row.get("source_reports", []) or []),
            })
    return hits


def why_line(hit: dict) -> str:
    srcs = ", ".join((hit.get("source_reports", []) or [])[:MAX_SOURCES_SHOWN]) or "curated"
    return (f"[vocab] learned '{hit['term']}'->'{hit['canonical_value']}' "
            f"(approved x{hit.get('approval_count', 0)}, {srcs}) +{hit['weight']}")


def apply_vocab_boost(ev, ev_fp: Fingerprint,
                      scored: list[dict], vocab: list[dict]) -> list[dict]:
    """Attach base_score/vocab_bonus/vocab_hits + WHY lines in place.

    `scored` entries must carry activity_code, score (base), why, and afp.
    Returns the same list for chaining.
    """
    for c in scored:
        hits = hits_for_candidate(ev, ev_fp, c["activity_code"], c["afp"], vocab)
        bonus = round(min(VOCAB_MAX_BONUS, sum(h["weight"] for h in hits)), 1)
        c["base_score"] = c["score"]
        c["vocab_bonus"] = bonus
        c["vocab_hits"] = hits
        c["score"] = round(c["score"] + bonus, 1)
        for h in hits:
            c["why"].append(why_line(h))
        del c["afp"]
    return scored
