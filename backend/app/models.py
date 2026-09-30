"""BRIDGE-X Phase 2 data models (synthetic project).

Synthetic demonstration data — not real Oil India data.
"""
from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))


class WbsNode(Base):
    __tablename__ = "wbs_nodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    level: Mapped[int] = mapped_column(Integer)  # 5 or 6
    parent_code: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    wbs_code: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(300))
    discipline: Mapped[str] = mapped_column(String(32), index=True)
    location: Mapped[str] = mapped_column(String(32), index=True)
    object: Mapped[str] = mapped_column(String(80), default="")
    action: Mapped[str] = mapped_column(String(80), default="")
    size: Mapped[str] = mapped_column(String(32), default="")
    tag: Mapped[str] = mapped_column(String(64), default="")
    planned_start: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    planned_finish: Mapped[str] = mapped_column(String(10))
    actual_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    actual_finish: Mapped[str | None] = mapped_column(String(10), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="Not Started")


class ActivityRelationship(Base):
    __tablename__ = "activity_relationships"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_code: Mapped[str] = mapped_column(String(32), index=True)
    to_code: Mapped[str] = mapped_column(String(32), index=True)
    rel_type: Mapped[str] = mapped_column(String(8), default="FS")


class FieldReport(Base):
    __tablename__ = "field_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="text")
    discipline: Mapped[str] = mapped_column(String(32), default="")
    location: Mapped[str] = mapped_column(String(32), default="")
    report_date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    category: Mapped[str] = mapped_column(String(24), index=True)
    linked_activity_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Honest provenance: SYNTHETIC (regression fixtures) | USER_PROVIDED (ingested
    # field evidence). REAL_PUBLIC material lives ONLY in source_documents /
    # domain_terms — never as field_reports/DPRs — so it is never mistaken
    # for field execution data.
    source_type: Mapped[str] = mapped_column(String(16), default="SYNTHETIC")  # SYNTHETIC|USER_PROVIDED
    meta: Mapped[str] = mapped_column(Text, default="{}")  # JSON: filename, row/pages, contractor...


class ExecutionHistory(Base):
    __tablename__ = "execution_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern: Mapped[str] = mapped_column(String(160))
    discipline: Mapped[str] = mapped_column(String(32), index=True)
    executions: Mapped[int] = mapped_column(Integer, default=0)
    avg_planned_days: Mapped[float] = mapped_column(Float, default=0.0)
    avg_actual_days: Mapped[float] = mapped_column(Float, default=0.0)
    common_issues: Mapped[str] = mapped_column(Text, default="")
    synthetic: Mapped[int] = mapped_column(Integer, default=1)


class Conflict(Base):
    __tablename__ = "conflicts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conflict_type: Mapped[str] = mapped_column(String(24), index=True)
    evidence_a: Mapped[str] = mapped_column(String(40))
    evidence_b: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    suggested_action: Mapped[str] = mapped_column(Text)


class ExtractedEvent(Base):
    __tablename__ = "extracted_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_code: Mapped[str] = mapped_column(String(40), index=True)
    event_json: Mapped[str] = mapped_column(Text)  # serialized FieldEvent
    extractor: Mapped[str] = mapped_column(String(16), default="fallback")
    created_at: Mapped[str] = mapped_column(String(30), default="")


class MatchCandidate(Base):
    __tablename__ = "match_candidates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_code: Mapped[str] = mapped_column(String(40), index=True)
    event_json: Mapped[str] = mapped_column(Text)  # FieldEvent used for this run
    activity_code: Mapped[str] = mapped_column(String(32), index=True)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    base_score: Mapped[float] = mapped_column(Float, default=0.0)  # P14: weighted 8-signal score, no vocab
    vocab_bonus: Mapped[float] = mapped_column(Float, default=0.0)  # P14: bounded learned-vocabulary evidence
    vocab_hits_json: Mapped[str] = mapped_column(Text, default="[]")  # P14: provenance per hit
    signals_json: Mapped[str] = mapped_column(Text, default="{}")
    why_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[str] = mapped_column(String(30), default="")


class VerificationResult(Base):
    __tablename__ = "verification_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_code: Mapped[str] = mapped_column(String(40), index=True)
    target_activity: Mapped[str] = mapped_column(String(32), default="")
    proposal: Mapped[str] = mapped_column(String(32), default="")
    valid: Mapped[int] = mapped_column(Integer, default=0)
    decision: Mapped[str] = mapped_column(String(16), default="REVIEW")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(30), default="")


