"""REAL_PUBLIC OIL knowledge tests: provenance, ingestion, retrieval,
source_type separation, LLM/fallback provenance. No fabricated OIL data;
all assertions use the curated seed + deterministic paths.
"""
import json

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.domain_knowledge import (
    domain_context_block,
    lookup_term_provenance,
    retrieve_terms,
)
from app.llm import openrouter as oro
from app.llm.base import extract_field_event
from app.main import app
from app.models import DomainTerm, FieldReport, SourceDocument
from seed.oil_public_data import SOURCES, TERMS, load_oil_knowledge
from seed.synthetic_project import run_seed

client = TestClient(app)


class _Resp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _reset():
    run_seed()
    load_oil_knowledge()
    return SessionLocal()


def test_sources_have_full_provenance():
    db = _reset()
    try:
        rows = db.query(SourceDocument).all()
        assert len(rows) == len(SOURCES) == 4
        for r in rows:
            assert r.source_type == "REAL_PUBLIC"
            assert r.title and r.publisher == "Oil India Limited" or "Oil India" in r.publisher
            assert r.source_url.startswith("https://www.oil-india.com/")
            assert r.retrieved_at == "2026-09-22"
            assert r.document_type
            assert r.local_file.startswith("backend/data/oil_public/")
            # checksum filled when local file present
            assert r.checksum.startswith("sha256:") or r.checksum == ""
        ids = {r.source_id for r in rows}
        assert ids == {s["source_id"] for s in SOURCES}
    finally:
        db.close()


def test_terms_link_to_sources_no_dpr_content():
    db = _reset()
    try:
        assert db.query(DomainTerm).count() == len(TERMS) == 49
        src_ids = {r.source_id for r in db.query(SourceDocument).all()}
        for t in db.query(DomainTerm).all():
            assert t.source_id in src_ids
            assert t.term and t.context_snippet and t.category
            # terms are terminology context, never DPR/schedule/progress records
            low = (t.term + " " + t.context_snippet).lower()
            assert "dpr-2026" not in low
    finally:
        db.close()


def test_ingestion_idempotent_no_dpr_invented():
    db = _reset()
    try:
        before_reports = db.query(FieldReport).count()
        assert before_reports == 35  # synthetic fixtures intact
        first = load_oil_knowledge(db)
        second = load_oil_knowledge(db)
        assert second["new_sources"] == 0 and second["new_terms"] == 0
        assert db.query(FieldReport).count() == before_reports
        assert db.query(SourceDocument).count() == 4
        assert db.query(DomainTerm).count() == 49
        assert first["sources"] == 4 and first["terms"] == 49
    finally:
        db.close()


def test_source_type_separation():
    db = _reset()
    try:
        # synthetic fixtures stay SYNTHETIC
        synth = db.query(FieldReport).filter(FieldReport.report_code.like("DPR-%")).all()
        assert len(synth) == 35
        assert {r.source_type for r in synth} == {"SYNTHETIC"}
        # no field report may claim REAL_PUBLIC (real docs live in source_documents only)
        assert db.query(FieldReport).filter(FieldReport.source_type == "REAL_PUBLIC").count() == 0
        # sources are all REAL_PUBLIC
        assert {r.source_type for r in db.query(SourceDocument).all()} == {"REAL_PUBLIC"}
    finally:
        db.close()
    # ingested user evidence arrives as USER_PROVIDED
    run_seed()
    load_oil_knowledge()
    r = client.post("/api/reports", json={"raw_text": "Pump P-204A erected at PH1.", "report_date": "2026-09-20"})
    assert r.status_code == 201, r.text
    assert r.json()["source_type"] == "USER_PROVIDED"


def test_retrieval_returns_provenance():
    db = _reset()
    try:
        hits = retrieve_terms(db, "trunk pipeline pumping station 1247 km")
        assert hits, "expected overlap hits for midstream wording"
        for h in hits:
            assert h["source_type"] == "REAL_PUBLIC"
            assert h["source_url"].startswith("https://www.oil-india.com/")
            assert h["source_title"] and h["publisher"]
        assert retrieve_terms(db, "") == []
        assert retrieve_terms(db, "zzzqqq nnnmmm") == []
        ctx, prov = domain_context_block(db, "trunk pipeline pumping station")
        assert "Domain terminology reference" in ctx and "Do NOT invent" in ctx
        assert prov and prov[0]["source_type"] == "REAL_PUBLIC"
        empty_ctx, empty_prov = domain_context_block(db, "")
        assert empty_ctx == "" and empty_prov == []
    finally:
        db.close()


