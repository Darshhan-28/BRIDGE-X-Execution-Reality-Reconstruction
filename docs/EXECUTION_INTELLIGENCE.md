# EXECUTION_INTELLIGENCE.md — P15 graph + P16 risk (read-only, advisory)

> Describe this as **explainable execution intelligence / attention
> signals**, NOT a validated predictive ML model. No probabilities, no
> accuracy claims, no "chance of delay" anywhere in code, tests, or UI.

## P15 — Execution Graph Intelligence (`app/execution_graph.py`)

Builds a deterministic local neighborhood from existing schedule data —
no duplicate data, no new tables, no LLM, CPU-only.

- **Construction:** activity itself + all immediate FS predecessors and
  successors + optional 2nd level (`?depth=1|2`, clamped to 2), each with
  code/name/status/progress/planned/actual dates/rel-type/`via`.
- **Backbone:** ordered strip walking first-by-code FS links
  (e.g. `PIP-204-017 → 018 → 019 → 020`); multi-predecessor merges show
  one strip plus full pred/succ lists (no inference invented).
- **Warning kinds** (each names codes + `rel_type: FS` + status/date
  evidence): `blocked_predecessor` (reported-complete vs unfinished pred →
  judge-readable *"Reported: … → X; Required predecessor: Y; Current
  predecessor state: …; Result: Dependency sequence conflict → REVIEW"*),
  `early_start`, `blocked_chain` (not-started preds only), `successor_ahead`
  (finished successor while self unfinished, from stored actuals), plus
  isolation notes and a read-only `latest_review` P7 cross-reference.
- **API:** `GET /api/graph/{code}?depth=&report_code=` (404s; proposal
  derived from the stored event). **UI:** Execution Context strip on
  Linker/FieldIntelligence for the top candidate. Time Agent untouched
  (endpoint shaped for later reuse).

## P16 — Explainable Execution Risk Intelligence (`app/execution_risk.py`)

Advisory board derived live; SELECTs only.

- **Categories:** `SCHEDULE_VARIANCE` (late finish / overdue-incomplete with
  day counts), `DEPENDENCY_RISK` (reused P15 structural warnings),
  `VERIFICATION_CONFLICT` (stored P7 failure cited), `UNMATCHED_EXECUTION`
  (below-gate links + unlinked reports), `CONTRADICTION` (conflict rows
  naming the activity + unlinked conflict items), `REPEATED_EXECUTION_ISSUE`
  (only when same-discipline synthetic aggregates overrun >1d AND a timing
  issue exists; always labeled synthetic).
- **Tally (not a model):** weights 3/3/2/2/1/1, cap 10 →
  **ATTENTION** (≥4 or conflict present) / **WATCH** (≥2) / **NORMAL**,
  each with reasons, variance, dates, and evidence IDs.
- **APIs:** `GET /api/risk/project/{code}?level=` (61 items on seed:
  55 activities + 3 unmatched + 3 conflicts; unknown project 404),
  `GET /api/risk/activity/{code}`. **UI:** Dashboard Attention Signals
  with per-category filter.
