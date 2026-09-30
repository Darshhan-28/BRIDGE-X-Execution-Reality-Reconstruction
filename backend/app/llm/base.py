"""BRIDGE-X structured field-event schema + extractor dispatch.

LLM is optional: without a configured key (or on any LLM failure)
extraction falls back to the deterministic local parser.
"""
from pydantic import BaseModel, Field

EVENT_TYPES = ("completion", "progress", "start", "status", "unknown")


class FieldEvent(BaseModel):
    event_type: str = "unknown"
    action: str = ""
    object: str = ""
    size: str = ""
    tag: str = ""
    location: str = ""
    discipline: str = ""
    event_date: str = ""
    progress_pct: float | None = None
    evidence_text: str = ""
    report_id: str = ""
    extractor: str = "fallback"  # llm | fallback
    warnings: list[str] = Field(default_factory=list)


def extract_field_event(
    text: str,
    report_id: str = "",
    report_date: str = "",
    discipline_hint: str = "",
    location_hint: str = "",
    prefer: str = "auto",  # auto | llm | fallback
    domain_context: str = "",
) -> FieldEvent:
    """Extract a structured event from raw field-report text.

    prefer="fallback" forces the local parser (tests, offline).
    Otherwise the OpenRouter adapter is tried when configured;
    any failure degrades to the deterministic fallback.

    domain_context is optional REAL_PUBLIC terminology reference text
    (with provenance tracked by the caller). It is passed to the LLM
    only; the fallback parser never sees it, so offline output is
    byte-identical with or without knowledge loaded.
    """
    from .fallback import parse_event_fallback

    if prefer == "fallback":
        return parse_event_fallback(text, report_id, report_date, discipline_hint, location_hint)

    from ..config import settings
    from .openrouter import extract_via_llm

    if prefer == "llm" or settings.llm_configured:
        try:
            return extract_via_llm(text, report_id, report_date, discipline_hint,
                                   location_hint, domain_context)
        except Exception as e:
            ev = parse_event_fallback(text, report_id, report_date, discipline_hint, location_hint)
            ev.warnings.append(f"LLM unavailable ({e}); used deterministic fallback.")
            return ev
    ev = parse_event_fallback(text, report_id, report_date, discipline_hint, location_hint)
    ev.warnings.append("LLM not configured; used deterministic fallback.")
    return ev


def answer_time_agent(question: str, context: dict | None = None) -> dict:
    """Phase 10: database-grounded Time Agent (delegates to app.time_agent).

    context may carry {"db": Session}. Without one, a short-lived session
    is opened. Read-only; never writes.
    """
    from ..db import SessionLocal
    from ..time_agent import answer as _answer

    db = (context or {}).get("db")
    close = False
    if db is None:
        db = SessionLocal()
        close = True
    try:
        return _answer(question, db)
    finally:
        if close:
            db.close()
