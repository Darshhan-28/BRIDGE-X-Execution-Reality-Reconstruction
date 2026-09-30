# AI_START_HERE.md — read this first

> Before modifying code, read AI_START_HERE.md and DEVELOPMENT_RULES.md.
> Do not implement future features or invent new architecture unless the user explicitly requests it.

## What BRIDGE-X is

One-line definition: **BRIDGE-X is an AI-assisted execution-intelligence layer that converts messy field evidence into verified, schedule-linked project intelligence.**

Field reports (free text, CSV/XLSX, PDF) arrive in inconsistent site language.
BRIDGE-X understands them, links them to L5/L6 schedule activities, verifies
the link against schedule logic, gates automation by confidence, routes
everything consequential to a human planner, audits every decision, learns
project vocabulary only from approvals, and answers grounded questions —
all offline-capable on a CPU-only laptop.

## Core flow

```text
FIELD → INGEST → UNDERSTAND → MATCH → GRANULARITY → VERIFY → GATE
  → HUMAN REVIEW → AUDIT + MEMORY → EXECUTION INTELLIGENCE (graph, risk, agent)
```

Governing principle: **AI proposes. Deterministic verification validates.
Confidence gate controls. Human decides. Audit records. Approved decisions teach.**

## Current status

- **Baseline P1–P16 complete and frozen.** Current feature boundary: **P16**.
  Backend `0.16.0-p16` (`backend/app/config.py`). Do not begin P17 or invent
  differentiators unless the project owner explicitly instructs it.
- Backend: **127 pytest tests green** (`backend/tests/`, 14 files).
- Frontend: strict `tsc -b` + Vite build clean; `npm run smoke` 29/29 checks green.
- All demo/seed data is **synthetic** (never real Oil India data).

## Stack

Backend `backend/`: FastAPI 0.116 + SQLAlchemy 2.0 + SQLite (`bridge_x.db`),
pydantic-settings, httpx, pandas/openpyxl, PyMuPDF, scikit-learn, RapidFuzz,
python-multipart, pytest. Frontend `frontend/`: React 19 + Vite 8 + TypeScript
+ react-router-dom. Ports: API `:8000`, UI `:5173` (`VITE_API_URL` override).

## Architectural principles (non-negotiable)

1. **P7 verification is authoritative.** Never replace deterministic checks with an LLM.
2. **Offline-first.** Core works with empty `OPENROUTER_API_KEY` (fallback parser + templates).
3. **Scores propose nothing alone.** Gate + verification + human `force+reason` required.
4. **Schedule is never silently overwritten.** `activities` is read-only to the pipeline; only `schedule_updates` records + human approval.
5. **Only eligible human-approved decisions teach vocabulary** (approve/remap/curated POST).
6. **No fabricated numbers.** No probabilities, no accuracy claims, no predictions. P16 is advisory attention, not ML.
7. **Synthetic stays labeled** as synthetic everywhere.

## Read next (in order)

1. `docs/DEVELOPMENT_RULES.md` — strict modification rules + feature freeze
2. `docs/PROJECT_CONTEXT.md` — full briefing
3. `docs/ARCHITECTURE.md` — modules, determinism map, diagram
4. `docs/API_REFERENCE.md` + `docs/DATA_MODEL.md` — contracts and schema
5. `docs/MATCHING_ENGINE.md`, `docs/VERIFICATION_ENGINE.md` — the two engines
6. `docs/DEMO_SCENARIOS.md` — reproduce the three demos first

## Testing expectations

- After meaningful backend changes: `py -m pytest -q` in `backend/` (must stay 127+, never weaken tests).
- After frontend changes: `npm run build` in `frontend/`; with backend running: `npm run smoke`.
- Setup: `docs/PROJECT_CONTEXT.md` (run/test section) and repo `README.md`.
