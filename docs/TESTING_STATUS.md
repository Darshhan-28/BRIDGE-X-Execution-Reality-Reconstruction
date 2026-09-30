# TESTING_STATUS.md — current actual status (verify, don't trust blindly)

## Backend (`backend/`, `.venv` Python 3.13)

- **138 tests, all green** across 15 files (counted 2026-09-22 via
  `Select-String '^def test_'`): demo 4, events 12, execution_graph 9,
  execution_risk 12, granularity 8, health 2, ingestion 7, matching 9,
  memory 9, review 10, seed 5, time_agent 13, verification 15,
  vocabulary_integration 12, oil_public_data 11.
- Command: `py -m pytest -q` (from `backend/` with `.venv` active).
- Style: behavior-pinning, not magic numbers (ordering/margins/evidence,
  never hardcoded exact scores); mocked transports for all LLM paths;
  rollback-isolated mutation probes; read-only proofs via table counts.
- Known warnings (cosmetic): Starlette anyio deprecation, PyMuPDF SWIG
  `__module__`, PowerShell em-dash glyph.

## Frontend (`frontend/`, Node 24)

- `npm run build` = strict `tsc -b` + Vite build clean (36 modules).
- `npm run smoke` (`smoke.mjs`): **29 checks green** — 2 build artifacts,
  6 export unit tests (real `export.ts` compiled via installed tsc: CSV
  header/quoting, P6 disclaimer/rows/escaping), 21 live-API contracts
  (reseeds dev DB, runs all 3 demos, gating 422s, queue, vocab, patterns,
  cited agent, conflicts). Needs backend on `:8000`.
- No browser-automation tests; logic is covered backend-side.

## Intentionally synthetic tests

Seed counts, seeded conflicts/duplicates/contradictions, execution
patterns, and vocabulary-learning fixtures are synthetic by design and
asserted as such (e.g. `synthetic: true` flags, reseed wipes).

## Limitations (honest)

- UI states (loading/retry/empty) are verified by code review + smoke
  contracts, not DOM tests.
- Relative words ("yesterday") resolve against wall-clock date; demos use
  explicit dates for reproducibility.
- Overdue-driven variance grows with wall-clock time vs 2026 seed dates.

## Last verified

Full suite + build + smoke green at P16 completion. Re-run the three
commands above after any meaningful change; never weaken/delete tests to
make a feature pass.
