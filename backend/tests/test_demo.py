"""Phase 12: end-to-end hardening for the three live demo scenarios.

Each demo runs the REAL pipeline over HTTP (TestClient): ingest text ->
extract -> contextual match -> granularity -> verification -> gate ->
human review action -> schedule-update record -> audit trail.
No hard-coded scores; assertions pin behavior, not magic numbers.
"""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Activity
from seed.synthetic_project import run_seed

client = TestClient(app)


def _ingest(text, date="2026-09-18", disc="Piping", loc="R-204"):
    r = client.post("/api/reports", json={"raw_text": text, "report_date": date,
                                          "discipline": disc, "location": loc})
    assert r.status_code == 201, r.text
    return r.json()["report_code"]


def _match(code):
    r = client.post("/api/matching/run", json={"report_code": code})
    assert r.status_code == 201, r.text
    return r.json()


def _status(code):
    db = SessionLocal()
    try:
        return db.query(Activity).filter(Activity.code == code).first().status
    finally:
        db.close()


# ---- DEMO 1: clean spool erection -> match -> verify -> approve -> audit ----
def test_demo1_clean_match_verify_approve_audit():
    run_seed()
    # The canonical §28 demo sentence lives in seed report DPR-2026-09-18-01;
    # re-ingesting it verbatim would (correctly) trip duplicate detection,
    # so the clean demo runs on the filed report itself.
    code = "DPR-2026-09-18-01"
    m = _match(code)

    # UNDERSTAND
    assert (m["event"]["action"], m["event"]["object"], m["event"]["location"]) == ("erect", "spool", "R-204")
    # CONTEXTUAL MATCH
    assert m["candidates"][0]["activity_code"] == "PIP-204-017"
    assert m["candidates"][0]["score"] >= 75
    assert any("Piping" in w for w in m["candidates"][0]["why"])
    # VERIFY
    assert m["verification"]["valid"] is True
    assert m["granularity"]["type"] == "ONE_TO_ONE"
    # CONFIDENCE GATE: honest margin block, no silent auto-update
    assert m["verification"]["gate"]["decision"] == "REVIEW"
    assert client.post("/api/review/approve", json={"report_code": code}).status_code == 422
    # HUMAN REVIEW: explicit approval with reason
    r = client.post("/api/review/approve", json={"report_code": code, "actor": "demo-planner",
                                                 "force": True, "reason": "Demo 1: supervisor confirmed."})
    assert r.status_code == 201, r.text
    # SCHEDULE UPDATE as record only
    ups = client.get("/api/schedule-updates", params={"report_code": code}).json()
    assert len(ups) == 1 and ups[0]["activity_code"] == "PIP-204-017"
    assert ups[0]["status"] == "approved" and ups[0]["actor"] == "demo-planner"
    assert _status("PIP-204-017") == "In Progress"  # never silently overwritten
    # AUDIT TRAIL closes the loop
    trail = client.get("/api/audit", params={"report_code": code}).json()
    assert any(t["action"] == "approve" and "Complete" in t["after_json"] for t in trail)
    # MEMORY learned the phrasing
    vocab = client.get("/api/memory/vocabulary").json()
    assert any(v["term"] == "erect spool" and v["canonical_value"] == "PIP-204-017" for v in vocab)


# ---- DEMO 2: ambiguous R204 piping -> group -> human review, never auto ----
def test_demo2_ambiguous_knows_not_to_automate():
    run_seed()
    code = _ingest("R204 piping work completed.", "2026-09-19")
    m = _match(code)

    assert len(m["candidates"]) >= 2
    scores = [c["score"] for c in m["candidates"]]
    assert max(scores) < 60 and max(scores) - min(scores) < 5  # tight, unsafe cluster
    g = m["granularity"]
    assert g["type"] == "ONE_TO_MANY" and g["insufficient_evidence"] is True
    assert g["proposed_action"] == "planner_review"
    assert m["verification"]["gate"]["decision"] != "PROPOSE"
    # cannot be silently approved as an automatic update
    assert client.post("/api/review/approve", json={"report_code": code}).status_code == 422
    assert client.get("/api/schedule-updates", params={"report_code": code}).json() == []
    # visible in the review queue as pending
    q = {i["report_code"]: i for i in client.get("/api/review/queue").json()}
    assert q[code]["decision"]["state"] == "pending"


# ---- DEMO 3: welding before erection -> dependency error -> blocked ----
def test_demo3_predecessor_violation_blocked_then_overridden():
    run_seed()
    code = _ingest("24 inch welding completed at R204 on 18 Sep 2026.")
    m = _match(code)

    assert m["candidates"][0]["activity_code"] == "PIP-204-019"
    assert m["verification"]["valid"] is False
    assert any("PIP-204-018" in e for e in m["verification"]["errors"])
    assert m["verification"]["gate"]["forced"] is True
    # blocked as an automatic proposal...
    assert client.post("/api/review/approve", json={"report_code": code}).status_code == 422
    # ...but a human can still decide with a written reason, fully audited
    r = client.post("/api/review/approve", json={"report_code": code, "force": True,
                                                 "reason": "Demo 3: erection verified on site."})
    assert r.status_code == 201 and r.json()["forced"] is True
    trail = client.get("/api/audit", params={"report_code": code}).json()
    assert any(t["action"] == "approve" and "Demo 3" in t["reason"] for t in trail)
    assert _status("PIP-204-019") == "Not Started"


# ---- OFFLINE: whole demo 1 chain with network killed and a key configured ----
def test_demo1_offline_no_openrouter():
    run_seed()
    import httpx
    from app.llm import openrouter as oro

    oro.settings.OPENROUTER_API_KEY = "test-key"  # configured yet unreachable
    orig_post = httpx.post
    httpx.post = lambda *a, **k: (_ for _ in ()).throw(ConnectionError("offline"))
    try:
        code = "DPR-2026-09-18-01"
        m = _match(code)
        assert m["event"]["extractor"] == "fallback"
        assert m["candidates"][0]["activity_code"] == "PIP-204-017"
        assert m["verification"]["valid"] is True
        r = client.post("/api/time-agent", json={"question": "What conflicts were detected?"})
        assert r.status_code == 200 and "duplicate" in r.json()["answer"]
    finally:
        httpx.post = orig_post
        oro.settings.OPENROUTER_API_KEY = ""
