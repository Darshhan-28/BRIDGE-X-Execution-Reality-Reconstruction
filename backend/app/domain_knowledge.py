"""REAL-DATA phase: provenance-aware domain knowledge retrieval.

Keyword-overlap retrieval over curated REAL_PUBLIC domain terms —
deterministic, CPU-only, no embeddings. Used strictly as LLM *context*
(terminology reference with provenance), never as matching evidence and
never as schedule/execution data. The deterministic fallback parser never
sees this context, so offline behavior is byte-identical.
"""
import json
import re

from .models import DomainTerm, SourceDocument

MAX_TERMS = 8
MIN_OVERLAP = 2


def _tokens(s: str) -> set:
    return set(t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(t) > 2)


def _source_map(db) -> dict:
    return {r.source_id: r for r in db.query(SourceDocument).all()}


def retrieve_terms(db, query_text: str, limit: int = MAX_TERMS) -> list[dict]:
    """Rank domain terms by token overlap with the query. Deterministic."""
    qtok = _tokens(query_text)
    if not qtok:
        return []
    smap = _source_map(db)
    scored = []
    for t in db.query(DomainTerm).all():
        overlap = qtok & (_tokens(t.term) | _tokens(t.context_snippet))
        # Term-phrase matches weigh more than incidental snippet words.
        phrase_hit = 3 if _tokens(t.term) <= qtok else 0
        score = len(overlap) + phrase_hit
        if score >= MIN_OVERLAP:
            src = smap.get(t.source_id)
            try:
                extra = json.loads(t.extra_json or "{}")
            except Exception:
                extra = {}
            scored.append((score, t.term, {
                "term": t.term,
                "category": t.category,
                "context_snippet": t.context_snippet,
                "section_ref": t.section_ref or "",
                "extra": extra,
                "source_id": t.source_id,
                "source_title": src.title if src else "",
                "source_url": src.source_url if src else "",
                "publisher": src.publisher if src else "",
                "publication_date": src.publication_date if src else "",
                "retrieved_at": src.retrieved_at if src else "",
                "source_type": src.source_type if src else "REAL_PUBLIC",
                "score": score,
            }))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [s for _, _, s in scored[:limit]]


def domain_context_block(db, query_text: str, limit: int = MAX_TERMS) -> tuple[str, list[dict]]:
    """Format retrieved terms as LLM context + structured provenance.

    Returns (context_text, provenance). Empty query/no hits -> ("", []).
    The block instructs the model to use terms as vocabulary reference
    only and never invent source facts.
    """
    terms = retrieve_terms(db, query_text, limit)
    if not terms:
        return "", []
    lines = ["Domain terminology reference (public Oil India documents; "
             "use ONLY as vocabulary reference for understanding field wording. "
             "Do NOT invent facts, dates, or events beyond the field report itself):"]
    for t in terms:
        lines.append(f"- {t['term']} [{t['category']}] — \"{t['context_snippet']}\" "
                     f"(Source: {t['source_title']}, {t['publisher']})")
    prov = [{"term": t["term"], "category": t["category"],
             "source_id": t["source_id"], "source_title": t["source_title"],
             "source_url": t["source_url"], "publisher": t["publisher"],
             "publication_date": t["publication_date"],
             "retrieved_at": t["retrieved_at"],
             "source_type": t.get("source_type", "REAL_PUBLIC")} for t in terms]
    return "\n".join(lines), prov


def lookup_term_provenance(db, term: str) -> list[dict]:
    """Answer 'where did this OIL-specific term come from?' — exact match."""
    out = []
    for t in db.query(DomainTerm).filter(DomainTerm.term == term).all():
        src = db.query(SourceDocument).filter(
            SourceDocument.source_id == t.source_id).first()
        try:
            extra = json.loads(t.extra_json or "{}")
        except Exception:
            extra = {}
        out.append({"term": t.term, "category": t.category,
                    "context_snippet": t.context_snippet,
                    "section_ref": t.section_ref or "", "extra": extra,
                    "source_id": t.source_id,
                    "source_title": src.title if src else "",
                    "publisher": src.publisher if src else "",
                    "source_url": src.source_url if src else "",
                    "publication_date": src.publication_date if src else "",
                    "retrieved_at": src.retrieved_at if src else "",
                    "source_type": src.source_type if src else "REAL_PUBLIC",
                    "document_type": src.document_type if src else ""})
    return out
