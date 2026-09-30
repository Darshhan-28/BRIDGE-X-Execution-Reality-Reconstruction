"""Phase 7 tests: six verification areas + confidence gate + variance.

All deterministic and offline. Score tiers follow config thresholds:
HIGH>=85 & margin>=15 PROPOSE; 60-85 or margin<15 REVIEW; <60 UNMATCHED;
any verification error forces REVIEW.
"""
from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import VerificationResult
from app.verification.confidence_gate import decide
from seed.synthetic_project import run_seed

client = TestClient(app)


def _run(payload):
    r = client.post("/api/matching/run", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---- gate tiers (unit) ----
def test_gate_propose():
    g = decide(97.4, 40.0, False, settings)
    assert (g["decision"], g["tier"]) == ("PROPOSE", "HIGH")


def test_gate_margin_forces_review():
    g = decide(89.3, 10.4, False, settings)  # high score, ambiguous margin
    assert g["decision"] == "REVIEW"


def test_gate_medium_band_review():
    assert decide(70.0, 30.0, False, settings)["decision"] == "REVIEW"


def test_gate_low_unmatched():
    g = decide(39.3, 27.6, False, settings)
    assert (g["decision"], g["tier"]) == ("UNMATCHED", "LOW")


def test_gate_errors_force_review():
    g = decide(97.4, 40.0, True, settings)
    assert g["decision"] == "REVIEW" and g["forced"] is True


# ---- end-to-end paths ----
def test_clean_propose_path():
    run_seed()
    b = _run({"raw_text": "Compressor K-201 erection completed at Yard-A on 14 Sep 2026.",
              "report_date": "2026-09-14", "discipline": "Mechanical", "location": "Yard-A"})
    v = b["verification"]
    assert v["valid"] is True and v["errors"] == []
    assert v["gate"]["decision"] == "PROPOSE"
    assert b["candidates"][0]["activity_code"] == "MEC-YRD-077"


def test_clean_demo_valid_but_margin_review():
    run_seed()
    b = _run({"report_code": "DPR-2026-09-18-01"})
    v = b["verification"]
    assert v["valid"] is True  # temporal/dependency/state all pass...
    assert v["gate"]["decision"] == "REVIEW"  # ...but margin 10.4 < 15 blocks auto-propose
    assert v["variance"]["finish_variance_days"] == 6
    assert v["variance"]["verdict"] == "behind plan"


def test_low_confidence_unmatched():
    run_seed()
    b = _run({"raw_text": "Helipad lighting completed at guest house complex.", "report_date": "2026-09-21"})
    assert b["verification"]["gate"]["decision"] == "UNMATCHED"


def test_predecessor_failure_welding_before_erection():
    run_seed()
    b = _run({"report_code": "DPR-2026-09-18-26"})
    v = b["verification"]
    assert v["valid"] is False
    assert any("PIP-204-018" in e and "predecessor" in e.lower() for e in v["errors"])
    assert v["gate"] == {"decision": "REVIEW", "tier": "MEDIUM", "margin": v["gate"]["margin"],
                         "forced": True, "reasons": v["gate"]["reasons"]}


def test_duplicate_report_detected():
    run_seed()
    text = "Busbar installation at S1 completed on 08 Sep 2026."
    a = client.post("/api/reports", json={"raw_text": text, "report_date": "2026-09-08"}).json()
    b = client.post("/api/reports", json={"raw_text": text, "report_date": "2026-09-08"}).json()
    rb = _run({"report_code": b["report_code"]})
    assert rb["verification"]["valid"] is False
    assert any(a["report_code"] in e and "uplicate" in e for e in rb["verification"]["errors"])
    assert rb["verification"]["gate"]["decision"] == "REVIEW"


def test_contradiction_start_after_completion():
    run_seed()
    _run({"report_code": "DPR-2026-09-18-26"})  # welding completed 18 Sep
    b = _run({"report_code": "DPR-2026-09-19-27"})  # welding started 19 Sep
    v = b["verification"]
    assert v["valid"] is False
    assert any("DPR-2026-09-18-26" in e and "ontradiction" in e for e in v["errors"])


def test_future_date_rejected():
    run_seed()
    b = _run({"raw_text": "24 inch spool erection completed at R-204 on 01 Jan 2030.",
              "report_date": "2030-01-01", "discipline": "Piping", "location": "R-204"})
    assert b["verification"]["valid"] is False
    assert any("uture" in e for e in b["verification"]["errors"])


def test_already_complete_state_error():
    run_seed()
    b = _run({"raw_text": "Transformer erection at substation S1 completed on 03 Sep 2026.",
              "report_date": "2026-09-03", "discipline": "Electrical", "location": "S1"})
    v = b["verification"]
    assert v["valid"] is False
    assert any("already" in e.lower() for e in v["errors"])


def test_verification_persisted_with_evidence():
    run_seed()
    _run({"report_code": "DPR-2026-09-18-26"})
    db = SessionLocal()
    try:
        rows = db.query(VerificationResult).filter(
            VerificationResult.report_code == "DPR-2026-09-18-26").all()
        assert len(rows) == 1
        assert rows[0].decision == "REVIEW" and rows[0].target_activity == "PIP-204-019"
        assert "PIP-204-018" in rows[0].result_json  # evidence preserved
    finally:
        db.close()


def test_verification_needs_no_network(monkeypatch):
    run_seed()
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("net!")))
    b = _run({"report_code": "DPR-2026-09-18-01"})
    assert b["verification"]["valid"] is True
