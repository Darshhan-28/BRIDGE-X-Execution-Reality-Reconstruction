"""BRIDGE-X Phase 2 read APIs + dashboard counts + seed trigger + Phase 3 ingestion."""
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import ingestion as ing
from .db import get_db
from .models import (
    Activity,
    ActivityRelationship,
    Conflict,
    ExecutionHistory,
    FieldReport,
    Project,
    WbsNode,
)

router = APIRouter()


def _activity_dict(a: Activity) -> dict:
    return {c.name: getattr(a, c.name) for c in a.__table__.columns}


@router.get("/api/projects")
def list_projects(db: Session = Depends(get_db)):
    return [{"code": p.code, "name": p.name} for p in db.query(Project).all()]


@router.get("/api/activities")
def list_activities(discipline: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Activity)
    if discipline:
        q = q.filter(Activity.discipline == discipline)
    return [_activity_dict(a) for a in q.order_by(Activity.code).all()]


@router.get("/api/activities/{code}")
def get_activity(code: str, db: Session = Depends(get_db)):
    a = db.query(Activity).filter(Activity.code == code).first()
    if not a:
        raise HTTPException(404, f"Activity {code} not found")
    preds = [r.from_code for r in db.query(ActivityRelationship).filter(ActivityRelationship.to_code == code).all()]
    succs = [r.to_code for r in db.query(ActivityRelationship).filter(ActivityRelationship.from_code == code).all()]
    out = _activity_dict(a)
    out["predecessors"] = preds
    out["successors"] = succs
    return out


@router.get("/api/graph/{code}")
def execution_graph(code: str, depth: int = 1, report_code: str = "",
                    db: Session = Depends(get_db)):
    """Execution neighborhood + dependency-chain context for an activity.

    Deterministic, read-only, reusable (e.g. by the Time Agent later).
    With report_code, the stored field event is checked against the
    expected FS order. Never mutates schedule, review, or gate state.
    """
    import json

    from .execution_graph import analyze
    from .llm.base import FieldEvent
    from .models import MatchCandidate

    ev, proposal = None, ""
    if report_code:
        row = db.query(MatchCandidate).filter(
            MatchCandidate.report_code == report_code).order_by(
            MatchCandidate.rank).first()
        if not row:
            raise HTTPException(404, f"No match run for report {report_code}")
        try:
            ev = FieldEvent(**json.loads(row.event_json))
        except Exception as e:
            raise HTTPException(422, f"Stored event unreadable: {e}")
        if ev.event_type == "completion":
            proposal = "propose_complete"
        elif ev.event_type == "progress" and (ev.progress_pct or 0) < 100:
            proposal = "propose_progress"
        else:
            proposal = "planner_review"
    try:
        return analyze(db, code, ev, proposal, depth)
    except LookupError as e:
        raise HTTPException(404, str(e))


@router.get("/api/risk/project/{project_code}")
def risk_project(project_code: str, level: str = "", db: Session = Depends(get_db)):
    """Project attention board: ATTENTION / WATCH / NORMAL items with evidence.

    Read-only and advisory: derived live from schedule, P7 verification,
    P15 graph context, unmatched evidence, conflicts, and synthetic
    history. Never mutates anything, never predicts. `?level=` filters.
    """
    from .execution_risk import project_risk

    try:
        return project_risk(db, project_code, level)
    except LookupError as e:
        raise HTTPException(404, str(e))


@router.get("/api/risk/activity/{code}")
def risk_activity(code: str, db: Session = Depends(get_db)):
    """Single-activity attention item with full evidence (read-only)."""
    from . import execution_risk as R

    a = db.query(Activity).filter(Activity.code == code).first()
    if not a:
        raise HTTPException(404, f"Activity {code} not found")
    return R.assess_activity(db, a, R._unmatched_links(db))


@router.get("/api/reports")
def list_reports(category: str | None = None, db: Session = Depends(get_db)):
    q = db.query(FieldReport)
    if category:
        q = q.filter(FieldReport.category == category)
    return [
        {c.name: getattr(r, c.name) for c in r.__table__.columns}
        for r in q.order_by(FieldReport.report_code).all()
    ]


