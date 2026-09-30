"""Phase 9 tests: approval-only vocabulary learning + pattern aggregates."""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.memory import lookup_term
from app.models import ProjectVocabulary
from seed.synthetic_project import run_seed

client = TestClient(app)

PIPE_TEXT = "24 inch pipe erection completed at R204."


def _ingest(text=PIPE_TEXT, date="2026-09-18"):
    r = client.post("/api/reports", json={"raw_text": text, "report_date": date,
                                          "discipline": "Piping", "location": "R-204"})
    assert r.status_code == 201, r.text
    return r.json()["report_code"]


def _run(code):
    r = client.post("/api/matching/run", json={"report_code": code})
    assert r.status_code == 201, r.text
    return r.json()


def _approve(code, **kw):
    body = {"report_code": code, "force": True, "reason": "Site confirmed.", **kw}
    r = client.post("/api/review/approve", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _vocab():
    return client.get("/api/memory/vocabulary").json()


def test_approval_learns_term_mappings_with_evidence():
    run_seed()
    code = _ingest()
    top = _run(code)["candidates"][0]["activity_code"]
    assert top == "PIP-204-017"
    learned = _approve(code)["vocabulary_learned"]
    assert {"term": "pipe", "canonical_type": "object", "canonical_value": "spool"} in learned
    assert {"term": "erect pipe", "canonical_type": "phrase",
            "canonical_value": "PIP-204-017"} in learned
    rows = { (v["term"], v["canonical_type"]): v for v in _vocab() }
    assert rows[("pipe", "object")]["approval_count"] == 1
    assert rows[("pipe", "object")]["source_reports"] == [code]
    assert rows[("pipe", "object")]["discipline"] == "Piping"


def test_duplicate_approval_reinforces_no_dup_rows():
    run_seed()
    a, b = _ingest(), _ingest()
    _run(a)
    _run(b)
    _approve(a)
    _approve(b)
    rows = _vocab()
    pipe = [v for v in rows if (v["term"], v["canonical_type"]) == ("pipe", "object")]
    assert len(pipe) == 1  # no duplicate rows
    assert pipe[0]["approval_count"] == 2
    assert sorted(pipe[0]["source_reports"]) == sorted([a, b])


def test_no_learning_without_approval():
    run_seed()
    code = _ingest()
    _run(code)  # matching alone teaches nothing
    assert _vocab() == []
    client.post("/api/review/reject", json={"report_code": code, "reason": "Not credible."})
    assert _vocab() == []  # rejection teaches nothing either


def test_learning_needs_no_network(monkeypatch):
    run_seed()
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("net!")))
    code = _ingest()
    _run(code)
    assert _approve(code)["vocabulary_learned"]  # LLM never consulted


def test_remap_learns_new_phrase_mapping():
    run_seed()
    code = _ingest()
    _run(code)
    r = client.post("/api/review/remap", json={"report_code": code, "activity_code": "PIP-204-018",
                                               "force": True, "reason": "Fit-up crew did it."})
    assert r.status_code == 201, r.text
    assert {"term": "erect pipe", "canonical_type": "phrase",
            "canonical_value": "PIP-204-018"} in r.json()["vocabulary_learned"]


def test_curated_post_and_dedup():
    run_seed()
    r = client.post("/api/memory/vocabulary", json={"term": "X-ray", "canonical_type": "object",
                                                    "canonical_value": "weld", "discipline": "Piping"})
    assert r.status_code == 201 and r.json()["approval_count"] == 1
    r = client.post("/api/memory/vocabulary", json={"term": "x-ray", "canonical_type": "object",
                                                    "canonical_value": "weld", "discipline": "Piping"})
    assert r.json()["approval_count"] == 2  # normalized dedup
    assert len(_vocab()) == 1
    assert client.post("/api/memory/vocabulary", json={"term": "x", "canonical_type": "bogus",
                                                       "canonical_value": "y"}).status_code == 422
    assert client.get("/api/memory/vocabulary", params={"discipline": "Piping"}).json()
    assert not client.get("/api/memory/vocabulary", params={"discipline": "Civil"}).json()


def test_lookup_term():
    run_seed()
    code = _ingest()
    _run(code)
    _approve(code)
    db = SessionLocal()
    try:
        hits = lookup_term(db, "Pipe", "object")
        assert hits and hits[0]["canonical_value"] == "spool"
        assert lookup_term(db, "nope") == []
    finally:
        db.close()


def test_patterns_aggregation_and_synthetic_label():
    run_seed()
    p = client.get("/api/memory/patterns").json()
    assert p["synthetic"] is True and "ynthetic" in p["note"]
    assert len(p["patterns"]) == 8
    assert all(x["synthetic"] is True for x in p["patterns"])
    piping = p["by_discipline"]["Piping"]
    assert piping["executions"] == 49 and piping["avg_overrun_days"] == 1.3
    assert "Material availability" in piping["common_issues"]
    assert all(v["synthetic"] is True for v in p["by_discipline"].values())
    assert p["delays_by_discipline"]["Piping"] >= 1
    assert p["vocabulary_size"] == 0


def test_reseed_clears_learning_only_table():
    run_seed()
    code = _ingest()
    _run(code)
    _approve(code)
    assert _vocab()
    run_seed()
    assert _vocab() == []
    db = SessionLocal()
    try:
        assert db.query(ProjectVocabulary).count() == 0
    finally:
        db.close()
