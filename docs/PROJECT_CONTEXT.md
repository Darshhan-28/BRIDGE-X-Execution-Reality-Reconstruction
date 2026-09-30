# PROJECT_CONTEXT.md — complete project briefing

## Product

BRIDGE-X is an execution intelligence layer that converts messy field
evidence into verified, schedule-linked project intelligence. A planner
pastes a DPR line like *"24 inch spool erection completed at R-204"* and
gets: the understood event, ranked schedule candidates with WHY evidence,
granularity verdict, verification results, a confidence-gate decision, a
human review action, a full audit trail, learned vocabulary, and grounded
answers from a Time Agent.

## Problem

Projects are planned in structured L5/L6 schedules but executed through
messy field reports containing discipline-specific terminology,
inconsistent formats, different activity granularity, incomplete
information, and terminology mismatch (e.g. site says "pipe", schedule
says "spool"; one report covers six activities; "R204 piping done"
names no activity at all).

## Core principle

```text
AI proposes.
Deterministic verification validates.
Confidence gate controls.
Human decides.
Audit records.
Approved decisions teach.
```

## Complete pipeline

```text
FIELD REALITY
    ↓  POST /api/reports | /api/reports/analyze (text/CSV/XLSX/PDF/TXT)
INGEST
    ↓  raw text + meta preserved verbatim
UNDERSTAND
    ↓  POST /api/events/extract → FieldEvent (LLM if key, else regex fallback)
CONTEXTUAL MATCH
    ↓  POST /api/matching/run → fingerprints, TF-IDF+RapidFuzz, 8-signal score
GRANULARITY
    ↓  ONE_TO_ONE / ONE_TO_MANY / PARTIAL / NEW_UNPLANNED (groups never auto-complete)
VERIFY
    ↓  temporal, dependency, state, duplicate, contradiction + variance (P7)
CONFIDENCE GATE
    ↓  PROPOSE (≥85 + margin ≥15) / REVIEW / UNMATCHED (<60); errors force REVIEW
HUMAN REVIEW
    ↓  approve / reject / remap / mark-new / merge, force+reason gated
AUDIT + MEMORY
    ↓  every action logged; approvals teach project vocabulary
EXECUTION INTELLIGENCE
       P15 graph neighborhoods · P16 attention board · Time Agent Q&A
```

## Target use case

Industrial project controls (demo: synthetic refinery upgrade) where field
DPRs must be reconciled with a Primavera-style schedule without blindly
trusting AI matching.

## Prototype scope

Single SQLite database, single synthetic project (`BRX-DEMO-01`: 55
activities, 35 reports), CPU-only laptop, no GPU/Neo4j/embeddings/OCR.
Exports are prototype-grade (CSV/JSON/P6-XML with validate-before-import
disclaimer). See `docs/FEATURES.md` (P1–P16) and `docs/TESTING_STATUS.md`.

## Synthetic-data status

All seed content (schedules, reports, history, conflicts, vocabulary
origins) is synthetic and labeled as such in UI strings, API notes, and
docs. Planner approvals and audit trails created during a session are
real user actions, not seed data. Reseeding (`POST /api/seed`, Dashboard
reset) wipes runtime tables back to synthetic baseline.

## Offline-first behavior

With empty `OPENROUTER_API_KEY` the app runs fully: deterministic fallback
parser, template Time Agent composer, TF-IDF/RapidFuzz matching, all gates.
Verified by `test_demo1_offline_no_openrouter` and smoke's fallback checks.

## Optional LLM architecture

`backend/app/llm/`: `base.py` (FieldEvent schema + dispatch), `fallback.py`
(regex parser), `openrouter.py` (JSON-only adapter, max 2 attempts, then
fallback; never raises to callers). Model
`meta-llama/llama-3.1-8b-instruct:free`, 15 s timeout. The LLM summarizes
retrieved facts only — it never writes to the DB, never verifies, never
teaches vocabulary.

## Human-in-the-loop philosophy

Consequential decisions (schedule updates, ambiguous links, conflicts,
unplanned work) require an explicit human action with actor + reason.
`force=true` overrides are first-class, audited events — not backdoors.

## Current differentiators (P14–P16)

- **P14 Adaptive Vocabulary:** approved terminology (`pipe→spool`,
  `"erect pipe"→PIP-204-017`) adds bounded bonus evidence (+2.0/+1.5/+3.0,
  cap +5.0) with provenance on WHY cards; thresholds/gates unchanged.
- **P15 Execution Graph:** read-only FS neighborhoods, backbone chains,
  judge-readable dependency-conflict explanations; P7 stays authoritative.
- **P16 Risk Intelligence:** advisory ATTENTION/WATCH/NORMAL board from
  stored evidence only; no probabilities, no predictions.

## Explicit non-goals

ML delay prediction, schedule auto-editing, production OCR, embeddings/
vector DBs, Primavera certification, multi-project enterprise deployment,
chatbot/RAG over documents, blockchain, computer vision, local heavy models.
See `docs/DEVELOPMENT_RULES.md`.