@router.get("/api/conflicts")
def list_conflicts(db: Session = Depends(get_db)):
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in db.query(Conflict).all()]


@router.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    by_disc = dict(db.query(Activity.discipline, func.count()).group_by(Activity.discipline).all())
    by_cat = dict(db.query(FieldReport.category, func.count()).group_by(FieldReport.category).all())
    by_status = dict(db.query(Activity.status, func.count()).group_by(Activity.status).all())
    return {
        "synthetic": True,
        "note": "Synthetic demonstration data — not real Oil India data.",
        "projects": db.query(Project).count(),
        "wbs_nodes": db.query(WbsNode).count(),
        "activities": db.query(Activity).count(),
        "relationships": db.query(ActivityRelationship).count(),
        "reports": db.query(FieldReport).count(),
        "execution_patterns": db.query(ExecutionHistory).count(),
        "conflicts": db.query(Conflict).count(),
        "activities_by_discipline": by_disc,
        "reports_by_category": by_cat,
        "activities_by_status": by_status,
    }


@router.post("/api/seed")
def seed(db: Session = Depends(get_db)):
    from seed.oil_public_data import load_oil_knowledge
    from seed.synthetic_project import run_seed

    out = run_seed(db)
    out["oil_knowledge"] = load_oil_knowledge(db)
    return out


class ReportIn(BaseModel):
    raw_text: str = Field(min_length=1)
    source: str = "text"
    discipline: str = ""
    location: str = ""
    report_date: str = ""
    category: str = "unclassified"
    meta: dict = Field(default_factory=dict)


def _report_dict(r: FieldReport) -> dict:
    return {c.name: getattr(r, c.name) for c in r.__table__.columns}


@router.post("/api/reports", status_code=201)
def ingest_text_report(body: ReportIn, db: Session = Depends(get_db)):
    """Ingest one free-text field report. Raw text is preserved verbatim."""
    raw = body.raw_text.strip()
    if not raw:
        raise HTTPException(422, "raw_text must not be blank.")
    rdate = ing.normalize_date(body.report_date) if body.report_date else date.today().isoformat()
    if not rdate:
        raise HTTPException(422, "report_date is unparseable; use YYYY-MM-DD.")
    rec = ing.create_report(
        db,
        raw_text=raw,
        source=body.source or "text",
        report_date=rdate,
        discipline=body.discipline,
        location=body.location,
        category=body.category or "unclassified",
        meta={"ingested_via": "api", **body.meta},
    )
    db.commit()
    return _report_dict(rec)


