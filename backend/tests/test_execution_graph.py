"""P15: execution-graph neighborhood + dependency-chain context.

Read-only, deterministic, no LLM. P7 remains authoritative; tests assert
the graph agrees with P7 rather than duplicating or overriding it.
"""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.execution_graph import analyze
from app.main import app
from app.models import Activity, ActivityRelationship
from seed.synthetic_project import run_seed

client = TestClient(app)


def _db():
    return SessionLocal()


def _graph(code, **params):
    r = client.get(f"/api/graph/{code}", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_normal_dependency_chain():
    run_seed()
    g = _graph("PIP-204-018", depth=1)
    assert [p["code"] for p in g["predecessors"]] == ["PIP-204-017"]
    assert [s["code"] for s in g["successors"]] == ["PIP-204-019"]
    assert [n["code"] for n in g["backbone"]] == ["PIP-204-017", "PIP-204-018", "PIP-204-019"]
    assert all(p["rel_type"] == "FS" for p in g["predecessors"] + g["successors"])
    assert g["predecessors"][0]["status"] == "In Progress"
    assert g["predecessors"][0]["planned_finish"] == "2026-09-12"
    assert g["warnings"] == []  # 017 in progress is not a stored-state violation


def test_incomplete_predecessor_judge_readable():
    run_seed()
    client.post("/api/matching/run", json={"report_code": "DPR-2026-09-18-26"})
    g = _graph("PIP-204-019", depth=2, report_code="DPR-2026-09-18-26")
    hit = next(w for w in g["warnings"] if w["kind"] == "blocked_predecessor")
    assert hit["activities"] == ["PIP-204-019", "PIP-204-018"]
    assert hit["rel_type"] == "FS"
    assert hit["evidence"]["PIP-204-018"]["status"] == "Not Started"
    for fragment in ("Reported:", "PIP-204-019", "Required predecessor: PIP-204-018",
                     "Current predecessor state: Not Started", "REVIEW"):
        assert fragment in hit["message"]
    chain = next(w for w in g["warnings"] if w["kind"] == "blocked_chain")
    assert "PIP-204-018" in chain["activities"]


def test_invalid_execution_order_early_start():
    run_seed()
    client.post("/api/matching/run", json={"report_code": "DPR-2026-09-19-27"})
    g = _graph("PIP-204-019", report_code="DPR-2026-09-19-27")
    hit = next(w for w in g["warnings"] if w["kind"] == "early_start")
    assert hit["activities"] == ["PIP-204-019", "PIP-204-018"]
    assert "PIP-204-018" in hit["message"] and "REVIEW" in hit["message"]


def test_successor_context_inverted_order():
    run_seed()
    db = _db()
    try:
        db.query(Activity).filter(Activity.code == "MEC-204-073").update({"status": "Complete"})
        db.flush()
        out = analyze(db, "MEC-204-072")
        hit = next(w for w in out["warnings"] if w["kind"] == "successor_ahead")
        assert hit["activities"] == ["MEC-204-072", "MEC-204-073"]
        assert hit["rel_type"] == "FS"
        db.rollback()
    finally:
        db.close()


def test_isolated_activity():
    run_seed()
    g = _graph("INS-CR1-088")
    assert g["predecessors"] == [] and g["successors"] == []
    assert [n["code"] for n in g["backbone"]] == ["INS-CR1-088"]
    assert g["warnings"] == []
    assert any("isolated" in r for r in g["reasons"])


def test_multiple_predecessors():
    run_seed()
    g = _graph("MEC-204-073")
    assert {p["code"] for p in g["predecessors"]} == {"MEC-204-071", "MEC-204-072"}
    states = {p["code"]: p["status"] for p in g["predecessors"]}
    assert states == {"MEC-204-071": "Complete", "MEC-204-072": "In Progress"}


def test_graph_project_isolation_and_depth():
    run_seed()
    assert client.get("/api/graph/NOPE-1").status_code == 404
    assert client.get("/api/graph/PIP-204-019", params={"report_code": "NOPE"}).status_code == 404
    g = _graph("PIP-204-019", depth=9)
    assert g["depth"] == 2  # clamped, never unbounded
    db = _db()
    try:
        known = {a.code for a in db.query(Activity).all()}
    finally:
        db.close()
    for n in g["backbone"] + g["predecessors"] + g["successors"] + g["second_level"]:
        assert n["code"] in known  # nothing outside the project schedule


def test_consistency_with_p7_verification():
    run_seed()
    bad = client.post("/api/matching/run", json={"report_code": "DPR-2026-09-18-26"}).json()
    assert bad["verification"]["valid"] is False  # P7 authoritative
    g = _graph("PIP-204-019", report_code="DPR-2026-09-18-26")
    assert any(w["kind"] == "blocked_predecessor" and "PIP-204-018" in w["activities"]
               for w in g["warnings"])  # graph agrees, citing the same evidence
    assert g["latest_review"]["decision"] == "REVIEW"  # references, not overrides
    good = client.post("/api/matching/run", json={"report_code": "DPR-2026-09-18-01"}).json()
    assert good["verification"]["valid"] is True
    g2 = _graph("PIP-204-017", report_code="DPR-2026-09-18-01")
    assert not [w for w in g2["warnings"] if w["kind"] == "blocked_predecessor"]


def test_graph_never_mutates_schedule():
    run_seed()
    db = _db()
    try:
        before = (db.query(Activity).count(), db.query(ActivityRelationship).count(),
                  db.query(Activity).filter(Activity.code == "PIP-204-019").first().status)
    finally:
        db.close()
    for code in ("PIP-204-019", "MEC-204-073", "INS-CR1-088", "PIP-204-017"):
        _graph(code, depth=2)
    db = _db()
    try:
        after = (db.query(Activity).count(), db.query(ActivityRelationship).count(),
                 db.query(Activity).filter(Activity.code == "PIP-204-019").first().status)
    finally:
        db.close()
    assert before == after