def test_lookup_provenance_exact():
    db = _reset()
    try:
        out = lookup_term_provenance(db, "trunk pipeline")
        assert len(out) == 1
        assert out[0]["source_id"] == "OIL-MIDSTREAM-20260325"
        assert out[0]["source_type"] == "REAL_PUBLIC"
        assert "oil-india.com" in out[0]["source_url"]
        assert lookup_term_provenance(db, "no such term xyz") == []
    finally:
        db.close()


def test_fallback_ignores_domain_context():
    a = extract_field_event(
        "24 inch spool erection completed at R-204 on 18 Sep 2026.",
        report_id="X", report_date="2026-09-18", prefer="fallback")
    b = extract_field_event(
        "24 inch spool erection completed at R-204 on 18 Sep 2026.",
        report_id="X", report_date="2026-09-18", prefer="fallback",
        domain_context="pumping station trunk pipeline reference text")
    assert a.extractor == b.extractor == "fallback"
    assert a.model_dump(exclude={"warnings"}) == b.model_dump(exclude={"warnings"})


def test_llm_success_identified(monkeypatch):
    monkeypatch.setattr(oro.settings, "OPENROUTER_API_KEY", "test-key")
    payload = {"choices": [{"message": {"content": json.dumps({
        "event_type": "completion", "action": "erect", "object": "spool",
        "size": '24"', "tag": "", "location": "R-204", "discipline": "Piping",
        "event_date": "2026-09-18", "progress_pct": 100.0,
        "evidence_text": "24 inch spool erection completed at R-204.",
        "report_id": "X", "extractor": "llm", "warnings": []})}}]}
    seen = {}

    def _fake_post(p):
        seen.update(p)
        return _Resp(200, payload)

    monkeypatch.setattr(oro, "_post", _fake_post)
    ev = extract_field_event("24 inch spool erection completed at R-204.", prefer="llm")
    assert seen.get("model") == oro.settings.OPENROUTER_MODEL  # configured model used
    assert ev.extractor == "llm"
    assert (ev.action, ev.object, ev.event_type) == ("erect", "spool", "completion")


def test_llm_failure_falls_back_with_provenance(monkeypatch):
    monkeypatch.setattr(oro.settings, "OPENROUTER_API_KEY", "test-key")
    calls = []
    monkeypatch.setattr(
        oro, "_post",
        lambda p: (calls.append(1), _Resp(200, {"choices": [{"message": {"content": "NOT JSON"}}]}))[1])
    ev = extract_field_event("24 inch spool erection completed at R-204.", prefer="llm")
    assert ev.extractor == "fallback"
    assert len(calls) == 2
    assert any("fallback" in w.lower() for w in ev.warnings)


def test_unavailable_api_no_network(monkeypatch):
    monkeypatch.setattr(oro.settings, "OPENROUTER_API_KEY", "")

    def _boom(payload):
        raise AssertionError("network used!")

    monkeypatch.setattr(oro, "_post", _boom)
    ev = extract_field_event("24 inch spool erection completed at R-204.", prefer="auto")
    assert ev.extractor == "fallback"
    assert any("not configured" in w for w in ev.warnings)


def test_knowledge_endpoints_and_promote_guard():
    run_seed()
    load_oil_knowledge()
    srcs = client.get("/api/knowledge/sources").json()
    assert len(srcs) == 4 and all(s["source_type"] == "REAL_PUBLIC" for s in srcs)
    terms = client.get("/api/knowledge/terms", params={"q": "pumping station trunk pipeline"}).json()
    assert terms and all("source_id" in t for t in terms)
    look = client.get("/api/knowledge/lookup", params={"q": "trunk pipeline"}).json()
    assert len(look) == 1 and look[0]["source_url"].startswith("https://www.oil-india.com/")
    assert client.get("/api/knowledge/lookup", params={"q": "  "}).status_code == 422
    # promote requires explicit human reason; unpromoted terms never leak into vocabulary
    vocab_before = {v["term"] for v in client.get("/api/memory/vocabulary").json()}
    assert "trunk pipeline" not in vocab_before
    assert client.post("/api/knowledge/promote", json={"term_id": 1}).status_code == 422
    r = client.post("/api/knowledge/promote", json={
        "term_id": 1, "canonical_type": "object",
        "canonical_value": "pipeline", "actor": "planner", "reason": "test provenance"})
    assert r.status_code == 201, r.text
    assert client.get("/api/memory/vocabulary").json()