@router.post("/api/reports/analyze")
async def analyze_upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Ingest CSV / XLSX / PDF / TXT uploads.

    PDFs are text-extraction only (no OCR). Scanned PDFs return
    inserted=0 with an explicit "Prototype / OCR required" warning.
    """
    filename = file.filename or "upload.bin"
    data = await file.read()
    if not data:
        raise HTTPException(400, f"{filename}: empty file.")
    try:
        ext, blob = ing.read_upload(filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    warnings: list[str] = []
    candidates: list[dict] = []
    ocr_required = False

    if ext in ("csv", "xlsx", "xls"):
        try:
            df = ing.dataframe_from_upload(ext, blob)
        except Exception as e:
            raise HTTPException(400, f"{filename}: could not be parsed ({e}).")
        candidates, warnings = ing.parse_tabular(df, filename)
        source = ext
    elif ext == "pdf":
        text, meta, warnings = ing.extract_pdf(blob, filename)
        source = "pdf"
        if meta.get("ocr_required"):
            return {"inserted": 0, "report_codes": [], "warnings": warnings, "ocr_required": True}
        candidates = [{
            "raw_text": text,
            "discipline": "",
            "location": "",
            "report_date": date.today().isoformat(),
            "meta": meta,
        }]
    else:  # txt
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            text = blob.decode("latin-1")
        text = text.strip()
        if not text:
            raise HTTPException(400, f"{filename}: no text content.")
        source = "text"
        candidates = [{
            "raw_text": text,
            "discipline": "",
            "location": "",
            "report_date": date.today().isoformat(),
            "meta": {"filename": filename, "chars": len(text)},
        }]

    codes: list[str] = []
    for c in candidates:
        rec = ing.create_report(
            db, raw_text=c["raw_text"], source=source,
            report_date=c["report_date"], discipline=c["discipline"],
            location=c["location"], category="unclassified", meta=c["meta"],
        )
        codes.append(rec.report_code)
    db.commit()
    return {"inserted": len(codes), "report_codes": codes, "warnings": warnings, "ocr_required": ocr_required}


class MatchRunIn(BaseModel):
    report_code: str = ""
    event: dict = Field(default_factory=dict)
    raw_text: str = ""
    report_date: str = ""
    discipline: str = ""
    location: str = ""
    prefer: str = "fallback"  # deterministic default; "auto"/"llm" opt in
    top_k: int = 3


@router.post("/api/matching/run", status_code=201)
def run_matching(body: MatchRunIn, db: Session = Depends(get_db)):
    """Contextual schedule linking for one field event.

    Consumes a Phase-4 FieldEvent (passed directly, or built from a
    stored report / inline text). Never calls the LLM itself, never
    applies schedule updates. Persists top-k candidates plus the
    verification result and confidence-gate decision.
    """
    import json
    from datetime import datetime, timezone

    from .llm.base import FieldEvent, extract_field_event
    from .matching.scorer import match_event
    from .models import MatchCandidate, VerificationResult
    from .verification.pipeline import verify_proposal

    code = body.report_code.strip()
    if body.event:
        try:
            ev = FieldEvent(**body.event)
        except Exception as e:
            raise HTTPException(422, f"Invalid event: {e}")
    else:
        text = body.raw_text.strip()
        rdate, disc, loc = body.report_date, body.discipline, body.location
        if code:
            rep = db.query(FieldReport).filter(FieldReport.report_code == code).first()
            if not rep:
                raise HTTPException(404, f"Report {code} not found")
            text = text or rep.raw_text
            rdate = rdate or rep.report_date
            disc = disc or rep.discipline
            loc = loc or rep.location
        if not text:
            raise HTTPException(422, "Provide report_code, event, or raw_text.")
        ev = extract_field_event(
            text, report_id=code, report_date=rdate,
            discipline_hint=disc, location_hint=loc, prefer=body.prefer,
        )
    activities = db.query(Activity).order_by(Activity.code).all()
    if not activities:
        raise HTTPException(409, "No activities seeded. POST /api/seed first.")
    result = match_event(ev, activities, top_k=max(1, min(body.top_k, 10)), db=db)

    if code:
        db.query(MatchCandidate).filter(MatchCandidate.report_code == code).delete()
        db.query(VerificationResult).filter(VerificationResult.report_code == code).delete()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for c in result["candidates"]:
        db.add(MatchCandidate(
            report_code=code, event_json=ev.model_dump_json(),
            activity_code=c["activity_code"], rank=c["rank"], score=c["score"],
            base_score=c.get("base_score", c["score"]),
            vocab_bonus=c.get("vocab_bonus", 0.0),
            vocab_hits_json=json.dumps(c.get("vocab_hits", [])),
            signals_json=json.dumps(c["signals"]), why_json=json.dumps(c["why"]),
            created_at=now,
        ))
    verification = verify_proposal(ev, result["granularity"], result["candidates"], db, code)
    if code:
        db.add(VerificationResult(
            report_code=code, target_activity=verification["target"] or "",
            proposal=verification["proposal"], valid=int(verification["valid"]),
            decision=verification["gate"]["decision"],
            result_json=json.dumps(verification), created_at=now,
        ))
    db.commit()
    return {"report_code": code, "event": ev.model_dump(), **result, "verification": verification}


@router.get("/api/matching/{report_code}")
def get_matching(report_code: str, db: Session = Depends(get_db)):
    """Latest persisted match run for a report (granularity recomputed)."""
    import json

    from .llm.base import FieldEvent
    from .matching.granularity import resolve_granularity
    from .matching.scorer import UNMATCHED_FLOOR
    from .models import MatchCandidate
    from .verification.pipeline import verify_proposal

    rows = db.query(MatchCandidate).filter(
        MatchCandidate.report_code == report_code).order_by(MatchCandidate.rank).all()
    if not rows:
        raise HTTPException(404, f"No match run for {report_code}")
    ev = FieldEvent(**json.loads(rows[0].event_json))
    cands = [
        {"activity_code": r.activity_code, "rank": r.rank, "score": r.score,
         "base_score": (r.base_score if r.base_score is not None else r.score),
         "vocab_bonus": (r.vocab_bonus or 0.0),
         "vocab_hits": json.loads(r.vocab_hits_json or "[]"),
         "signals": json.loads(r.signals_json), "why": json.loads(r.why_json)}
        for r in rows
    ]
    unmatched = not cands or cands[0]["score"] < UNMATCHED_FLOOR
    gran = resolve_granularity(ev, cands, unmatched)
    verification = verify_proposal(ev, gran, cands, db, report_code)
    return {
        "report_code": report_code,
        "event": ev.model_dump(),
        "candidates": cands,
        "unmatched": unmatched,
        "granularity": gran,
        "verification": verification,
    }


class EventExtractIn(BaseModel):
    report_code: str = ""
    raw_text: str = ""
    report_date: str = ""
    discipline: str = ""
    location: str = ""
    prefer: str = "auto"  # auto | llm | fallback


@router.post("/api/events/extract", status_code=201)
def extract_event(body: EventExtractIn, db: Session = Depends(get_db)):
    """Understand one field report -> structured, validated FieldEvent.

    Accepts a stored report_code or inline raw_text. Persists the event
    with source report_id + raw evidence. LLM optional, fallback always.
    """
    from datetime import datetime, timezone

    from .llm.base import extract_field_event
    from .models import ExtractedEvent

    text, code = body.raw_text.strip(), body.report_code.strip()
    rdate, disc, loc = body.report_date, body.discipline, body.location
    if code:
        rep = db.query(FieldReport).filter(FieldReport.report_code == code).first()
        if not rep:
            raise HTTPException(404, f"Report {code} not found")
        text = text or rep.raw_text
        rdate = rdate or rep.report_date
        disc = disc or rep.discipline
        loc = loc or rep.location
    if not text:
        raise HTTPException(422, "Provide report_code or raw_text.")
    if body.prefer not in ("auto", "llm", "fallback"):
        raise HTTPException(422, "prefer must be auto, llm or fallback.")
    # REAL-DATA phase: source-grounded terminology context for the LLM
    # only. The fallback parser never sees it (offline output unchanged).
    domain_ctx, domain_prov = "", []
    if body.prefer != "fallback":
        from .config import settings as _settings
        from .domain_knowledge import domain_context_block

        if _settings.llm_configured:
            domain_ctx, domain_prov = domain_context_block(db, text)
    ev = extract_field_event(
        text, report_id=code, report_date=rdate,
        discipline_hint=disc, location_hint=loc, prefer=body.prefer,
        domain_context=domain_ctx,
    )
    rec = ExtractedEvent(
        report_code=code, event_json=ev.model_dump_json(),
        extractor=ev.extractor, created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    db.add(rec)
    db.commit()
    return {"id": rec.id, "event": ev.model_dump(), "domain_provenance": domain_prov}


@router.get("/api/events")
def list_events(report_code: str | None = None, db: Session = Depends(get_db)):
    """List extracted events, optionally filtered by report."""
    from .models import ExtractedEvent

    q = db.query(ExtractedEvent)
    if report_code:
        q = q.filter(ExtractedEvent.report_code == report_code)
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in q.order_by(ExtractedEvent.id).all()]


def _review_err(e) -> HTTPException:
    from .review import ReviewError

    if isinstance(e, ReviewError):
        return HTTPException(e.status, e.detail)
    raise e


class ReviewActionIn(BaseModel):
    report_code: str
    actor: str = "planner"
    reason: str = ""
    force: bool = False


class RemapIn(ReviewActionIn):
    activity_code: str = ""


class MarkNewIn(ReviewActionIn):
    activity_name: str = ""


class MergeIn(ReviewActionIn):
    into_report_code: str = ""


@router.get("/api/review/queue")
def review_queue(bucket: str = "", db: Session = Depends(get_db)):
    """Planner review queue with HIGH/MEDIUM/LOW/CONFLICT/UNMATCHED buckets."""
    from .review import build_queue

    return build_queue(db, bucket)


@router.get("/api/review/decisions")
def review_decisions(report_code: str | None = None, db: Session = Depends(get_db)):
    from .models import ReviewDecision

    q = db.query(ReviewDecision)
    if report_code:
        q = q.filter(ReviewDecision.report_code == report_code)
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns}
            for r in q.order_by(ReviewDecision.id).all()]


@router.post("/api/review/approve", status_code=201)
def review_approve(body: ReviewActionIn, db: Session = Depends(get_db)):
    from .review import do_approve

    try:
        return do_approve(db, body.report_code, body.actor, body.reason, body.force)
    except Exception as e:
        raise _review_err(e)


@router.post("/api/review/reject", status_code=201)
def review_reject(body: ReviewActionIn, db: Session = Depends(get_db)):
    from .review import do_reject

    try:
        return do_reject(db, body.report_code, body.actor, body.reason, body.force)
    except Exception as e:
        raise _review_err(e)


@router.post("/api/review/remap", status_code=201)
def review_remap(body: RemapIn, db: Session = Depends(get_db)):
    from .review import do_remap

    try:
        return do_remap(db, body.report_code, body.activity_code, body.actor, body.reason, body.force)
    except Exception as e:
        raise _review_err(e)


@router.post("/api/review/mark-new", status_code=201)
def review_mark_new(body: MarkNewIn, db: Session = Depends(get_db)):
    from .review import do_mark_new

    try:
        return do_mark_new(db, body.report_code, body.actor, body.reason, body.activity_name)
    except Exception as e:
        raise _review_err(e)


@router.post("/api/review/merge", status_code=201)
def review_merge(body: MergeIn, db: Session = Depends(get_db)):
    from .review import do_merge

    try:
        return do_merge(db, body.report_code, body.into_report_code, body.actor, body.reason)
    except Exception as e:
        raise _review_err(e)


@router.get("/api/schedule-updates")
def schedule_updates(report_code: str | None = None, db: Session = Depends(get_db)):
    from .models import ScheduleUpdate

    q = db.query(ScheduleUpdate)
    if report_code:
        q = q.filter(ScheduleUpdate.report_code == report_code)
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns}
            for r in q.order_by(ScheduleUpdate.id).all()]


@router.get("/api/audit")
def audit_trail(report_code: str | None = None, action: str | None = None, db: Session = Depends(get_db)):
    from .models import AuditEvent

    q = db.query(AuditEvent)
    if report_code:
        q = q.filter(AuditEvent.report_code == report_code)
    if action:
        q = q.filter(AuditEvent.action == action)
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns}
            for r in q.order_by(AuditEvent.id).all()]


class VocabularyIn(BaseModel):
    term: str
    canonical_type: str = "object"
    canonical_value: str = ""
    discipline: str = ""
    actor: str = "planner"


@router.get("/api/memory/vocabulary")
def memory_vocabulary(discipline: str = "", term: str = "", db: Session = Depends(get_db)):
    """Learned project terminology (approval-sourced) with evidence metadata."""
    from .memory import list_vocabulary

    return list_vocabulary(db, discipline, term)


@router.post("/api/memory/vocabulary", status_code=201)
def memory_vocabulary_add(body: VocabularyIn, db: Session = Depends(get_db)):
    """Planner-curated term: an explicit human action, recorded with provenance."""
    from .memory import add_curated_term, now

    try:
        row = add_curated_term(db, body.term, body.canonical_type, body.canonical_value,
                               body.discipline, body.actor, now())
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"term": row.term, "canonical_type": row.canonical_type,
            "canonical_value": row.canonical_value, "approval_count": row.approval_count}


@router.get("/api/memory/patterns")
def memory_patterns(db: Session = Depends(get_db)):
    """Execution-pattern aggregates. Synthetic — never real project data."""
    from .memory import execution_patterns

    return execution_patterns(db)


class TimeAgentIn(BaseModel):
    question: str = Field(min_length=1)


@router.post("/api/time-agent")
def time_agent(body: TimeAgentIn, db: Session = Depends(get_db)):
    """Conversational Time Agent: grounded tools, cited answers, no writes."""
    from .time_agent import answer

    q = body.question.strip()
    if not q:
        raise HTTPException(422, "question must not be blank.")
    return answer(q, db)


class PromoteIn(BaseModel):
    term_id: int
    canonical_type: str = "object"
    canonical_value: str = ""
    actor: str = "planner"
    reason: str = ""


@router.get("/api/knowledge/sources")
def knowledge_sources(db: Session = Depends(get_db)):
    """Curated REAL_PUBLIC source documents with full provenance."""
    from .models import SourceDocument

    return [{c.name: getattr(r, c.name) for c in r.__table__.columns}
            for r in db.query(SourceDocument).order_by(SourceDocument.id).all()]


@router.get("/api/knowledge/terms")
def knowledge_terms(q: str = "", category: str = "", db: Session = Depends(get_db)):
    """Domain terms with per-item source provenance. Never schedule/DPR data."""
    from .domain_knowledge import retrieve_terms
    from .models import DomainTerm

    if q.strip():
        return retrieve_terms(db, q)
    query = db.query(DomainTerm)
    if category:
        query = query.filter(DomainTerm.category == category)
    return [{"term": r.term, "category": r.category, "source_id": r.source_id,
             "context_snippet": r.context_snippet, "section_ref": r.section_ref or ""}
            for r in query.order_by(DomainTerm.term).all()]


@router.get("/api/knowledge/lookup")
def knowledge_lookup(q: str, db: Session = Depends(get_db)):
    """Answer 'where did this OIL-specific term come from?' Honest provenance."""
    from .domain_knowledge import lookup_term_provenance

    if not q.strip():
        raise HTTPException(422, "q must not be blank.")
    return lookup_term_provenance(db, q.strip())


@router.post("/api/knowledge/promote", status_code=201)
def knowledge_promote(body: PromoteIn, db: Session = Depends(get_db)):
    """Promote a REAL_PUBLIC domain term into project vocabulary.

    Explicit human action (actor + reason required): goes through the same
    curated path as manual terms, so P14 eligibility rules still apply.
    The domain term itself never influences matching until promoted.
    """
    import json
    from datetime import datetime, timezone

    from .memory import add_curated_term, now
    from .models import AuditEvent, DomainTerm

    if not (body.reason or "").strip():
        raise HTTPException(422, "Promoting a term requires a reason.")
    term = db.query(DomainTerm).filter(DomainTerm.id == body.term_id).first()
    if not term:
        raise HTTPException(404, f"Domain term {body.term_id} not found.")
    try:
        row = add_curated_term(db, term.term, body.canonical_type,
                               body.canonical_value, "", body.actor, now())
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.add(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        actor=body.actor or "planner", action="promote_knowledge",
        report_code="", activity_codes=json.dumps([row.canonical_value]),
        before_json=json.dumps({"source_id": term.source_id, "term": term.term}),
        after_json=json.dumps({"vocabulary": row.term, "canonical_value": row.canonical_value}),
        reason=body.reason))
    db.commit()
    return {"term": row.term, "canonical_value": row.canonical_value,
            "approval_count": row.approval_count, "source_id": term.source_id}
