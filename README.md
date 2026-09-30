# BRIDGE-X — AI Planning-to-Execution Intelligence Layer

> **Synthetic demonstration data — not real Oil India data.**
> AI proposes. Verification validates. Humans control consequential decisions.

## Phase 16 — Execution Risk Intelligence (current)

`GET /api/risk/project/{code}?level=` and `GET /api/risk/activity/{code}`
return advisory ATTENTION / WATCH / NORMAL items derived live from
schedule variance, P15 graph warnings, P7 verification errors, unmatched
evidence, conflict rows, and synthetic history aggregates — no new
tables, no probabilities, no predictions, no mutations. The Dashboard
shows a compact Attention Signals section with per-category filtering.

`GET /api/graph/{code}?depth=1|2&report_code=` returns the deterministic
local execution neighborhood (activity, predecessors, successors, second
level, ordered backbone chain) with statuses, dates, FS relationship
types, stored-state checks (successor-ahead, not-started chain,
isolation) and, with a report, event-vs-order checks whose messages name
codes, states, and the REVIEW result. Read-only CPU-only; P7 stays
authoritative. Linker and Field Intelligence show an Execution Context /
Dependency Chain strip for the top candidate.

## Phase 15 — Execution Graph Intelligence

## Phase 14 — Adaptive Project Vocabulary

Human-approved vocabulary now contributes bounded bonus evidence to
future linking (`score = base 8-signal score + vocab bonus`, cap +5.0):
object (+2.0), action (+1.5), and phrase→activity (+3.0) hits, each with
approval-count/source-report provenance on WHY cards and a `learned +N`
badge in the Linker. Only active, approved, same-project rows fire;
thresholds, margins, granularity, verification, and gates are unchanged
and still apply. Base scores are persisted separately for audit.

## Phase 11 — Dashboard UI (current)

Dark industrial React + Vite + TS app (`frontend/`, `npm run dev` on
:5173, API at :8000 or `VITE_API_URL`): Dashboard (live counts, pipeline
strip, queue buckets, audit tail), Field Intelligence (paste/upload →
ingest → full pipeline view), Schedule Linker (top-3, margin, WHY signal
cards, granularity, verification, gate), Review Queue (real
approve/reject/remap/mark-new/merge with force+reason gating), Schedule
(planned-vs-actual Gantt + CSV/JSON/P6-XML-prototype exports with a
validate-before-import disclaimer), Project Memory (learned terms +
synthetic patterns, all labeled), Audit (filterable timeline + JSON
export), Time Agent (chat with evidence citations). No mock data, no
fake buttons — every control hits a real endpoint.

`POST /api/time-agent` answers grounded questions via a deterministic
intent router and read-only DB tools (started/completed on a date,
delayed, unmatched, explain-link, conflicts, activity status). Every
answer carries report_id/activity_id evidence citations; unknown
questions and empty evidence get graceful guidance, never invention.
OpenRouter only summarizes retrieved facts (1 retry, then templates);
without a key the template composer answers fully offline. The LLM has
no database access and cannot trigger writes. Dashboards and UI arrive
in Phase 11.

Approvals teach: `approve`/`remap` derive object/phrase mappings
(e.g. pipe→spool, "erect pipe"→PIP-204-017) into `project_vocabulary`
with approval counts + source-report evidence (`GET /api/memory/vocabulary`,
planner-curated `POST`, duplicates reinforce instead of duplicating).
Nothing is learned from raw LLM output or unreviewed matches.
`GET /api/memory/patterns` aggregates synthetic execution history
(planned-vs-actual, overruns, common issues) plus live schedule delays —
every figure labeled synthetic, never real project data. Conversational
Time Agent arrives in Phase 10.

`GET /api/review/queue` (buckets HIGH/MEDIUM/LOW/CONFLICT/UNMATCHED) plus
five explicit actions: `POST /api/review/{approve,reject,remap,mark-new,merge}`.
Only approvals create `schedule_updates` — as approved records with
before/after snapshots that never touch the `activities` table. Gate
PROPOSE + valid verification approves cleanly; REVIEW/UNMATCHED/invalid
cases need `force=true` plus a written reason (else 422), re-decisions
need force (else 409). Every action writes an `audit_events` row
(`GET /api/audit`) with actor, action, IDs, before/after, timestamp and
reason. Project memory (vocabulary + execution patterns) arrives in
Phase 9.

Every match run now carries `verification`: six deterministic checks
(temporal, predecessor/dependency, state-machine, duplicate,
contradiction, plus planned-vs-actual variance) with all evidence and
reasons preserved, persisted to `verification_results`. The gate uses
`config.py` thresholds — HIGH ≥85 + margin ≥15 → PROPOSE, 60–85 or
margin <15 → REVIEW, <60 → UNMATCHED — and any verification error
forces REVIEW. Nothing is applied to the schedule; human review of
consequential decisions arrives in Phase 8.

