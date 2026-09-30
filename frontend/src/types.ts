export interface Health {
  status: string; app: string; version: string; database: string; llm: string; message: string;
}
export interface Activity {
  id: number; code: string; wbs_code: string; name: string; discipline: string;
  location: string; object: string; action: string; size: string; tag: string;
  planned_start: string; planned_finish: string;
  actual_start: string | null; actual_finish: string | null;
  progress: number; status: string;
  predecessors?: string[]; successors?: string[];
}
export interface FieldReport {
  id: number; report_code: string; raw_text: string; source: string;
  discipline: string; location: string; report_date: string; category: string;
  linked_activity_code: string | null; meta: string; source_type?: string;
}
export interface SourceDocument {
  id: number; source_id: string; title: string; publisher: string;
  source_url: string; publication_date: string; retrieved_at: string;
  document_type: string; local_file: string; checksum: string;
  source_type: string; notes: string;
}
export interface DomainTerm {
  term: string; category: string; source_id: string;
  context_snippet: string; section_ref: string;
  source_title?: string; source_url?: string; publisher?: string;
  publication_date?: string; retrieved_at?: string; source_type?: string;
  score?: number;
}
export interface FieldEvent {
  event_type: string; action: string; object: string; size: string; tag: string;
  location: string; discipline: string; event_date: string;
  progress_pct: number | null; evidence_text: string; report_id: string;
  extractor: string; warnings: string[];
}
export interface VocabHit {
  term: string; canonical_type: string; canonical_value: string; weight: number;
  approval_count: number; source_reports: string[];
}
export interface Candidate {
  activity_code: string; activity_name?: string; rank: number; score: number;
  base_score?: number; vocab_bonus?: number; vocab_hits?: VocabHit[];
  signals: Record<string, number>; why: string[];
}
export interface Granularity {
  type: string; activity_codes: string[]; reference_ids?: string[];
  proposed_progress: number | null; proposed_action: string;
  insufficient_evidence: boolean; reason: string; details: string[];
}
export interface Gate { decision: string; tier: string; margin: number; forced: boolean; reasons: string[] }
export interface Verification {
  target: string | null; proposal: string; valid: boolean;
  warnings: string[]; errors: string[]; reasons: string[];
  checks: Record<string, { warnings: string[]; errors: string[]; reasons: string[] }>;
  variance: { planned_duration_days: number | null; finish_variance_days: number | null;
    elapsed_to_claim_days: number | null; verdict: string; details: string[] };
  gate: Gate;
}
export interface MatchRun {
  report_code: string; event: FieldEvent; candidates: Candidate[];
  unmatched: boolean; reason: string; granularity: Granularity; verification?: Verification;
}
export interface QueueItem {
  report_code: string; bucket: string; gate: Gate; granularity_type: string;
  top_activity: string; top_score: number; margin: number;
  event_type: string; event_date: string; verification_valid: boolean;
  verification_errors: string[];
  decision: { state: string; target: string; actor: string; reason: string };
}
export interface ScheduleUpdate {
  id: number; report_code: string; activity_code: string; update_type: string;
  gate_decision: string; proposal: string; before_json: string; after_json: string;
  status: string; actor: string; reason: string; forced: number; created_at: string;
}
export interface AuditEvent {
  id: number; timestamp: string; actor: string; action: string; report_code: string;
  activity_codes: string; before_json: string; after_json: string; reason: string;
}
export interface VocabTerm {
  term: string; canonical_type: string; canonical_value: string; discipline: string;
  approval_count: number; source_reports: string[];
  first_approved_by: string; last_approved_by: string; last_approved_at: string;
}
export interface Patterns {
  synthetic: boolean; note: string;
  patterns: { pattern: string; discipline: string; executions: number;
    avg_planned_days: number; avg_actual_days: number; overrun_days: number;
    overrun_pct: number; common_issues: string[]; synthetic: boolean }[];
  by_discipline: Record<string, { executions: number; avg_planned_days: number;
    avg_actual_days: number; avg_overrun_days: number; common_issues: string[]; synthetic: boolean }>;
  delayed_activities: { code: string; name: string; discipline: string; status: string;
    planned_finish: string; days_overdue: number }[];
  delays_by_discipline: Record<string, number>;
  vocabulary_size: number;
}
export interface RiskSignal {
  signal: string; reason: string; variance_days: number | null; evidence: Record<string, unknown>;
}
export interface RiskItem {
  subject_type: string; subject_id: string; activity_code?: string; name: string;
  status: string; discipline: string; location: string;
  planned_start: string; planned_finish: string; actual_start: string; actual_finish: string;
  priority: string; attention_score: number; signals: string[]; reasons: string[];
  signal_details: RiskSignal[];
}
export interface RiskBoard {
  project_code: string; item_count: number;
  summary: { by_priority: Record<string, number>; by_signal: Record<string, number> };
  items: RiskItem[]; note: string;
}
export interface Dashboard {
  synthetic: boolean; note: string; projects: number; wbs_nodes: number;
  activities: number; relationships: number; reports: number;
  execution_patterns: number; conflicts: number;
  activities_by_discipline: Record<string, number>;
  reports_by_category: Record<string, number>;
  activities_by_status: Record<string, number>;
}
export interface Conflict {
  id: number; conflict_type: string; evidence_a: string; evidence_b: string;
  reason: string; suggested_action: string;
}
export interface GraphNode {
  code: string; name: string; status: string; progress: number;
  planned_start: string; planned_finish: string; actual_start: string; actual_finish: string;
  rel_type: string; via: string; level: number; direction: string;
}
export interface GraphWarning {
  kind: string; activities: string[]; rel_type: string;
  evidence: Record<string, { status: string; planned_finish: string; actual_start: string; actual_finish: string }>;
  message: string;
}
export interface ExecGraph {
  activity: GraphNode; predecessors: GraphNode[]; successors: GraphNode[];
  second_level: GraphNode[]; backbone: GraphNode[]; depth: number;
  warnings: GraphWarning[]; reasons: string[];
  latest_review: { report: string; decision: string; valid?: boolean; errors?: string[] } | null;
}
export interface Citation { type: string; id: string; label: string }
export interface AgentReply {
  answer: string; citations: Citation[]; intent: string; tools_used: string[]; composer: string;
}
