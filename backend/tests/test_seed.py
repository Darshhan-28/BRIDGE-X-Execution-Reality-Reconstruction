"""Phase 2 tests: synthetic project counts, coverage, demo-critical records."""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from seed.synthetic_project import run_seed

client = TestClient(app)

EXPECTED_CATEGORIES = {
    "clean", "mismatch", "abbreviation", "incomplete", "ambiguous",
    "duplicate", "contradiction", "partial", "unmatched",
}


def test_seed_counts():
    counts = run_seed()
    assert counts["projects"] == 1
    assert counts["wbs_nodes"] == 12
    assert counts["activities"] == 55
    assert counts["relationships"] >= 15
    assert counts["reports"] >= 30
    assert counts["execution_patterns"] > 0
    assert counts["conflicts"] >= 3


def test_discipline_coverage():
    run_seed()
    db = SessionLocal()
    try:
        from app.models import Activity

        discs = {d for (d,) in db.query(Activity.discipline).distinct().all()}
        assert {"Piping", "Civil", "Electrical", "Mechanical", "Instrumentation"} <= discs
        n_piping = db.query(Activity).filter(Activity.discipline == "Piping").count()
        assert n_piping >= 10
    finally:
        db.close()


def test_demo_activities_and_chain():
    r = client.get("/api/activities/PIP-204-017")
    assert r.status_code == 200
    assert r.json()["location"] == "R-204"
    chain = client.get("/api/activities/PIP-204-019").json()
    assert "PIP-204-018" in chain["predecessors"]  # fit-up before welding
    assert "PIP-204-020" in chain["successors"]  # welding before NDT


def test_report_categories_covered():
    r = client.get("/api/reports").json()
    cats = {x["category"] for x in r}
    assert EXPECTED_CATEGORIES <= cats
    unmatched = [x for x in r if x["category"] == "unmatched"]
    assert len(unmatched) >= 2
    assert all(x["linked_activity_code"] is None for x in unmatched)


def test_dashboard_counts_match_seed():
    counts = run_seed()
    dash = client.get("/api/dashboard").json()
    assert dash["synthetic"] is True
    for k in ("projects", "wbs_nodes", "activities", "relationships", "reports", "conflicts"):
        assert dash[k] == counts[k], k