Every match run now carries a `granularity` verdict: `ONE_TO_ONE`
(decisive specific evidence → propose completion), `PARTIAL` (explicit
% → propose progress only, never completion), `ONE_TO_MANY` (broad
report over an activity cluster → insufficient evidence, planner review,
group must NEVER be auto-completed), or `NEW_UNPLANNED` (below retrieval
floor → propose a new activity). Pure deterministic logic on the
FieldEvent + ranked candidates — no LLM. Verification gates and human
review arrive in Phases 7–8.

`POST /api/matching/run` (by `report_code`, inline `event`, or raw text;
`GET /api/matching/{report_code}` reloads the run) consumes the Phase-4
`FieldEvent` — never the LLM — and returns top-k candidates with scores,
8-signal breakdowns and WHY lines. Retrieval is TF-IDF + RapidFuzz with
structured pre-filters; scoring uses the configured weights in
`config.py`; terminology aliases (pipe→spool, joint→weld) bridge wording
gaps. Below-floor results are flagged `unmatched`. Granularity,
verification gates and review arrive in Phases 6–8.

`POST /api/events/extract` (by `report_code` or inline `raw_text`,
`prefer: auto|llm|fallback`) returns a Pydantic-validated `FieldEvent`
(action, object, size/tag, location, discipline, dates, status/progress,
evidence + source report_id) and persists it to `extracted_events`
(`GET /api/events`). Deterministic fallback parser (abbreviations,
synonyms, yesterday/date resolution) keeps everything working with no
API key; OpenRouter adapter (`meta-llama/llama-3.1-8b-instruct:free`,
JSON-only, 1 retry then fallback) activates when `OPENROUTER_API_KEY`
is set. Time Agent proper arrives in Phase 10.

`POST /api/reports` (single free-text JSON) and
`POST /api/reports/analyze` (CSV / XLSX / PDF / TXT upload).
Flexible spreadsheet headers (`Day/Disc/Site/Narration/...`), raw text
always preserved verbatim, metadata kept in `meta` JSON.
PDFs are PyMuPDF text-extraction only — scanned PDFs return
`inserted: 0` with an explicit `Prototype / OCR required` warning
(`ocr_required: true`); no OCR dependency. New `meta` column is
auto-migrated into existing `bridge_x.db` on startup/seed.

1 project (BRX-DEMO-01), 12 WBS nodes, 55 activities
(Piping 16 / Civil 11 / Electrical 10 / Mechanical 9 / Instrumentation 9),
34 FS relationships, 35 field reports across 9 categories
(clean/mismatch/abbreviation/incomplete/ambiguous/duplicate/
contradiction/partial/unmatched), 8 execution patterns, 3 seeded conflicts.
All synthetic — not real Oil India data.

```powershell
# seed / reseed (venv active, in backend/)
py -m seed.synthetic_project
# or: POST http://127.0.0.1:8000/api/seed
# verify: GET http://127.0.0.1:8000/api/dashboard
```

## Setup (Windows 11, `py` launcher)

```powershell
# backend
Set-Location D:\SIH26122\backend
Copy-Item .env.example .env
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m uvicorn app.main:app --reload --port 8000
# health: http://127.0.0.1:8000/api/health  docs: /docs

# backend tests (new terminal, venv active)
Set-Location D:\SIH26122\backend
py -m pytest -q

# frontend
Set-Location D:\SIH26122\frontend
npm install
npm run dev
# http://localhost:5173  (expects API at http://127.0.0.1:8000)

# frontend smoke (backend must be running; reseeds dev DB, runs demos)
Set-Location D:\SIH26122\frontend
npm run smoke
```

## 2-minute demo script

Reset first: Dashboard → **Reset demo data** (or `POST /api/seed`).

1. **Clean match.** Linker → **Demo: Clean match** (`DPR-2026-09-18-01`):
   erect/spool/24"/R-204 → `PIP-204-017`, WHY signals, `ONE_TO_ONE`,
   verification passes (+6d variance), gate REVIEW on margin.
   Review Queue → approve with force + reason → audit trail + learned
   vocabulary (`erect spool` → `PIP-204-017` in Memory).
2. **Ambiguous.** Linker → **Demo: Ambiguous** (`DPR-2026-09-19-19`):
   tight sub-60 cluster → `ONE_TO_MANY`, insufficient evidence,
   group is never auto-completed. This is BRIDGE-X refusing to guess.
3. **Contradiction.** Linker → **Demo: Dependency error**
   (`DPR-2026-09-18-26`): welding reported complete while predecessor
   `PIP-204-018` never started → verification error forces REVIEW.
   Time Agent → *"What conflicts were detected?"* for cited evidence.

Everything above runs with no API key (fallback-only mode).

## Env

See `backend/.env.example`. Never commit `.env` or real keys.
Default model: `meta-llama/llama-3.1-8b-instruct:free`.
