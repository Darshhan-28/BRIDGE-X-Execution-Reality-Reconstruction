"""P16: explainable execution-risk intelligence — advisory, read-only.

No probabilities, no predictions, no mutations. Every assertion pins
evidence-backed behavior: signals appear iff their evidence exists.
"""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import (
    Activity,
    ActivityRelationship,
    AuditEvent,
    Conflict,
    ExecutionHistory,
    FieldReport,
    MatchCandidate,
    Project,
    ProjectVocabulary,
    ReviewDecision,
    ScheduleUpdate,
    VerificationResult,
    WbsNode,
)
from seed.synthetic_project import run_seed

client = TestClient(app)
TABLES = [Activity, ActivityRelationship, FieldReport, ExecutionHistory, Conflict,
          MatchCandidate, VerificationResult, ScheduleUpdate, ReviewDecision,
          AuditEvent, ProjectVocabulary, Project, WbsNode]


def _counts():
    db = SessionLocal()
    try:
        return [db.query(t).count() for t in TABLES]
    finally:
        db.close()


def _board(**params):
    r = client.get("/api/risk/project/BRX-DEMO-01", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _by_id(board, sid):
    return next(i for i in board["items"] if i["subject_id"] == sid)


def test_normal_activity():
    run_seed()
    a = client.get("/api/risk/activity/PIP-YRD-015").json()
    assert a["priority"] == "NORMAL" and a["signals"] == []
    assert a["status"] == "Complete" and a["planned_finish"] == "2026-09-04"
    assert "routine monitoring" in a["reasons"][-1]


def test_delayed_activity_variance():
    run_seed()
    a = client.get("/api/risk/activity/CIV-204-033").json()
    assert "SCHEDULE_VARIANCE" in a["signals"]
    assert a["priority"] in ("WATCH", "ATTENTION")
    assert any("past planned finish" in r for r in a["reasons"])
    assert a["planned_finish"] != ""


def test_dependency_risk_structural():
    run_seed()  # no match runs needed: chain evidence is structural
    a = client.get("/api/risk/activity/PIP-204-019").json()
    assert "DEPENDENCY_RISK" in a["signals"]
    det = next(d for d in a["signal_details"] if d["signal"] == "DEPENDENCY_RISK")
    assert "PIP-204-018" in det["evidence"]["activities"]
    assert det["evidence"]["rel_type"] == "FS"


def test_verification_conflict_after_run():
    run_seed()
    client.post("/api/matching/run", json={"report_code": "DPR-2026-09-18-26"})
    a = client.get("/api/risk/activity/PIP-204-019").json()
    assert "VERIFICATION_CONFLICT" in a["signals"]
    det = next(d for d in a["signal_details"] if d["signal"] == "VERIFICATION_CONFLICT")
    assert det["evidence"]["report"] == "DPR-2026-09-18-26"
    assert "PIP-204-018" in det["reason"]
    assert a["priority"] == "ATTENTION"


def test_unmatched_evidence_without_runs():
    run_seed()
    b = _board()
    unlinked = [i for i in b["items"] if i["subject_type"] == "report"]
    assert {i["subject_id"] for i in unlinked} >= {
        "DPR-2026-09-21-33", "DPR-2026-09-21-34", "DPR-2026-09-22-35"}
    assert all(i["priority"] == "WATCH" and i["signals"] == ["UNMATCHED_EXECUTION"]
               for i in unlinked)


def test_contradiction_items_without_runs():
    run_seed()
    b = _board()
    cons = [i for i in b["items"] if "CONTRADICTION" in i["signals"]]
    assert len(cons) == 4  # 3 conflict rows + PIP-210-011 named as evidence
    rows = {i["subject_id"] for i in cons if i["subject_type"] == "conflict"}
    assert len(rows) == 3
    assert all(i["priority"] == "ATTENTION" for i in cons)
    ev_ids = {e for i in cons for d in i["signal_details"]
              for e in (d["evidence"].get("evidence_a", ""), d["evidence"].get("evidence_b", ""))
              if e}
    assert {"DPR-2026-09-18-26", "DPR-2026-09-19-27"} <= ev_ids


def test_multiple_simultaneous_signals():
    run_seed()
    client.post("/api/matching/run", json={"report_code": "DPR-2026-09-18-26"})
    a = client.get("/api/risk/activity/PIP-204-019").json()
    assert {"SCHEDULE_VARIANCE", "DEPENDENCY_RISK", "VERIFICATION_CONFLICT"} <= set(a["signals"])
    assert a["priority"] == "ATTENTION" and a["attention_score"] >= 4
    assert a["attention_score"] <= 10  # bounded tally, never a probability


def test_evidence_reason_generation_complete():
    run_seed()
    b = _board()
    assert b["project_code"] == "BRX-DEMO-01" and b["item_count"] == len(b["items"])
    for i in b["items"]:
        assert i["subject_id"] and i["name"] and i["status"] and i["priority"]
        assert i["reasons"] and all(isinstance(r, str) and r for r in i["reasons"])
        assert "chance" not in " ".join(i["reasons"]).lower()
        assert "probability" not in " ".join(i["reasons"]).lower()
    assert "not a prediction" in b["note"]


def test_project_isolation():
    run_seed()
    assert client.get("/api/risk/project/NOPE").status_code == 404
    assert client.get("/api/risk/activity/NOPE-1").status_code == 404
    b = _board()
    db = SessionLocal()
    try:
        proj = db.query(Project).filter(Project.code == "BRX-DEMO-01").first()
        wbs = {w.code for w in db.query(WbsNode).filter(WbsNode.project_id == proj.id).all()}
        codes = {a.code for a in db.query(Activity).all()}
    finally:
        db.close()
    for i in b["items"]:
        if i["subject_type"] == "activity":
            assert i["subject_id"] in codes
    assert wbs  # scoping map is non-trivial


def test_level_filter():
    run_seed()
    b = _board(level="ATTENTION")
    assert b["items"] and all(i["priority"] == "ATTENTION" for i in b["items"])


def test_read_only_no_mutation():
    run_seed()
    client.post("/api/matching/run", json={"report_code": "DPR-2026-09-18-26"})
    before = _counts()
    db = SessionLocal()
    try:
        status_before = db.query(Activity).filter(
            Activity.code == "PIP-204-019").first().status
    finally:
        db.close()
    _board()
    client.get("/api/risk/activity/PIP-204-019")
    _board(level="WATCH")
    after = _counts()
    db = SessionLocal()
    try:
        status_after = db.query(Activity).filter(
            Activity.code == "PIP-204-019").first().status
    finally:
        db.close()
    assert before == after and status_before == status_after == "Not Started"


def test_consistency_with_p7_and_p15():
    run_seed()
    m = client.post("/api/matching/run", json={"report_code": "DPR-2026-09-18-26"}).json()
    assert m["verification"]["valid"] is False  # P7 authoritative
    g = client.get("/api/graph/PIP-204-019",
                   params={"report_code": "DPR-2026-09-18-26"}).json()
    a = client.get("/api/risk/activity/PIP-204-019").json()
    graph_codes = {c for w in g["warnings"] if w["kind"] == "blocked_chain"
                   for c in w["activities"]}
    risk_codes = {c for d in a["signal_details"] if d["signal"] == "DEPENDENCY_RISK"
                  for c in d["evidence"]["activities"]}
    assert graph_codes and graph_codes <= risk_codes  # same evidence, same codes
    assert any("PIP-204-018" in r for r in a["reasons"])
