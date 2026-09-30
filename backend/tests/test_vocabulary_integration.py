"""P14: approved vocabulary actively improves linking — with safety rails.

Covers: boost on approved mappings, base-score formula intact, static
aliases unaffected, unapproved/inactive/foreign-project rows ignored,
no learning from LLM output / reject / merge / mark-new / raw reports,
gate + thresholds unchanged and unbypassable, bonus cap, persistence.
"""
from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.matching import vocabulary_boost as vb
from app.matching.scorer import UNMATCHED_FLOOR, match_event, weights_from_settings
from app.models import Activity, ProjectVocabulary
from seed.synthetic_project import run_seed

client = TestClient(app)

PIPE_A = "24 inch pipeline erection completed at R-210 on 20 Sep 2026."
PIPE_B = "24 inch pipeline fit-up completed at R-210 on 21 Sep 2026."


def _ingest(text, date="2026-09-20", disc="Piping", loc="R-210"):
    r = client.post("/api/reports", json={"raw_text": text, "report_date": date,
                                          "discipline": disc, "location": loc})
    assert r.status_code == 201, r.text
    return r.json()["report_code"]


def _run(code, **kw):
    body = {"report_code": code, **kw}
    r = client.post("/api/matching/run", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _approve(code, **kw):
    body = {"report_code": code, "force": True, "reason": "P14 test.", **kw}
    r = client.post("/api/review/approve", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _acts():
    db = SessionLocal()
    try:
        return db.query(Activity).order_by(Activity.code).all()
    finally:
        db.close()


def _learn_pipeline_mapping():
    """Controlled demo setup: approve pipeline-wording erection at R-210."""
    code = _ingest(PIPE_A)
    _run(code)
    return code, _approve(code)["vocabulary_learned"]


def test_controlled_demo_boost_with_provenance():
    run_seed()
    code_a, learned = _learn_pipeline_mapping()
    assert {"term": "line", "canonical_type": "object", "canonical_value": "spool"} in learned
    code_b = _ingest(PIPE_B, date="2026-09-21")
    before = _run(code_b)
    # NOTE: `before` already sees the mapping (learned above); the no-vocab
    # baseline is reconstructed by direct match_event without a session.
    from app.llm.base import extract_field_event
    ev = extract_field_event(PIPE_B, report_date="2026-09-21",
                             discipline_hint="Piping", location_hint="R-210", prefer="fallback")
    plain = match_event(ev, _acts())  # db=None -> exact P5 behavior
    assert all(c.get("vocab_bonus", 0.0) == 0.0 for c in plain["candidates"])
    top_plain = next(c for c in plain["candidates"] if c["activity_code"] == "PIP-210-012")
    top = before["candidates"][0]
    assert top["activity_code"] == "PIP-210-012"
    assert top["base_score"] == top_plain["score"]  # base untouched by learning
    assert top["vocab_bonus"] == vb.VOCAB_W_OBJECT  # object hit only
    assert top["score"] == round(top["base_score"] + vb.VOCAB_W_OBJECT, 1)
    (hit,) = top["vocab_hits"]
    assert (hit["term"], hit["canonical_value"]) == ("line", "spool")
    assert hit["approval_count"] == 1 and code_a in hit["source_reports"]
    assert any(w.startswith("[vocab]") and "'line'->'spool'" in w and code_a in w
               for w in top["why"])


def test_base_score_formula_intact_with_vocab_present():
    run_seed()
    _learn_pipeline_mapping()
    code = _ingest(PIPE_B, date="2026-09-21")
    m = _run(code)
    w = weights_from_settings(settings)
    for c in m["candidates"]:
        expect = round(100 * sum(w[k] * c["signals"][k] for k in c["signals"]), 1)
        assert c["base_score"] == expect
        assert c["score"] == round(expect + c["vocab_bonus"], 1)
        assert c["vocab_bonus"] <= vb.VOCAB_MAX_BONUS


def test_static_alias_needs_no_vocab():
    run_seed()
    assert client.get("/api/memory/vocabulary").json() == []
    code = _ingest("24 inch pipe erection completed at R204.", date="2026-09-18", loc="R-204")
    m = _run(code)
    assert m["candidates"][0]["activity_code"] == "PIP-204-017"
    assert m["candidates"][0]["vocab_bonus"] == 0.0


def _insert_vocab_row(**kw):
    params = {"project_code": "BRX-DEMO-01", "term": "line", "canonical_type": "object",
              "canonical_value": "spool", "discipline": "Piping", "approval_count": 1,
              "source_reports": "[]", "is_active": 1}
    params.update(kw)
    db = SessionLocal()
    try:
        db.add(ProjectVocabulary(**params))
        db.commit()
    finally:
        db.close()


def test_unapproved_vocab_ignored():
    run_seed()
    _insert_vocab_row(approval_count=0)
    code = _ingest(PIPE_B, date="2026-09-21")
    assert _run(code)["candidates"][0]["vocab_bonus"] == 0.0


def test_inactive_vocab_ignored():
    run_seed()
    _insert_vocab_row(is_active=0)
    code = _ingest(PIPE_B, date="2026-09-21")
    assert _run(code)["candidates"][0]["vocab_bonus"] == 0.0


def test_foreign_project_vocab_ignored():
    run_seed()
    _insert_vocab_row(project_code="OTHER-PROJ")
    code = _ingest(PIPE_B, date="2026-09-21")
    assert _run(code)["candidates"][0]["vocab_bonus"] == 0.0


def test_llm_output_cannot_teach(monkeypatch):
    run_seed()
    import json as _json

    from app.llm import openrouter as oro

    monkeypatch.setattr(oro.settings, "OPENROUTER_API_KEY", "test-key")

    class _Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": _json.dumps({
                "event_type": "completion", "action": "erect", "object": "line",
                "size": '24"', "tag": "", "location": "R-210", "discipline": "Piping",
                "event_date": "2026-09-20", "progress_pct": 100.0,
                "evidence_text": PIPE_A, "report_id": "", "extractor": "llm", "warnings": []})}}]}

    monkeypatch.setattr(oro, "_post", lambda payload: _Resp())
    code = _ingest(PIPE_A)
    m = _run(code, prefer="llm")
    assert m["event"]["extractor"] == "llm"  # LLM really ran...
    db = SessionLocal()
    try:
        assert db.query(ProjectVocabulary).count() == 0  # ...and taught nothing
    finally:
        db.close()
    assert m["candidates"][0]["vocab_bonus"] == 0.0


