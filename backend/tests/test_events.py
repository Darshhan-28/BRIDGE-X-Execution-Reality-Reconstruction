"""Phase 4 tests: fallback extraction, mocked LLM paths, demo reports, endpoint."""
import json

import pytest
from fastapi.testclient import TestClient

from app.llm import openrouter as oro
from app.llm.base import extract_field_event
from app.llm.fallback import parse_event_fallback
from app.main import app
from seed.synthetic_project import run_seed

client = TestClient(app)

DEMO_CLEAN = "24 inch spool erection completed at R-204 on 18 Sep 2026."


class _Resp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _llm_payload(**kw):
    base = {
        "event_type": "completion", "action": "erect", "object": "spool",
        "size": '24"', "tag": "", "location": "R-204", "discipline": "Piping",
        "event_date": "2026-09-18", "progress_pct": 100.0,
        "evidence_text": DEMO_CLEAN, "report_id": "DPR-2026-09-18-01",
        "extractor": "llm", "warnings": [],
    }
    base.update(kw)
    return {"choices": [{"message": {"content": json.dumps(base)}}]}


# ---- fallback: Phase 2 demo reports ----
def test_fallback_demo_clean():
    ev = parse_event_fallback(DEMO_CLEAN, "DPR-2026-09-18-01", "2026-09-18", "Piping", "R-204")
    assert (ev.action, ev.object, ev.size) == ("erect", "spool", '24"')
    assert (ev.location, ev.discipline) == ("R-204", "Piping")
    assert ev.event_type == "completion" and ev.progress_pct == 100.0
    assert ev.event_date == "2026-09-18"
    assert ev.evidence_text == DEMO_CLEAN and ev.report_id == "DPR-2026-09-18-01"


def test_fallback_terminology_mismatch():
    ev = parse_event_fallback(
        "Yesterday night team completed pipe erection of 24 inch line near R204.",
        "DPR-2026-09-18-06", "2026-09-18",
    )
    assert ev.action == "erect" and ev.size == '24"' and ev.location == "R-204"
    assert ev.event_type == "completion"
    assert ev.event_date == "2026-09-17"  # yesterday resolved against report_date


def test_fallback_abbreviation():
    ev = parse_event_fallback("Erec. of 24in sp. R204 done.", "DPR-2026-09-18-11", "2026-09-18")
    assert (ev.action, ev.object, ev.size, ev.location) == ("erect", "spool", '24"', "R-204")
    assert ev.event_type == "completion"


def test_fallback_partial_progress():
    ev = parse_event_fallback(
        "24 inch spool erection at R-204 60 percent complete.", "DPR-2026-09-11-30", "2026-09-11"
    )
    assert ev.event_type == "progress" and ev.progress_pct == 60.0


def test_fallback_ambiguous_warns():
    ev = parse_event_fallback("R204 piping work completed.", "DPR-2026-09-19-19", "2026-09-19")
    assert ev.event_type == "completion"
    assert any("object" in w for w in ev.warnings)


def test_fallback_start_and_negated_status():
    assert parse_event_fallback("24 inch welding at R-204 started on 19 Sep 2026.").event_type == "start"
    ev = parse_event_fallback("Fit-up at R-210 not yet started as of 12 Sep.")
    assert ev.event_type == "status" and ev.progress_pct == 0.0


# ---- LLM paths (fully offline via monkeypatched transport) ----
def test_llm_success_validated(monkeypatch):
    monkeypatch.setattr(oro.settings, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(oro, "_post", lambda payload: _Resp(200, _llm_payload()))
    ev = extract_field_event(DEMO_CLEAN, "DPR-2026-09-18-01", "2026-09-18")
    assert ev.extractor == "llm"
    assert (ev.action, ev.object, ev.location) == ("erect", "spool", "R-204")


def test_llm_malformed_twice_then_fallback(monkeypatch):
    monkeypatch.setattr(oro.settings, "OPENROUTER_API_KEY", "test-key")
    calls = []
    monkeypatch.setattr(
        oro, "_post", lambda payload: (calls.append(1), _Resp(200, {"choices": [{"message": {"content": "NOT JSON"}}]}))[1]
    )
    ev = extract_field_event(DEMO_CLEAN, "DPR-2026-09-18-01", "2026-09-18")
    assert ev.extractor == "fallback"
    assert len(calls) == 2  # exactly one retry
    assert any("twice" in w for w in ev.warnings)
    assert ev.action == "erect"  # fallback still understood the report


def test_llm_rate_limit_then_fallback(monkeypatch):
    monkeypatch.setattr(oro.settings, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(oro, "_post", lambda payload: _Resp(429, None, "rate limited"))
    ev = extract_field_event(DEMO_CLEAN, prefer="llm")
    assert ev.extractor == "fallback" and ev.action == "erect"


def test_no_key_no_network(monkeypatch):
    monkeypatch.setattr(oro.settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(oro, "_post", lambda payload: (_ for _ in ()).throw(AssertionError("network used!")))
    ev = extract_field_event(DEMO_CLEAN, "DPR-2026-09-18-01", "2026-09-18")
    assert ev.extractor == "fallback"
    assert any("not configured" in w for w in ev.warnings)


# ---- endpoint ----
def test_extract_endpoint_persists():
    run_seed()
    r = client.post("/api/events/extract", json={"report_code": "DPR-2026-09-18-01", "prefer": "fallback"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["event"]["action"] == "erect"
    assert body["event"]["report_id"] == "DPR-2026-09-18-01"
    got = client.get("/api/events", params={"report_code": "DPR-2026-09-18-01"}).json()
    assert len(got) == 1 and got[0]["extractor"] == "fallback"


def test_extract_endpoint_inline_and_404():
    run_seed()
    r = client.post("/api/events/extract", json={"raw_text": DEMO_CLEAN, "prefer": "fallback"})
    assert r.status_code == 201
    assert client.post("/api/events/extract", json={"report_code": "NOPE-01"}).status_code == 404
    assert client.post("/api/events/extract", json={"raw_text": "  "}).status_code == 422
