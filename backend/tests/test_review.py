"""Phase 8 tests: queue buckets, 5 actions, approval gating, audit."""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Activity
from seed.synthetic_project import run_seed

client = TestClient(app)

K201 = ("Compressor K-201 erection completed at Yard-A on 14 Sep 2026.",
        "2026-09-14", "Mechanical", "Yard-A")


def _run(payload):
    r = client.post("/api/matching/run", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _ingest(text, date, disc="", loc=""):
    r = client.post("/api/reports", json={"raw_text": text, "report_date": date,
                                          "discipline": disc, "location": loc})
    assert r.status_code == 201, r.text
    return r.json()["report_code"]


def test_queue_buckets_and_filter():
    run_seed()
    for rc in ("DPR-2026-09-18-01", "DPR-2026-09-18-26", "DPR-2026-09-19-27",
               "DPR-2026-09-19-19", "DPR-2026-09-21-33"):
        _run({"report_code": rc})
    q = {i["report_code"]: i for i in client.get("/api/review/queue").json()}
    assert q["DPR-2026-09-18-01"]["bucket"] == "MEDIUM"
    assert q["DPR-2026-09-18-26"]["bucket"] == "LOW"
    assert q["DPR-2026-09-19-27"]["bucket"] == "CONFLICT"
    assert q["DPR-2026-09-19-19"]["bucket"] == "UNMATCHED"
    assert q["DPR-2026-09-21-33"]["bucket"] == "UNMATCHED"
    for item in q.values():
        assert item["decision"]["state"] == "pending"
        assert item["top_activity"] and item["margin"] is not None
    only = client.get("/api/review/queue", params={"bucket": "CONFLICT"}).json()
    assert [i["report_code"] for i in only] == ["DPR-2026-09-19-27"]


def test_approve_clean_propose_no_schedule_overwrite():
    run_seed()
    code = _ingest(*K201)
    _run({"report_code": code})
    r = client.post("/api/review/approve", json={"report_code": code, "actor": "planner-one"})
    assert r.status_code == 201, r.text
    assert r.json()["forced"] is False
    ups = client.get("/api/schedule-updates", params={"report_code": code}).json()
    assert len(ups) == 1 and ups[0]["status"] == "approved"
    assert ups[0]["after_json"].find("Complete") > 0
    # record-only: the schedule itself is untouched
    db = SessionLocal()
    try:
        a = db.query(Activity).filter(Activity.code == "MEC-YRD-077").first()
        assert a.status == "Not Started" and a.progress == 0.0
    finally:
        db.close()


def test_approve_review_needs_explicit_override():
    run_seed()
    _run({"report_code": "DPR-2026-09-18-01"})
    r = client.post("/api/review/approve", json={"report_code": "DPR-2026-09-18-01"})
    assert r.status_code == 422  # gate REVIEW: no silent auto-approval
    r = client.post("/api/review/approve", json={"report_code": "DPR-2026-09-18-01",
                                                 "force": True})  # override without reason
    assert r.status_code == 422
    r = client.post("/api/review/approve", json={"report_code": "DPR-2026-09-18-01",
                                                 "force": True, "reason": "Confirmed by phone with site engineer."})
    assert r.status_code == 201 and r.json()["forced"] is True


def test_approve_invalid_blocked_then_forced():
    run_seed()
    _run({"report_code": "DPR-2026-09-18-26"})  # welding: predecessor error
    assert client.post("/api/review/approve",
                       json={"report_code": "DPR-2026-09-18-26"}).status_code == 422
    r = client.post("/api/review/approve", json={"report_code": "DPR-2026-09-18-26",
                                                 "force": True, "reason": "Erection verified on site, backfill DPR."})
    assert r.status_code == 201


def test_double_approve_conflicts():
    run_seed()
    code = _ingest(*K201)
    _run({"report_code": code})
    assert client.post("/api/review/approve", json={"report_code": code}).status_code == 201
    assert client.post("/api/review/approve", json={"report_code": code}).status_code == 409
    r = client.post("/api/review/approve", json={"report_code": code, "force": True, "reason": "Re-confirm."})
    assert r.status_code == 201


def test_reject_requires_reason_and_writes_no_update():
    run_seed()
    _run({"report_code": "DPR-2026-09-18-26"})
    assert client.post("/api/review/reject",
                       json={"report_code": "DPR-2026-09-18-26"}).status_code == 422
    r = client.post("/api/review/reject", json={"report_code": "DPR-2026-09-18-26",
                                                "reason": "Erection not done; welding claim impossible."})
    assert r.status_code == 201
    assert client.get("/api/schedule-updates",
                      params={"report_code": "DPR-2026-09-18-26"}).json() == []
    dec = client.get("/api/review/decisions",
                     params={"report_code": "DPR-2026-09-18-26"}).json()
    assert dec[0]["decision"] == "rejected"


def test_remap_reverifies_and_catches_double_completion():
    run_seed()
    _run({"report_code": "DPR-2026-09-18-01"})  # 017 completed 18 Sep
    _run({"report_code": "DPR-2026-09-19-19"})  # ambiguous R204 group
    # remapping the 19th completion onto 017 collides with the 18th completion
    r = client.post("/api/review/remap", json={"report_code": "DPR-2026-09-19-19",
                                               "activity_code": "PIP-204-017",
                                               "reason": "Crew confirmed R-204 spool."})
    assert r.status_code == 422  # contradiction caught, override required
    r = client.post("/api/review/remap", json={"report_code": "DPR-2026-09-19-19",
                                               "activity_code": "PIP-204-017", "force": True,
                                               "reason": "18th DPR was data entry error; 19th stands."})
    assert r.status_code == 201
    assert r.json()["target"] == "PIP-204-017"
    assert client.post("/api/review/remap", json={"report_code": "DPR-2026-09-19-19",
                                                  "activity_code": "NOPE-1",
                                                  "reason": "x"}).status_code in (404, 409)


def test_mark_new_creates_proposal_not_activity():
    run_seed()
    _run({"report_code": "DPR-2026-09-21-33"})
    db = SessionLocal()
    try:
        n_before = db.query(Activity).count()
    finally:
        db.close()
    r = client.post("/api/review/mark-new", json={"report_code": "DPR-2026-09-21-33",
                                                  "reason": "Guest-house works are out of scope schedule."})
    assert r.status_code == 201
    ups = client.get("/api/schedule-updates", params={"report_code": "DPR-2026-09-21-33"}).json()
    assert ups[0]["update_type"] == "new_activity"
    db = SessionLocal()
    try:
        assert db.query(Activity).count() == n_before  # schedule table untouched
    finally:
        db.close()


def test_merge_duplicate_evidence():
    run_seed()
    text = "Busbar installation at S1 completed on 08 Sep 2026."
    a = _ingest(text, "2026-09-08", "Electrical", "S1")
    b = _ingest(text, "2026-09-08", "Electrical", "S1")
    _run({"report_code": a})
    _run({"report_code": b})
    assert client.post("/api/review/merge", json={"report_code": b,
                                                  "into_report_code": a}).status_code == 422  # reason required
    client.post("/api/review/approve", json={"report_code": a, "force": True,
                                             "reason": "Both crews saw the same busbar close-out."})
    r = client.post("/api/review/merge", json={"report_code": b, "into_report_code": a,
                                               "reason": "Same busbar, second crew DPR."})
    assert r.status_code == 201
    assert r.json()["attached_to_update"] is not None
    ups = client.get("/api/schedule-updates", params={"report_code": a}).json()
    assert b in ups[0]["after_json"]  # evidence attached to the approved update


def test_audit_trail_complete():
    run_seed()
    code = _ingest(*K201)
    _run({"report_code": code})
    client.post("/api/review/approve", json={"report_code": code, "actor": "planner-one"})
    trail = client.get("/api/audit", params={"report_code": code}).json()
    assert len(trail) == 1
    ev = trail[0]
    assert ev["actor"] == "planner-one" and ev["action"] == "approve"
    assert ev["timestamp"] and ev["activity_codes"].find("MEC-YRD-077") > 0
    assert ev["before_json"].find("Not Started") > 0 and ev["after_json"].find("Complete") > 0
    assert client.get("/api/audit", params={"action": "approve"}).json()
