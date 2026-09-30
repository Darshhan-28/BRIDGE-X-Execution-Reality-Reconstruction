# OIL_PUBLIC_DATA.md — real public Oil India material (provenance, no fabrication)

> Public terminology reference only. Nothing here is a DPR, a schedule,
> an activity, an execution date, progress, or an operational record.
> Public documents never become field execution data in BRIDGE-X.

## Actual public sources used (4 fetched first-hand)

| source_id | Title | Publisher | URL | Publication date | Retrieved | Type | Local file |
|---|---|---|---|---|---|---|---|
| OIL-MIDSTREAM-20260325 | Midstream \| Oil India Limited (Pipeline - The Energy Highway) | Oil India Limited | https://www.oil-india.com/integrated-energy-company/midstream | 2026-03-25 (page header "Last Updated 25/03/2026") | 2026-09-22 | official webpage | backend/data/oil_public/oil_midstream_page.html |
| OIL-INVESTOR-TRANSCRIPT-20260529 | Transcript of Analysts' and Investors' Meet on 25th May, 2026 | Oil India Limited | https://www.oil-india.com/files/investor_services_documents/2a520951_8bd3_4612_92b2_5e1b1ca8af5b.pdf | 2026-05-29 (meet 25 May 2026; forwarded to NSE/BSE under SEBI LODR) | 2026-09-22 | official investor transcript (PDF, 30 pages) | backend/data/oil_public/oil_investor_meet_transcript_2026-05-29.pdf |
| OIL-NIT-CDG5545P24 | E-Tender No. CDG5545P24 Forwarding Letter (Charter Hire drilling rigs) | Oil India Limited, Contracts Department, Duliajan | https://www.oil-india.com/files/oldtender/global/NIT_CDG5545P24.pdf | 2024-02 (bid closing 29.02.2024) | 2026-09-22 | official tender document (PDF, 385 pages; curated from first 60) | backend/data/oil_public/oil_nit_CDG5545P24.pdf |
| OIL-TENDER-LIST-202609 | OIL National Tenders list snapshot (tender-list/63) | Oil India Limited | https://www.oil-india.com/tender-list/63 | none (live listing snapshot; listed tenders dated Aug–Oct 2026; titles change over time) | 2026-09-22 | official tender listing snapshot | backend/data/oil_public/oil_tender_list_national.html |

## What was actually extracted (49 curated terms)

49 rows in `domain_terms`, each a verbatim snippet observed in its source
(see `backend/seed/oil_public_data.py` TERMS). By source:

- Midstream page (21): trunk pipeline, pumping station, repeater station,
  prime mover engines, cathodic protection system, river crossings,
  micro-tunnelling, coating refurbishment, pigging stations,
  OFC based communication network, MMTPA, NSPL, DNPL, Duliajan,
  Numaligarh, Guwahati, Bongaigaon, Barauni, Siliguri, augmentation,
  commissioned.
- Investor transcript (7): mechanical completion, physical completion,
  ROU acquired, commissioning, capacity expansion, MMSCMD, shutdown.
- NIT CDG5545P24 (12): Charter Hire, Drilling Rig Package, 2000 HP,
  Mobilization Time, Operating Day Rate, Draw-works, mast and
  sub-structure, IFB, ICB, Bid Security, Demobilization Charges,
  Duliajan Assam headquarters.
- Tender-list snapshot (9): Well plinth, CC/RCC Foundation, PEB Roof,
  EOT Crane, VFD Rig, Tengakhat, Chabua, Dibrugarh district,
  Engineering Procurement Construction and Commissioning.

No DPRs, no schedules, no activities, no execution dates, no progress
were extracted — terminology and specification vocabulary only.

## Provenance mechanism

- `source_documents` (one row per source above): `source_id`, `title`,
  `publisher`, `source_url`, `publication_date`, `retrieved_at`,
  `document_type`, `local_file`, `checksum` (sha256 of the fetched file),
  `source_type='REAL_PUBLIC'`, `notes`.
- `domain_terms` (one row per term): `source_id`, `term`, `category`,
  `context_snippet` (verbatim), `section_ref`, `extra_json`.
- Retrieval (`app/domain_knowledge.py`): deterministic token-overlap
  ranking over REAL_PUBLIC terms only; every hit returns full source
  provenance including `source_type='REAL_PUBLIC'`, title, URL,
  publisher, publication/publication-retrieval dates.
- LLM context only: `POST /api/events/extract` builds a domain context
  block for the OpenRouter model when `prefer != fallback` and a key is
  configured, and returns `domain_provenance` alongside the event. The
  deterministic fallback parser never sees this context, so offline
  output is byte-identical with or without knowledge loaded.
- Promotion is an explicit human act: `POST /api/knowledge/promote`
  requires actor + reason, routes through the same curated vocabulary
  path as manual terms, and writes a `promote_knowledge` audit row.
  Unpromoted terms never influence matching.
- Endpoints: `GET /api/knowledge/sources`, `GET /api/knowledge/terms`,
  `GET /api/knowledge/lookup`, `POST /api/knowledge/promote`.
- `POST /api/seed` loads synthetic fixtures + upserts OIL knowledge
  (idempotent; `run_seed` never wipes `source_documents`/`domain_terms`).

## What public OIL data does NOT provide

- No field DPRs, no daily progress, no execution dates, no % complete.
- No schedule network, no planned/actual dates, no resource data.
- No site-level operational records of any kind.
- Therefore: no matching evidence, no verification input, no gate
  input, no review target, and no execution-intelligence signal is ever
  derived from public documents. P7 stays authoritative, P15 stays
  evidence/context only, P16 stays advisory.

## Excluded (fetched but NOT integrated, on purpose)

- `backend/data/oil_public/pngrb_iggl_authorization_2026-02-26.pdf`
  (PNGRB IGGL authorization): scanned images, zero extractable
  characters — excluded per the no-OCR constraint.
- Search-result snippets (tender titles seen only in search excerpts):
  provenance too weak; only terms from directly fetched files stored.

## Exact distinction

| Class | Lives in | Label | Meaning |
|---|---|---|---|
| REAL_PUBLIC | `source_documents` + `domain_terms` | `source_type='REAL_PUBLIC'` | Public Oil India terminology reference with provenance. Context for the LLM only. Never execution data. |
| SYNTHETIC | `field_reports` (DPR-*), `activities`, `execution_history`, etc. | `source_type='SYNTHETIC'`, `synthetic=1`, UI `synthetic` badges | Regression/demo fixtures. Retained so the full P1–P16 suite keeps proving behavior. Never presented as real. |
| USER_PROVIDED | `field_reports` (TXT-*/ING-*) created via `POST /api/reports` or `/analyze` | `source_type='USER_PROVIDED'` | Planner-pasted or uploaded field evidence for the live pipeline. The only field execution input. |

Rules enforced in code and tests (`tests/test_oil_public_data.py`):
no `field_reports` row with `REAL_PUBLIC`; synthetic seed keeps 35
DPR fixtures; ingestion defaults to `USER_PROVIDED`; knowledge load is
idempotent and never creates reports; fallback output is identical with
or without domain context.