def test_reject_merge_marknew_cannot_teach():
    run_seed()
    db = SessionLocal()
    n0 = db.query(ProjectVocabulary).count()
    db.close()
    a = _ingest(PIPE_A)
    _run(a)
    client.post("/api/review/reject", json={"report_code": a, "reason": "P14 test."})
    b = _ingest("Helipad lighting completed at guest house complex.",
                date="2026-09-21", disc="", loc="")
    _run(b)
    client.post("/api/review/mark-new", json={"report_code": b, "reason": "P14 test."})
    c = _ingest("Busbar work at S1 done.", date="2026-09-08", disc="Electrical", loc="S1")
    _run(c)
    e = _ingest("Busbar work at S1 done.", date="2026-09-08", disc="Electrical", loc="S1")
    _run(e)
    client.post("/api/review/merge", json={"report_code": e, "into_report_code": c,
                                           "reason": "P14 test."})
    db = SessionLocal()
    try:
        assert db.query(ProjectVocabulary).count() == n0
    finally:
        db.close()


def test_vocab_cannot_bypass_gate_and_cap_holds():
    run_seed()
    code_a, _ = _learn_pipeline_mapping()
    # Same claim re-filed: learned bonus fires AND duplicate error forces REVIEW.
    dup = _ingest(PIPE_A)
    m = _run(dup)
    assert m["candidates"][0]["vocab_bonus"] > 0.0
    assert m["verification"]["valid"] is False
    assert m["verification"]["gate"]["decision"] == "REVIEW"
    assert m["verification"]["gate"]["forced"] is True
    # Bonus cap: stack object+action+phrase hits on one candidate via curation.
    client.post("/api/memory/vocabulary", json={"term": "line", "canonical_type": "object",
                                                "canonical_value": "spool", "discipline": "Piping"})
    code = _ingest("24 inch pipeline erection completed at R-210 on 22 Sep 2026.",
                   date="2026-09-22")
    top = _run(code)["candidates"][0]
    assert top["vocab_bonus"] == vb.VOCAB_MAX_BONUS
    assert top["score"] == round(top["base_score"] + vb.VOCAB_MAX_BONUS, 1)


def test_thresholds_and_weights_unchanged():
    assert (settings.HIGH_THRESHOLD, settings.MEDIUM_THRESHOLD, settings.MIN_MARGIN) == (85.0, 60.0, 15.0)
    assert UNMATCHED_FLOOR == 45.0
    from app.config import settings as s2

    assert abs(sum(weights_from_settings(s2).values()) - 1.0) < 1e-9


def test_phrase_mapping_is_activity_specific():
    run_seed()
    _learn_pipeline_mapping()  # learns "erect line" -> PIP-210-011
    code = _ingest("24 inch pipeline erection at R-210 completed on 22 Sep 2026.",
                   date="2026-09-22")
    m = _run(code, top_k=10)
    top = m["candidates"][0]
    assert top["activity_code"] == "PIP-210-011"
    assert "phrase" in {h["canonical_type"] for h in top["vocab_hits"]}
    # Phrase mappings fire only on their mapped activity, never elsewhere.
    for c in m["candidates"]:
        for h in c["vocab_hits"]:
            if h["canonical_type"] == "phrase":
                assert h["canonical_value"] == c["activity_code"]


def test_boost_persisted_and_reloaded():
    run_seed()
    _learn_pipeline_mapping()
    code = _ingest(PIPE_B, date="2026-09-21")
    live = _run(code)
    stored = client.get(f"/api/matching/{code}").json()
    for a, b in zip(live["candidates"], stored["candidates"]):
        assert (b["base_score"], b["vocab_bonus"], b["vocab_hits"]) == (
            a["base_score"], a["vocab_bonus"], a["vocab_hits"])
        assert b["score"] == a["score"]
