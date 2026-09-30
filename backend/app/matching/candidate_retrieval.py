"""Candidate retrieval: TF-IDF cosine + RapidFuzz + structured pre-filters.

No embeddings, no LLM. Structured overlap (discipline / location /
object / action) keeps genuinely related activities; a similarity floor
lets through paraphrases. Everything else is filtered before scoring.
"""
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .fingerprint import Fingerprint

TFIDF_FLOOR = 0.10
FUZZ_FLOOR = 40.0


def build_index(act_fps: list[tuple[str, Fingerprint]]):
    """Fit a TF-IDF vectorizer on activity texts. Returns (vectorizer, matrix, codes)."""
    codes = [c for c, _ in act_fps]
    corpus = [(fp.text or " ") for _, fp in act_fps]
    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(corpus)
    return vectorizer, matrix, codes


def retrieve(
    ev_fp: Fingerprint,
    act_fps: list[tuple[str, Fingerprint]],
    vectorizer,
    matrix,
    codes: list[str],
    top_n: int = 10,
) -> list[dict]:
    """Return up to top_n pre-candidates with raw similarity values."""
    ev_vec = vectorizer.transform([ev_fp.text or " "])
    cosines = cosine_similarity(ev_vec, matrix)[0]
    scored = []
    for i, (code, afp) in enumerate(act_fps):
        tfidf = float(cosines[i])
        lex = float(fuzz.token_set_ratio(ev_fp.text or " ", afp.text or " ")) / 100.0
        struct_hit = (
            (ev_fp.discipline and ev_fp.discipline == afp.discipline)
            or (ev_fp.location and ev_fp.location == afp.location)
            or (ev_fp.object and ev_fp.object == afp.object)
            or (ev_fp.action and ev_fp.action == afp.action)
        )
        if not struct_hit and tfidf < TFIDF_FLOOR and lex * 100 < FUZZ_FLOOR:
            continue
        scored.append({
            "activity_code": code,
            "tfidf": round(tfidf, 4),
            "lexical": round(lex, 4),
            "struct_hit": bool(struct_hit),
            "pre_score": round(0.5 * tfidf + 0.5 * lex, 4),
        })
    scored.sort(key=lambda d: d["pre_score"], reverse=True)
    return scored[:top_n]
