# FEATURES.md — P1 through P16 (verified against code)

> Current feature boundary: **P16**. Phases below summarize what the
> repository actually contains (`backend/app/*`, `frontend/src/*`).

## P1 Foundation

- **Purpose:** runnable skeleton. **Implementation:** FastAPI + SQLite +
  health endpoint; Vite+TS shell. **Files:** `app/main.py`, `config.py`,
  `db.py`. **APIs:** `GET /api/health`, `GET /`. **Tests:** `test_health.py` (2).
  **Constraint:** must boot with no API key (fallback-only).

## P2 Synthetic Project

- **Purpose:** realistic demo data, no real Oil India data. **Implementation:**
  `seed/synthetic_project.py` (idempotent wipe+insert), 7 models.
  **Data:** 1 project `BRX-DEMO-01`, 12 WBS (5×L5+7×L6), 55 activities
  (Piping 16/Civil 11/Electrical 10/Mechanical 9/Instrumentation 9),
  34 FS relationships, 35 reports (clean 5, mismatch 5, abbreviation 4,
  incomplete 4, ambiguous 3, duplicate 4, contradiction 4, partial 3,
  unmatched 3), 8 execution patterns, 3 conflicts.
  **APIs:** projects/activities/reports/conflicts/dashboard reads + `POST /api/seed`.
  **Tests:** `test_seed.py` (5).

## P3 Field Ingestion

- **Purpose:** multi-format intake preserving raw evidence. **Files:**
  `app/ingestion.py`. **APIs:** `POST /api/reports` (JSON, blank rejected
  422), `POST /api/reports/analyze` (CSV/XLSX/PDF/TXT upload).
  **DB:** `field_reports.meta` JSON (+`ensure_columns` migration).
  **Rules:** flexible headers, 10 date formats, scanned PDF → `inserted: 0`
  + explicit `Prototype / OCR required` (no OCR dep). **Tests:**
  `test_ingestion.py` (7). Deps added: pandas, openpyxl, pymupdf, python-multipart.

## P4 Event Understanding

- **Purpose:** structured `FieldEvent` (type/action/object/size/tag/
  location/discipline/date/progress/evidence/report/extractor/warnings).
  **Files:** `app/llm/{base,fallback,openrouter}.py`.
  **Rules:** LLM JSON-only, Pydantic-validated, 1 retry → fallback; never
  mandatory; `prefer: auto|llm|fallback`. **APIs:** `POST /api/events/extract`,
  `GET /api/events`. **DB:** `extracted_events`. **Tests:** `test_events.py`
  (12, incl. mocked LLM success/double-failure/rate-limit/no-key).

## P5 Contextual Matching

- **Purpose:** explainable schedule linking, no LLM. **Files:**
  `matching/{fingerprint,candidate_retrieval,scorer}.py`.
  **Method:** alias canonicalization (`pipe→spool`, `joint→weld`,
  `copper→cable`, `ct→cable tray`, `fdn/footing/rcc→foundation`) →
  TF-IDF cosine + RapidFuzz token-set (floors 0.10/40) → 8-signal weighted
  score (weights 0.25/0.20/0.15/0.12/0.10/0.08/0.05/0.05, sum 1.0) →
  top-k (default 3, max 10), floor 45.0, per-signal WHY cards.
  **APIs:** `POST /api/matching/run`, `GET /api/matching/{code}`.
  **DB:** `match_candidates`. **Tests:** `test_matching.py` (9).

## P6 Granularity

- **Purpose:** 1 event ≠ 1 activity. **File:** `matching/granularity.py`
  (pure function). Types: ONE_TO_ONE (specific + margin≥5 or ≥75) /
  ONE_TO_MANY (coarse + cluster, insufficient evidence, never auto-complete)
  / PARTIAL (explicit % → progress only) / NEW_UNPLANNED (below floor).
  Constants: margin 5.0, cluster band 8.0, high-safe 75.0, group cap 6.
  Carried on every match run. **Tests:** `test_granularity.py` (8).

## P7 Verification (authoritative)

- **Purpose:** deterministic proposal validation + gate. **Files:**
  `verification/` (8 files). Checks: temporal, FS-dependency, state
  machine, duplicate, contradiction + informational variance.
  Gate: errors→forced REVIEW; <60 UNMATCHED/LOW; ≥85+margin≥15 PROPOSE/HIGH;
  else REVIEW/MEDIUM. Nothing is applied to the schedule.
  **DB:** `verification_results`. **Tests:** `test_verification.py` (15).

## P8 Human Review

