# API_REFERENCE.md — all routes (verified in `routers.py` + `main.py`)

Base `http://127.0.0.1:8000`. JSON unless noted. Errors: 404 unknown,
422 bad input, 409 no-seed / re-decide.

## System / Demo-Seed

- `GET /api/health` → `{status, app, version, database, llm, message}`. No side effects.
- `GET /` → `{app, docs, health}`.
- `POST /api/seed` → counts `{projects, wbs_nodes, activities, relationships, reports, execution_patterns, conflicts}` + `oil_knowledge {sources, terms}`. **Wipes runtime tables** (safe: synthetic baseline restore; `source_documents`/`domain_terms` upserted, never wiped).

## Projects / Schedule / Dashboard / Conflicts (read-only)

- `GET /api/projects` → `[{code, name}]`.
- `GET /api/activities?discipline=` → activity rows.
- `GET /api/activities/{code}` → row + `predecessors[]`, `successors[]`.
- `GET /api/reports?category=` → report rows (raw verbatim + meta).
- `GET /api/conflicts` → seeded conflict rows.
- `GET /api/dashboard` → counts + `activities_by_discipline/status`, `reports_by_category`, `synthetic: true`.

## Field Reports (ingestion writes reports only)

- `POST /api/reports` 201 — `{raw_text*, source, discipline, location, report_date, category, meta}` → report (`TXT-`/`ING-` code). Blank text 422.
- `POST /api/reports/analyze` — multipart file (csv/xlsx/xls/pdf/txt) → `{inserted, report_codes[], warnings[], ocr_required}`. Scanned PDF → `inserted: 0` + OCR warning. Bad type/empty → 400.

## Matching (writes candidates + verification rows, never schedule)

- `POST /api/events/extract` 201 — `{report_code | raw_text*, report_date, discipline, location, prefer}` → `{id, event, domain_provenance[]}` (FieldEvent, persisted; REAL_PUBLIC terminology context goes to the LLM only, fallback never sees it). Unknown report 404.
- `GET /api/events?report_code=` → stored events.
- `POST /api/matching/run` 201 — `{report_code | event | raw_text, ..., prefer (default fallback), top_k (1–10)}` → `{report_code, event, candidates[], unmatched, reason, granularity, verification}`. Missing target 404/422; empty DB 409.
- `GET /api/matching/{report_code}` → latest run (granularity + verification recomputed from stored rows). No run 404.

## Verification

No standalone endpoint; verification rides on match-run responses and
`verification_results` rows (read via review/agent/risk flows). P7 is
invoked server-side only — there is no "verify anything" public tool.

## Review (the only consequential writes; all audited)

- `GET /api/review/queue?bucket=` → items `{report_code, bucket, gate, granularity_type, top_activity/score, margin, event_type/date, verification_valid/errors, decision{state,target,actor,reason}}`, sorted CONFLICT→UNMATCHED.
- `GET /api/review/decisions?report_code=` → decision rows.
- `POST /api/review/approve` 201 — `{report_code*, actor, reason, force}` → `{update_id, forced, after}` (+`vocabulary_learned`). 422 if no verification/target, or gate≠PROPOSE/invalid without `force+reason`. 409 if already decided.
- `POST /api/review/reject` 201 — reason required (422); no update created.
- `POST /api/review/remap` 201 — +`activity_code*`; re-verifies target (422 if invalid without force); 404 unknown activity.
- `POST /api/review/mark-new` 201 — +`activity_name?`; proposal record only, never an activity row.
- `POST /api/review/merge` 201 — +`into_report_code*`; attaches `merged_evidence`; reason required.
- `GET /api/schedule-updates?report_code=` → approved records with before/after.
- `GET /api/audit?report_code=&action=` → audit trail (JSON export in UI).

## Memory

- `GET /api/memory/vocabulary?discipline=&term=` → learned terms with counts/evidence.
- `POST /api/memory/vocabulary` 201 — planner-curated `{term*, canonical_type, canonical_value*, discipline, actor}`; repeats reinforce (count+1). Bad type/blank 422.
- `GET /api/memory/patterns` → synthetic aggregates + live delays, all `synthetic: true`.

## Public OIL knowledge (REAL_PUBLIC, context only — never execution data)

- `GET /api/knowledge/sources` → source documents with full provenance.
- `GET /api/knowledge/terms?q=&category=` → domain terms (ranked retrieval with `q`, else alphabetical) with per-item provenance. See `OIL_PUBLIC_DATA.md`.
- `GET /api/knowledge/lookup?q=` → exact-term provenance ("where did this OIL term come from?"). Blank 422.
- `POST /api/knowledge/promote` 201 — explicit human `{term_id*, canonical_type, canonical_value, actor, reason*}` → curated vocabulary + `promote_knowledge` audit row. Missing reason 422, unknown term 404.

## Time Agent / Graph / Risk (all read-only)

- `POST /api/time-agent` — `{question*}` → `{answer, citations[], intent, tools_used[], composer}`. Blank 422.
- `GET /api/graph/{code}?depth=1|2&report_code=` → neighborhood + chain checks + stored P7 reference. Unknown 404, depth clamped.
- `GET /api/risk/project/{code}?level=` → `{project_code, item_count, summary, items[], note}`. Unknown project 404.
- `GET /api/risk/activity/{code}` → single item. Unknown 404.
