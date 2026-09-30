"""Phase 5 tests: exact / mismatch / wrong-disc / wrong-loc / ambiguous / unmatched.

Thresholds below are empirical (see probe in dev notes) but assert
ordering, margins and consistency — never hard-coded exact scores.
"""
from fastapi.testclient import TestClient

from app.config import settings
from app.llm.base import extract_field_event
from app.main import app
from app.matching.scorer import match_event, weights_from_settings
from app.models import Activity
from app.db import SessionLocal
from seed.synthetic_project import run_seed

client = TestClient(app)

EXACT = ("24 inch spool erection completed at R-204 on 18 Sep 2026.", "2026-09-18", "Piping", "R-204")


def _acts():
    db = SessionLocal()
    try:
        return db.query(Activity).order_by(Activity.code).all()
    finally:
        db.close()


def _ev(text, date, disc="", loc=""):
    return extract_field_event(text, report_date=date, discipline_hint=disc,
                               location_hint=loc, prefer="fallback")


def test_exact_match_top_with_margin():
    acts = _acts()
    r = match_event(_ev(*EXACT), acts)
    top = r["candidates"]
    assert top[0]["activity_code"] == "PIP-204-017"
    assert top[0]["score"] >= 75
    assert top[0]["score"] - top[1]["score"] >= 8
    assert not r["unmatched"]


def test_terminology_mismatch_resolves():
    # "pipe" has no schedule word; alias pipe->spool must bridge it.
    ev = _ev("24 inch pipe erection completed at R204.", "2026-09-18")
    assert ev.object == "pipe"  # parser stays honest...
    r = match_event(ev, _acts())
    assert r["candidates"][0]["activity_code"] == "PIP-204-017"  # ...scorer canonicalizes
    assert r["candidates"][0]["signals"]["object"] == 1.0


def test_wrong_discipline_downscores():
    acts = _acts()
    exact = match_event(_ev(*EXACT), acts)["candidates"][0]["score"]
    ev = _ev(EXACT[0], EXACT[1], "Civil", "R-204")
    r = match_event(ev, acts)
    assert r["candidates"][0]["activity_code"] == "PIP-204-017"  # still retrievable
    assert r["candidates"][0]["score"] < exact - 10  # ...but clearly penalized
    assert r["candidates"][0]["signals"]["discipline"] == 0.0


def test_wrong_location_switches_rack():
    ev = _ev("24 inch spool erection completed at R-210 on 18 Sep 2026.", "2026-09-18", "Piping", "R-210")
    r = match_event(ev, _acts())
    assert r["candidates"][0]["activity_code"] == "PIP-210-011"
    assert r["candidates"][0]["signals"]["location"] == 1.0


def test_ambiguous_r204_piping_cluster():
    ev = _ev("R204 piping work completed.", "2026-09-19", "Piping", "R-204")
    r = match_event(ev, _acts())
    top = r["candidates"]
    assert len(top) == 3
    assert top[0]["score"] < 60  # no safe auto candidate
    assert top[0]["score"] - top[2]["score"] < 5  # tight cluster -> human review
    acts = {a.code: a for a in _acts()}
    for c in top:
        assert acts[c["activity_code"]].discipline == "Piping"
        assert acts[c["activity_code"]].location == "R-204"


def test_genuinely_unmatched():
    ev = _ev("Helipad lighting completed at guest house complex.", "2026-09-21")
    r = match_event(ev, _acts())
    assert r["unmatched"] is True
    assert r["reason"] != ""
    assert all(c["score"] < 45.0 for c in r["candidates"])


def test_scores_match_weights_and_why():
    r = match_event(_ev(*EXACT), _acts())
    w = weights_from_settings(settings)
    assert abs(sum(w.values()) - 1.0) < 1e-9
    for c in r["candidates"]:
        expect = round(100 * sum(w[k] * c["signals"][k] for k in c["signals"]), 1)
        assert c["score"] == expect
        assert set(c["signals"]) == set(w)
        assert len(c["why"]) >= 7
        assert any("Piping" in line for line in c["why"])


def test_run_endpoint_persists_and_reloads():
    run_seed()
    r = client.post("/api/matching/run", json={"report_code": "DPR-2026-09-18-01"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["candidates"][0]["activity_code"] == "PIP-204-017"
    assert body["event"]["action"] == "erect"
    got = client.get("/api/matching/DPR-2026-09-18-01").json()
    assert got["candidates"][0]["activity_code"] == "PIP-204-017"
    assert got["event"]["object"] == "spool"


def test_run_endpoint_validates():
    run_seed()
    assert client.post("/api/matching/run", json={"report_code": "NOPE"}).status_code == 404
    assert client.post("/api/matching/run", json={}).status_code == 422
    assert client.get("/api/matching/NOPE").status_code == 404
