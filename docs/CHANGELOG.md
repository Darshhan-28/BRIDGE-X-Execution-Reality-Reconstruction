# CHANGELOG.md — P1 through P16

> Dates are not recorded in repository history; phases are ordered, not dated. Do not invent dates.

- **P1 Foundation** — FastAPI + SQLite + health endpoint; Vite+TS shell; offline-first boot. Tests: 2.
- **P2 Synthetic Project** — 1 project, 12 WBS, 55 activities, 34 FS links, 35 reports (9 categories), 8 patterns, 3 conflicts; read APIs + seed. Tests: +5.
- **P3 Field Ingestion** — text/CSV/XLSX/PDF(TM) intake, flexible headers, verbatim raw + meta; scanned PDFs explicitly flagged, no OCR. Tests: +7.
- **P4 Event Understanding** — `FieldEvent` schema; deterministic fallback parser; OpenRouter JSON adapter (1 retry → fallback, never mandatory). Tests: +12.
- **P5 Contextual Matching** — fingerprints + static aliases, TF-IDF + RapidFuzz retrieval, 8-signal weighted score, top-k, floor 45.0, WHY cards. Tests: +9.
- **P6 Granularity** — ONE_TO_ONE / ONE_TO_MANY / PARTIAL / NEW_UNPLANNED; groups never auto-complete. Tests: +8.
- **P7 Verification** — temporal/dependency/state/duplicate/contradiction + variance; gate 85/60/15, errors force REVIEW; schedule never written. Tests: +15.
- **P8 Human Review** — queue buckets, approve/reject/remap/mark-new/merge with force+reason gating; update records + full audit. Tests: +10.
- **P9 Memory** — approval-only vocabulary learning with provenance; synthetic pattern aggregates. Tests: +9.
- **P10 Time Agent** — regex router + 7 read-only tools + cited answers (LLM summarize or templates). Tests: +13.
- **P11 Dashboard** — 8 routed pages, industrial theme, real endpoints only, CSV/P6-XML exports.
- **P12 Testing & Demo Hardening** — 3 E2E demo contracts (+offline variant); `smoke.mjs` 29 checks. Tests: +4.
- **P13 Final Polish** — retries, busy guards, decision banner, demo presets, responsive pass, dead-file removal, demo script. No logic changes.
- **P14 Adaptive Project Vocabulary** — approved terms add bounded bonus evidence (+2.0/+1.5/+3.0, cap +5.0) with provenance; thresholds/gates frozen; base scores persisted. Tests: +12.
- **P15 Execution Graph Intelligence** — read-only FS neighborhoods, backbone chains, judge-readable conflict explanations; P7 authoritative. Tests: +9.
- **P16 Explainable Execution Risk Intelligence** — advisory ATTENTION/WATCH/NORMAL board from stored evidence; weights 3/3/2/2/1/1, thresholds 4/2; no probabilities, no tables, no mutations; Dashboard section. Tests: +12.

```text
Current baseline: P16
Future changes must be added below this line.
```
