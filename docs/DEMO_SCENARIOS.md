# DEMO_SCENARIOS.md — judge flows (all inputs below are seeded synthetic data)

> Everything here runs offline with an empty `OPENROUTER_API_KEY`.
> Reset first: Dashboard → **Reset demo data** (or `POST /api/seed`).
> Linker page ships one-click chips for all three demos.

## Demo 1 — "I know this" (clean → approve → audit → learn)

- **Input:** `DPR-2026-09-18-01` — *"24 inch spool erection completed at R-204 on 18 Sep 2026."*
- **Matching:** top `PIP-204-017` (~89, margin ~10) with WHY signals; `ONE_TO_ONE`.
- **Verification:** valid; variance +6d behind plan; gate REVIEW (margin < 15 — honest, not inflated).
- **UI:** Linker shows event, candidates, WHY, granularity, gate; approve needs `force` + reason (422 without) → approved update + audit row + `erect spool→PIP-204-017` learned (Memory page).
- **Evidence:** `match_candidates` + `verification_results` + `schedule_updates` + `audit_events` rows; `activities` unchanged (still In Progress).
- **Outcome:** full FIELD→AUDIT loop closed; Time Agent can explain the link with citations.

## Demo 2 — "I don't know this yet" (ambiguous → refusal)

- **Input:** `DPR-2026-09-19-19` — *"R204 piping work completed."*
- **Matching:** tight sub-60 cluster (~52) across R-204 piping activities.
- **Granularity:** `ONE_TO_MANY`, `insufficient_evidence: true`; gate never PROPOSE.
- **UI:** Linker shows the cluster; approve without force → 422; queue shows pending.
- **Outcome:** system refuses to guess; no update, no audit change. This is the *"knows when not to automate"* moment.

## Demo 3 — "Something is wrong" (dependency conflict → attention)

- **Input:** `DPR-2026-09-18-26` — *"24 inch welding at R-204 completed on 18 Sep 2026."* (erection never started; companion `…-27` claims welding *started* 19 Sep).
- **Matching:** top `PIP-204-019`. **Graph** (`/api/graph/PIP-204-019?report_code=…`): backbone `017 → 018 → 019 → 020` with *"Reported: weld 24" completion → PIP-204-019; Required predecessor: PIP-204-018; Current predecessor state: Not Started; Result: Dependency sequence conflict → REVIEW."*
- **Verification:** dependency error naming `PIP-204-018`; gate forced REVIEW. Approving needs force + reason (audited); activity stays Not Started.
- **Risk:** `PIP-204-019` → ATTENTION (variance + dependency + verification-conflict + repeat-pattern signals); seeded contradiction row visible to the agent.
- **Outcome:** P7 blocks automation, P15 explains why, P16 keeps it on the attention board.

## P14 vocabulary demo (controlled, no fabricated gains)

1. Report A (*"24 inch pipeline erection … R-210"*, no static-alias benefit) links `PIP-210-011` @ base score, bonus 0.
2. Forced approval learns `line→spool` (+2.0) and `"erect line"→PIP-210-011` (+3.0).
3. A *different* report B (*"pipeline fit-up … R-210"*) re-runs: base score byte-identical, bonus +2.0 with `(approved x1, source)` provenance, final = base + bonus.

## Synthetic vs real

Every report, activity, date, conflict, pattern, and learned mapping above
is synthetic seed or session data, labeled as such in UI/API. Approvals,
reasons, and audit rows created live during a demo are genuine user actions.
