# ARCHITECTURE.md — actual architecture (verified against code)

## Backend (`backend/app/`, FastAPI + SQLAlchemy + SQLite)

| Module | Responsibility |
|---|---|
| `main.py` | App, lifespan (`create_all` + `ensure_columns`), health `/`, CORS for :5173 |
| `config.py` | `Settings` (.env): versions, DB URL, OpenRouter, 8 matching weights, 3 gate thresholds |
| `db.py` | Engine, `SessionLocal`, `get_db`, additive `ensure_columns()` migration |
| `models.py` | 16 tables (see `DATA_MODEL.md`: 14 pipeline + `source_documents`/`domain_terms` REAL_PUBLIC reference) |
| `routers.py` | All ~31 REST routes (see `API_REFERENCE.md`) |
| `ingestion.py` | Text/CSV/XLSX/PDF parsing, header aliases, date normalization, report codes |
| `llm/base.py` | `FieldEvent` schema + `extract_field_event()` dispatch + agent delegate |
| `llm/fallback.py` | Deterministic regex event parser (offline core) |
| `llm/openrouter.py` | JSON-only LLM adapter, 2 attempts → fallback, `_post` seam for tests |
| `matching/fingerprint.py` | Static alias canonicalization + fingerprint builder |
| `matching/candidate_retrieval.py` | TF-IDF cosine + RapidFuzz + structured pre-filters, top-10 |
| `matching/scorer.py` | 8-signal weighted score, `UNMATCHED_FLOOR=45.0`, `match_event()` |
| `matching/granularity.py` | ONE_TO_ONE / ONE_TO_MANY / PARTIAL / NEW_UNPLANNED resolver |
| `matching/vocabulary_boost.py` | P14 bounded learned-vocabulary bonus + provenance |
| `verification/` | 5 checks + variance + gate + `pipeline.verify_proposal()` (P7, authoritative) |
| `review.py` | Queue buckets, 5 gated actions, audit writer, learning hook |
| `memory.py` | Approval-only vocabulary learning + synthetic pattern aggregates |
| `time_agent.py` / `time_agent_tools.py` | Regex intent router + 7 read-only DB tools + LLM/template composer |
| `execution_graph.py` | P15 read-only FS neighborhoods + chain checks |
| `execution_risk.py` | P16 advisory attention board, derived live, no tables |
| `seed/synthetic_project.py` | Idempotent synthetic dataset (1/12/55/34/35/8/3) |
| `seed/oil_public_data.py` | Idempotent REAL_PUBLIC knowledge load (4 sources, 49 terms; never DPRs/schedule) + `domain_knowledge.py` keyword retrieval (LLM context only, fallback untouched) |

## Frontend (`frontend/src/`, React 19 + Vite 8 + TS + react-router-dom)

Routes (`App.tsx`): `/` Dashboard, `/field` FieldIntelligence,
`/linker` Linker, `/review` Review, `/schedule` Schedule, `/memory` Memory,
`/audit` Audit, `/agent` Agent (+ `*` fallback). Shared `components.tsx`
(Badge, GateBadge, DecisionBanner, ScoreBar, WhyCard, PipelineStrip,
ChainStrip, Loading, ErrorBox, Empty). `api.ts` is a thin typed fetch
client (`VITE_API_URL || http://127.0.0.1:8000`); `export.ts` builds
CSV/P6-XML downloads client-side. `smoke.mjs` runs build-artifact,
real-source export, and live-API contract checks.

## Processing flow (field report → intelligence)

1. **Ingest** → `field_reports` row (raw verbatim + meta, `source_type` SYNTHETIC|USER_PROVIDED).
2. **Understand** → `FieldEvent` (LLM or fallback) → `extracted_events`.
3. **Match** → fingerprints → candidates (top-k, default 3) → `match_candidates`.
4. **Granularity** → shape verdict attached to the run.
5. **Verify + gate** → P7 result → `verification_results`.
6. **Review** → human action → `schedule_updates` (records only) + `review_decisions` + `audit_events` + vocabulary learning.
7. **Intelligence** → graph neighborhoods, risk board, agent answers — all read from the above.

REAL_PUBLIC side flow (reference only, never execution):
`source_documents`/`domain_terms` → keyword retrieval → OpenRouter LLM
context + `domain_provenance` → existing understand/match/verify/review
pipeline unchanged. Fallback never sees domain context. Details:
`OIL_PUBLIC_DATA.md`.

## ASCII diagram

```text
                +------------------+     +------------------+
                |  Field evidence  |     | L5/L6 schedule   |
                | text/csv/xlsx/pdf|     | 55 acts, 34 FS   |
                +--------+---------+     +--------+---------+
                         v                        v
                +--------+------------------------+---------+
                | INGEST (verbatim)  UNDERSTAND (LLM|regex)|
                +--------+------------------------+---------+
                         v
              +----------+-----------+      +----------------+
              | MATCH (TF-IDF+fuzz, | ---> | learned vocab  |
              | 8 signals, +bonus)  | <--- | (approved only)|
              +----------+-----------+      +----------------+
                         v
              GRANULARITY -> VERIFY (P7) -> GATE (85/60/15)
                         v
              +----------+-----------+      +----------------+
              | HUMAN REVIEW (5 acts)| ---> | audit + memory |
              +----------+-----------+      +----------------+
                         v
          +--------------+---------------+------------------+
          v              v               v                  v
   Dashboard/UI   Graph (P15)     Risk board (P16)   Time Agent
```

## Component properties (do not invent others)

| Component | Deterministic | LLM-assisted | Read-only | Write-capable | Human-controlled |
|---|---|---|---|---|---|
| Ingestion, fallback parser | yes | no | writes reports only | reports | no |
| OpenRouter adapter | no | yes | no network writes to DB | no | no |
| Matching (+P14 bonus) | yes | no | reads | match/verification rows | no |
| Granularity, P7, gate | yes | no | reads | verification rows | no |
| Review actions | yes | no | — | updates/decisions/audit/vocab | **yes (actor+reason)** |
| Memory learning | yes | no | — | vocabulary (approvals only) | **yes** |
| Graph, risk, agent tools | yes | agent composes only | **yes** | none | no |

There are no embeddings, vector DBs, background workers, or external
services in the architecture. The heaviest compute is demo-time.
