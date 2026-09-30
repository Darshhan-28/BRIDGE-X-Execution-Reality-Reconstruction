"""OpenRouter LLM adapter for field-event extraction.

Strict contract: the model must return JSON matching FieldEvent.
Malformed output -> exactly one retry -> deterministic fallback.
No API key / no network -> fallback immediately. Never raises.
"""
import json

import httpx

from ..config import settings
from .base import FieldEvent
from .fallback import parse_event_fallback

SYSTEM_PROMPT = """You extract structured field-execution events for BRIDGE-X.
Return ONLY a single JSON object, no markdown, no commentary, with keys:
event_type (completion|progress|start|status|unknown), action, object,
size (e.g. 24\\"), tag, location, discipline, event_date (YYYY-MM-DD),
progress_pct (number or null), evidence_text (quote the report).
Normalize abbreviations: erec/erected->erect, sp/spool, fdn/foundation,
CT/cable tray, cal/calibrate, R204/Rack 204->R-204. Empty string when unknown."""


class LLMError(Exception):
    pass


def _post(payload: dict) -> httpx.Response:
    return httpx.post(
        f"{settings.OPENROUTER_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=settings.OPENROUTER_TIMEOUT_S,
    )


def _payload(text: str, report_date: str, discipline_hint: str, location_hint: str,
             domain_context: str = "") -> dict:
    ctx = f"Report date: {report_date or 'unknown'}. Hints: discipline={discipline_hint or '-'}, location={location_hint or '-'}. "
    user = ctx + "Field report: " + text
    if domain_context.strip():
        user += "\n\n" + domain_context.strip()
    return {
        "model": settings.OPENROUTER_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }


def _parse_content(content: str, text: str, report_id: str) -> FieldEvent:
    s = content.strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        raise LLMError(f"non-JSON output: {e}")
    if not isinstance(data, dict):
        raise LLMError("output is not a JSON object")
    data.setdefault("evidence_text", text)
    data.setdefault("report_id", report_id)
    try:
        ev = FieldEvent(**data)
    except Exception as e:
        raise LLMError(f"schema validation failed: {e}")
    if ev.event_type not in ("completion", "progress", "start", "status", "unknown"):
        raise LLMError(f"bad event_type '{ev.event_type}'")
    ev.extractor = "llm"
    return ev


def extract_via_llm(
    text: str,
    report_id: str = "",
    report_date: str = "",
    discipline_hint: str = "",
    location_hint: str = "",
    domain_context: str = "",
    _post_fn=None,
) -> FieldEvent:
    """Try the LLM up to 2 times; raise LLMError if both fail."""
    if not settings.llm_configured:
        raise LLMError("OPENROUTER_API_KEY not configured")
    post = _post_fn or _post
    last: Exception = LLMError("no attempts made")
    for attempt in (1, 2):
        try:
            resp = post(_payload(text, report_date, discipline_hint, location_hint, domain_context))
        except Exception as e:
            last = LLMError(f"attempt {attempt}: transport error: {e}")
            continue
        if resp.status_code in (429, 500, 502, 503):
            last = LLMError(f"attempt {attempt}: HTTP {resp.status_code}")
            continue
        if resp.status_code != 200:
            raise LLMError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            last = LLMError(f"attempt {attempt}: bad response envelope: {e}")
            continue
        try:
            return _parse_content(content, text, report_id)
        except LLMError as e:
            last = LLMError(f"attempt {attempt}: {e}")
            continue
    fb = parse_event_fallback(text, report_id, report_date, discipline_hint, location_hint)
    fb.warnings.append(f"LLM failed twice ({last}); used deterministic fallback.")
    fb.extractor = "fallback"
    return fb
