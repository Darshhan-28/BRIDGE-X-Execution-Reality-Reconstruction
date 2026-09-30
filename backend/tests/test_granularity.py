"""Phase 6 tests: ONE_TO_ONE / ONE_TO_MANY / PARTIAL / NEW_UNPLANNED."""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.llm.base import extract_field_event
from app.main import app
from app.matching.granularity import TYPES, resolve_granularity
from app.matching.scorer import match_event
from app.models import Activity
from seed.synthetic_project import run_seed

client = TestClient(app)


def _acts():
    db = SessionLocal()
    try:
        return db.query(Activity).order_by(Activity.code).all()
    finally:
        db.close()


def _run(text, date, disc="", loc=""):
    ev = extract_field_event(text, report_date=date, discipline_hint=disc,
                             location_hint=loc, prefer="fallback")
    return ev, match_event(ev, _acts())


def test_one_to_one_exact():
    ev, r = _run("24 inch spool erection completed at R-204 on 18 Sep 2026.", "2026-09-18", "Piping", "R-204")
    g = r["granularity"]
    assert g["type"] == "ONE_TO_ONE"
    assert g["activity_codes"] == ["PIP-204-017"]
    assert g["proposed_action"] == "propose_complete"
    assert g["proposed_progress"] == 100.0
    assert g["insufficient_evidence"] is False


def test_one_to_many_ambiguous_never_autocompletes():
    ev, r = _run("R204 piping work completed.", "2026-09-19", "Piping", "R-204")
    g = r["granularity"]
    assert g["type"] == "ONE_TO_MANY"
    assert len(g["activity_codes"]) >= 2
    assert g["insufficient_evidence"] is True
    assert g["proposed_action"] == "planner_review"  # never propose_complete for a group
    assert "auto-complete" in g["reason"] or "auto-completed" in g["reason"]
    acts = {a.code: a for a in _acts()}
    for code in g["activity_codes"]:
        assert acts[code].discipline == "Piping"
        assert acts[code].location == "R-204"


def test_one_to_many_missing_location():
    # Both R-204 and R-210 welds match; without a site the pick is unsafe.
    ev, r = _run("Welding done.", "2026-09-16", "Piping", "")
    g = r["granularity"]
    assert g["type"] == "ONE_TO_MANY"
    assert {"PIP-204-019", "PIP-210-013"} <= set(g["activity_codes"])
    assert g["insufficient_evidence"] is True


def test_partial_progress_single_target():
    ev, r = _run("24 inch spool erection at R-204 60 percent complete.", "2026-09-11", "Piping", "R-204")
    g = r["granularity"]
    assert g["type"] == "PARTIAL"
    assert g["activity_codes"] == ["PIP-204-017"]
    assert g["proposed_progress"] == 60.0
    assert g["proposed_action"] == "propose_progress"


def test_new_unplanned_genuine_miss():
    ev, r = _run("Helipad lighting completed at guest house complex.", "2026-09-21")
    g = r["granularity"]
    assert g["type"] == "NEW_UNPLANNED"
    assert g["activity_codes"] == []
    assert g["insufficient_evidence"] is True
    assert g["proposed_action"] == "propose_new_activity"


def test_granularity_types_valid_and_explained():
    for text, date, disc, loc in [
        ("24 inch spool erection completed at R-204 on 18 Sep 2026.", "2026-09-18", "Piping", "R-204"),
        ("R204 piping work completed.", "2026-09-19", "Piping", "R-204"),
        ("Helipad lighting completed at guest house complex.", "2026-09-21", "", ""),
    ]:
        ev, r = _run(text, date, disc, loc)
        assert r["granularity"]["type"] in TYPES
        assert r["granularity"]["reason"] != ""
        assert isinstance(r["granularity"]["details"], list)


def test_endpoint_carries_granularity():
    run_seed()
    one = client.post("/api/matching/run", json={"report_code": "DPR-2026-09-18-01"}).json()
    assert one["granularity"]["type"] == "ONE_TO_ONE"
    assert one["granularity"]["activity_codes"] == ["PIP-204-017"]
    many = client.post("/api/matching/run", json={"report_code": "DPR-2026-09-19-19"}).json()
    assert many["granularity"]["type"] == "ONE_TO_MANY"
    assert many["granularity"]["insufficient_evidence"] is True
    reloaded = client.get("/api/matching/DPR-2026-09-19-19").json()
    assert reloaded["granularity"]["type"] == "ONE_TO_MANY"


def test_resolve_pure_function_no_llm(monkeypatch):
    # Granularity must decide with zero network access.
    from app.matching import granularity as gran

    monkeypatch.setattr(gran, "UNMATCHED_FLOOR", 45.0)
    ev, r = _run("R204 piping work completed.", "2026-09-19", "Piping", "R-204")
    g = resolve_granularity(ev, r["candidates"], r["unmatched"], r["reason"])
    assert g["type"] == "ONE_TO_MANY"
