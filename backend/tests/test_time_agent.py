"""Phase 10 tests: tools, routing, citations, LLM + offline paths."""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Activity, FieldReport
from app.time_agent import answer, route
from app.time_agent_tools import (
    activities_completed_on,
    activities_started_on,
    activity_status,
    conflicts,
    delayed_activities,
    explain_link,
    unmatched_reports,
)
from seed.synthetic_project import run_seed

client = TestClient(app)


def _db():
    return SessionLocal()


# ---- tools read real database facts ----
def test_started_on_tool():
    run_seed()
    db = _db()
    try:
        out = activities_started_on(db, "2026-09-06")
        codes = {a["activity_id"] for a in out["facts"]["activities"]}
        assert {"MEC-204-072", "PIP-210-014", "MEC-204-079"} <= codes
        assert {c["id"] for c in out["citations"]} == codes
    finally:
        db.close()


def test_completed_on_tool():
    run_seed()
    db = _db()
    try:
        out = activities_completed_on(db, "2026-09-06")
        codes = {a["activity_id"] for a in out["facts"]["activities"]}
        assert {"ELE-204-051", "MEC-204-071", "CIV-204-036"} <= codes
    finally:
        db.close()


def test_delayed_tool_cites_every_row():
    run_seed()
    db = _db()
    try:
        out = delayed_activities(db)
        assert out["facts"]["count"] > 0
        assert len(out["citations"]) == out["facts"]["count"]
        assert all(a["days_overdue"] >= 0 for a in out["facts"]["activities"])
        r204 = delayed_activities(db, "R-204")
        assert all(a["location"] == "R-204" for a in r204["facts"]["activities"])
    finally:
        db.close()


def test_unmatched_tool_lists_seed_unmatched():
    run_seed()
    db = _db()
    try:
        out = unmatched_reports(db)
        ids = {r["report_id"] for r in out["facts"]["reports"]}
        assert {"DPR-2026-09-21-33", "DPR-2026-09-21-34", "DPR-2026-09-22-35"} <= ids
    finally:
        db.close()


def test_explain_link_needs_run_then_explains():
    run_seed()
    db = _db()
    try:
        assert "error" in explain_link(db, "DPR-2026-09-18-01")["facts"]
    finally:
        db.close()
    client.post("/api/matching/run", json={"report_code": "DPR-2026-09-18-01"})
    db = _db()
    try:
        out = explain_link(db, "DPR-2026-09-18-01")
        assert out["facts"]["top_activity"] == "PIP-204-017"
        assert out["facts"]["top_score"] >= 75
        assert len(out["facts"]["candidates"][0]["why"]) >= 7
        ids = {(c["type"], c["id"]) for c in out["citations"]}
        assert ("report", "DPR-2026-09-18-01") in ids and ("activity", "PIP-204-017") in ids
    finally:
        db.close()


def test_conflicts_tool_has_seeded_three():
    run_seed()
    db = _db()
    try:
        out = conflicts(db)
        assert out["facts"]["count"] == 3
        assert {c["type"] for c in out["facts"]["conflicts"]} == {"duplicate", "contradiction", "impossible"}
        assert len(out["citations"]) == 6
    finally:
        db.close()


def test_status_tool_and_missing():
    run_seed()
    db = _db()
    try:
        out = activity_status(db, "PIP-204-019")
        assert out["facts"]["activity"]["status"] == "Not Started"
        assert any(p["activity_id"] == "PIP-204-018" for p in out["facts"]["predecessors"])
        assert "error" in activity_status(db, "NOPE-1")["facts"]
    finally:
        db.close()


# ---- routing ----
def test_routing_matrix():
    assert route("What activities started on 6 Sep 2026?") == {"intent": "started", "args": {"date": "2026-09-06"}}
    assert route("Which activities completed on 2026-09-06?")["intent"] == "completed"
    assert route("Which activities are delayed?")["intent"] == "delayed"
    assert route("Show unmatched field reports.")["intent"] == "unmatched"
    r = route("Why was DPR-2026-09-18-01 linked to PIP-204-017?")
    assert r == {"intent": "explain", "args": {"report_code": "DPR-2026-09-18-01"}}
    assert route("What conflicts were detected?")["intent"] == "conflicts"
    assert route("Why is PIP-204-019 delayed?") == {"intent": "status", "args": {"code": "PIP-204-019"}}
    assert route("Tell me a joke")["intent"] == "unknown"
    assert route("Which activities were completed?")["intent"] == "unknown"  # no date -> graceful


# ---- end-to-end offline (template) ----
def test_agent_offline_answers_carry_evidence():
    run_seed()
    client.post("/api/matching/run", json={"report_code": "DPR-2026-09-18-01"})
    db = _db()
    try:
        for q, must in [
            ("What activities started on 6 Sep 2026?", "MEC-204-072"),
            ("Which activities are delayed?", "overdue"),
            ("Show unmatched field reports.", "DPR-2026-09-21-33"),
            ("Why was DPR-2026-09-18-01 linked to PIP-204-017?", "PIP-204-017"),
            ("What conflicts were detected?", "DPR-2026-09-09-22"),
        ]:
            out = answer(q, db)
            assert must in out["answer"], q
            assert out["composer"] == "template"
            assert out["citations"], q
            assert "Evidence:" in out["answer"]
    finally:
        db.close()


def test_agent_unknown_and_missing_evidence_graceful():
    run_seed()
    db = _db()
    try:
        out = answer("Tell me a joke about concrete", db)
        assert out["intent"] == "unknown" and out["citations"] == []
        assert "I can:" in out["answer"]
        out = answer("What activities started on 1 Jan 2030?", db)
        assert "0 found" in out["answer"]
    finally:
        db.close()


# ---- LLM compose path (mocked transport) ----
def test_agent_llm_success_keeps_citations(monkeypatch):
    run_seed()
    from app.llm import openrouter as oro

    monkeypatch.setattr(oro.settings, "OPENROUTER_API_KEY", "test-key")

    class _Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "Five activities started that day."}}]}

    monkeypatch.setattr(oro, "_post", lambda payload: _Resp())
    db = _db()
    try:
        out = answer("What activities started on 6 Sep 2026?", db)
        assert out["composer"] == "llm"
        assert "Five activities" in out["answer"]
        assert out["citations"]  # citations survive LLM composition
        assert "Evidence:" in out["answer"]
    finally:
        db.close()


def test_agent_llm_failure_falls_back(monkeypatch):
    run_seed()
    from app.llm import openrouter as oro

    monkeypatch.setattr(oro.settings, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(oro, "_post", lambda payload: (_ for _ in ()).throw(ConnectionError("down")))
    db = _db()
    try:
        out = answer("Which activities are delayed?", db)
        assert out["composer"] == "template" and "Delayed activities" in out["answer"]
    finally:
        db.close()


# ---- endpoint + read-only guarantee ----
def test_endpoint_and_read_only(monkeypatch):
    run_seed()
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("net!")))
    db = _db()
    try:
        n_act, n_rep = db.query(Activity).count(), db.query(FieldReport).count()
    finally:
        db.close()
    r = client.post("/api/time-agent", json={"question": "What conflicts were detected?"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "conflicts" and "duplicate" in body["answer"]
    assert client.post("/api/time-agent", json={"question": "  "}).status_code == 422
    db = _db()
    try:
        assert db.query(Activity).count() == n_act and db.query(FieldReport).count() == n_rep
    finally:
        db.close()