class ScheduleUpdate(Base):
    """Approved schedule change proposals. Records only — the activities
    table is never silently overwritten (no writer applies these)."""
    __tablename__ = "schedule_updates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_code: Mapped[str] = mapped_column(String(40), index=True)
    activity_code: Mapped[str] = mapped_column(String(32), default="")
    update_type: Mapped[str] = mapped_column(String(24), default="")  # complete|progress|new_activity|info
    gate_decision: Mapped[str] = mapped_column(String(16), default="")
    proposal: Mapped[str] = mapped_column(String(32), default="")
    before_json: Mapped[str] = mapped_column(Text, default="{}")
    after_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(16), default="approved")
    actor: Mapped[str] = mapped_column(String(64), default="planner")
    reason: Mapped[str] = mapped_column(Text, default="")
    forced: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(30), default="")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    decision: Mapped[str] = mapped_column(String(16), default="pending")
    target_activity: Mapped[str] = mapped_column(String(32), default="")
    actor: Mapped[str] = mapped_column(String(64), default="planner")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(30), default="")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[str] = mapped_column(String(30), index=True)
    actor: Mapped[str] = mapped_column(String(64), default="planner")
    action: Mapped[str] = mapped_column(String(24), index=True)
    report_code: Mapped[str] = mapped_column(String(40), default="")
    activity_codes: Mapped[str] = mapped_column(Text, default="[]")
    before_json: Mapped[str] = mapped_column(Text, default="{}")
    after_json: Mapped[str] = mapped_column(Text, default="{}")
    reason: Mapped[str] = mapped_column(Text, default="")


class ProjectVocabulary(Base):
    """Project-specific terminology memory. Rows are created ONLY from
    explicit human approvals (approve/remap) or planner-curated POSTs —
    never from raw LLM output or unreviewed matches."""
    __tablename__ = "project_vocabulary"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_code: Mapped[str] = mapped_column(String(32), default="BRX-DEMO-01", index=True)
    term: Mapped[str] = mapped_column(String(160), index=True)  # field phrase, normalized
    canonical_type: Mapped[str] = mapped_column(String(16), default="object")  # object|action|phrase
    canonical_value: Mapped[str] = mapped_column(String(160))  # e.g. "spool" or "PIP-204-017"
    discipline: Mapped[str] = mapped_column(String(32), default="")
    approval_count: Mapped[int] = mapped_column(Integer, default=0)
    source_reports: Mapped[str] = mapped_column(Text, default="[]")
    first_approved_by: Mapped[str] = mapped_column(String(64), default="")
    last_approved_by: Mapped[str] = mapped_column(String(64), default="")
    last_approved_at: Mapped[str] = mapped_column(String(30), default="")
    is_active: Mapped[int] = mapped_column(Integer, default=1)  # P14: only active rows may influence matching


class SourceDocument(Base):
    """REAL-DATA phase: curated public-source documents (Oil India public
    domain knowledge). Reference data only — never schedule, never DPRs."""
    __tablename__ = "source_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    publisher: Mapped[str] = mapped_column(String(200), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    publication_date: Mapped[str] = mapped_column(String(30), default="")
    retrieved_at: Mapped[str] = mapped_column(String(30), default="")
    document_type: Mapped[str] = mapped_column(String(64), default="")
    local_file: Mapped[str] = mapped_column(String(300), default="")
    checksum: Mapped[str] = mapped_column(String(80), default="")
    source_type: Mapped[str] = mapped_column(String(16), default="REAL_PUBLIC")
    notes: Mapped[str] = mapped_column(Text, default="")


class DomainTerm(Base):
    """REAL-DATA phase: one terminology/spec item with full provenance.
    Never a schedule node, never a DPR, never progress — context only."""
    __tablename__ = "domain_terms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    term: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(32), default="")
    context_snippet: Mapped[str] = mapped_column(Text, default="")
    section_ref: Mapped[str] = mapped_column(String(200), default="")
    extra_json: Mapped[str] = mapped_column(Text, default="{}")
