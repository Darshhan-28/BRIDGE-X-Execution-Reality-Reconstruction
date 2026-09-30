# DATA_MODEL.md — actual schema (`backend/app/models.py`, SQLite)

16 tables. Migrations for later-added columns live in `app/db.py`
`ensure_columns()` (ALTER TABLE only; `create_all` never alters).

| Table | Purpose | Key fields → used by |
|---|---|---|
| `projects` | Project registry | `code` (BRX-DEMO-01), `name` → seed, risk scoping |
| `wbs_nodes` | L5/L6 hierarchy | `project_id`, `code`, `level` 5\|6, `parent_code` → seed, risk scoping |
| `activities` | Schedule (read-only to pipeline) | `code`, `wbs_code`, `name`, `discipline`, `location`, `object`, `action`, `size`, `tag`, `planned_start/finish`, `actual_start/finish`, `progress`, `status` → matching, verification, graph, risk, agent, UI |
| `activity_relationships` | FS logic links | `from_code`, `to_code`, `rel_type` (all FS in seed) → dependencies, graph backbone, agent |
| `field_reports` | Raw evidence, verbatim | `report_code`, `raw_text`, `source`, `discipline`, `location`, `report_date`, `category`, `linked_activity_code` (seed hint), `source_type` (SYNTHETIC\|USER_PROVIDED; never REAL_PUBLIC), `meta` JSON → ingestion, duplicates, agent |
| `extracted_events` | Parsed events | `report_code`, `event_json`, `extractor`, `created_at` → extract API |
| `match_candidates` | Ranked links + audit | `report_code`, `event_json`, `activity_code`, `rank`, `score` (= base+bonus), `base_score`, `vocab_bonus`, `vocab_hits_json`, `signals_json`, `why_json` → matching, review, contradictions, UI |
| `verification_results` | P7 verdicts | `report_code`, `target_activity`, `proposal`, `valid`, `decision`, `result_json` → gate, review, risk, agent |
| `schedule_updates` | Approved change **records** | `report_code`, `activity_code`, `update_type` (complete\|progress\|new_activity\|info), `gate_decision`, `proposal`, `before/after_json`, `status`=approved, `actor`, `reason`, `forced` → review, audit, UI. Never applied to `activities` by any writer |
| `review_decisions` | One row per report | `report_code` unique, `decision`, `target_activity`, `actor`, `reason` → queue state, 409 re-decide guard |
| `audit_events` | Immutable trail | `timestamp`, `actor`, `action`, `report_code`, `activity_codes` JSON, `before/after_json`, `reason` → audit UI, demo proof |
| `project_vocabulary` | Learned terminology | `project_code`, `term`, `canonical_type` (object\|action\|phrase), `canonical_value`, `discipline`, `approval_count`, `source_reports` JSON, `first/last_approved_by/at`, `is_active` → memory, P14 boost |
| `execution_history` | Synthetic patterns | `pattern`, `discipline`, `executions`, `avg_planned/actual_days`, `common_issues`, `synthetic`=1 → patterns API, P16 REPEATED signal (always labeled synthetic) |
| `conflicts` | Known evidence clashes | `conflict_type` (duplicate\|contradiction\|impossible), `evidence_a/b`, `reason`, `suggested_action` → agent, risk |
| `source_documents` | REAL_PUBLIC provenance (never execution data) | `source_id` unique, `title`, `publisher`, `source_url`, `publication_date`, `retrieved_at`, `document_type`, `local_file`, `checksum`, `source_type`=REAL_PUBLIC, `notes` → knowledge APIs, LLM context provenance (see `OIL_PUBLIC_DATA.md`) |
| `domain_terms` | REAL_PUBLIC terminology (context only) | `source_id` → sources, `term`, `category`, `context_snippet` verbatim, `section_ref`, `extra_json` → keyword retrieval, LLM context; promotion to vocabulary is explicit human act only |

Constraints: `report_code` unique (reports, decisions); `activity.code` unique;
`match_candidates`/`verification_results` replaced per report on re-run
(delete+insert); reseed wipes everything except `projects/wbs/activities/
relationships/reports/history/conflicts` which are re-inserted.

## Lifecycle

```text
field_reports ──extract──▶ extracted_events
      │                         │
      └──── match ──▶ match_candidates ──verify──▶ verification_results
                                                        │
                        ┌─────────── human action ───────┘
                        ▼
              review_decisions + schedule_updates + audit_events
                        │                    │
                        │                    └──▶ project_vocabulary (approve/remap only)
                        ▼
              graph neighborhoods · risk board · agent answers (all read from above)
```