- **Purpose:** gated consequential decisions + audit. **File:** `app/review.py`.
  Queue buckets CONFLICT/HIGH/MEDIUM/LOW/UNMATCHED; actions approve, reject,
  remap (re-verifies target), mark-new (proposal record, never an activity
  row), merge (attaches `merged_evidence`). Gating: REVIEW/UNMATCHED/invalid
  need `force=true` + reason (422), re-decisions 409, missing verification 422.
  Only approve/remap create `schedule_updates` (before/after snapshots;
  `activities` provably untouched). **APIs:** queue/decisions + 5 POST
  actions + schedule-updates + audit. **DB:** `schedule_updates`,
  `review_decisions`, `audit_events`. **Tests:** `test_review.py` (10).

## P9 Memory

- **Purpose:** approval-only learning + pattern aggregates. **File:**
  `app/memory.py`. Learns object mappings (field≠schedule), action
  reinforcement (only when equal), phrase→activity; `(project,term,type,
  value)` dedup by approval-count increment + source reports.
  `GET/POST /api/memory/vocabulary`, `GET /api/memory/patterns` (all figures
  `synthetic: true`). **DB:** `project_vocabulary` (seeded empty by principle).
  **Tests:** `test_memory.py` (9). Rejects/merges/mark-new/unreviewed/LLM teach nothing.

## P10 Time Agent

- **Purpose:** grounded Q&A with citations. **Files:** `app/time_agent.py`
  (regex router: started/completed/delayed/unmatched/explain/conflicts/
  status/unknown), `app/time_agent_tools.py` (7 read-only tools),
  LLM-or-template composer (citations appended programmatically).
  **API:** `POST /api/time-agent` (blank 422). **Tests:** `test_time_agent.py` (13).

## P11 Dashboard

- **Purpose:** 8 routed pages, dark industrial theme, zero mock data.
  **Files:** `frontend/src/pages/*.tsx` (Dashboard, FieldIntelligence,
  Linker, Review, Schedule, Memory, Audit, Agent), `components.tsx`
  (Badge/GateBadge/DecisionBanner/ScoreBar/WhyCard/PipelineStrip/ChainStrip),
  `api.ts`, `export.ts` (CSV/P6-XML-prototype downloads).
  Linker ships 3 demo presets + decision banner; Dashboard has reseed reset.

## P12 Testing & Demo Hardening

- **Purpose:** lock the three demos as E2E contracts. `tests/test_demo.py`
  (4): clean→approve→audit (+offline variant), ambiguous refusal,
  predecessor block→override. `frontend/smoke.mjs` (`npm run smoke`, 29
  checks: build artifacts, real-source export units, live-API contracts).

## P13 Final Polish

- Retry on all API errors, busy-guarded buttons, loading/empty states,
  decision banner, demo presets, responsive ≤700px, dead-scaffold removal
  (`src/assets/*`, `public/icons.svg`, `frontend/README.md`), page title,
  2-minute demo script in README. No logic changes.

## P14 Adaptive Project Vocabulary

- Approved vocabulary fires as bounded additive evidence:
  object +2.0 / action +1.5 / phrase→activity +3.0, cap +5.0
  (`matching/vocabulary_boost.py`); `score = base + bonus`, base formula and
  all downstream paths unchanged; eligibility = active + approval_count>0 +
  same project (`memory.load_active_vocabulary`); provenance `[vocab]` WHY
  lines + Linker `learned +N` badge. **DB:** `is_active` +
  `base_score`/`vocab_bonus`/`vocab_hits_json` columns via migration.
  **Tests:** `test_vocabulary_integration.py` (12).

## P15 Execution Graph Intelligence

- Read-only FS neighborhoods (`app/execution_graph.py`): preds/succs/2nd
  level/backbone strip, statuses/dates, warning kinds
  `blocked_predecessor/early_start/blocked_chain(not-started only)/
  successor_ahead` + isolation notes + stored P7 cross-reference.
  **API:** `GET /api/graph/{code}?depth=1|2&report_code=` (404s, depth clamp).
  UI: Execution Context strip on Linker/FieldIntelligence. P7 untouched.
  **Tests:** `test_execution_graph.py` (9).

## P16 Explainable Execution Risk Intelligence

- Advisory board (`app/execution_risk.py`, no tables): signals
  VERIFICATION_CONFLICT:3, CONTRADICTION:3, DEPENDENCY_RISK:2,
  SCHEDULE_VARIANCE:2, UNMATCHED_EXECUTION:1, REPEATED_EXECUTION_ISSUE:1
  (synthetic aggregates only, overrun>1d + timing issue); score capped at 10;
  ATTENTION (≥4 or conflict present) / WATCH (≥2) / NORMAL + evidence reasons.
  **APIs:** `GET /api/risk/project/{code}?level=`, `GET /api/risk/activity/{code}`.
  UI: Dashboard Attention Signals with category filter. Not ML, no probabilities.
  **Tests:** `test_execution_risk.py` (12).
