# EVALUATOR GUIDE — BRIDGE-X in 7 minutes

> All inputs below are seeded synthetic data. Reset first: Overview → **Reset demo data** (or `POST /api/seed`). Everything runs offline with no API key.

## 2-minute demo (exact clicks)

1. Open `http://localhost:5173` → **Overview** (55 activities, 35 reports, queue buckets).
2. Go to **Reconciliation** → click **Demo: Clean match** (`DPR-2026-09-18-01`).
3. Read the trail: FIELD EVIDENCE → EXECUTION EVENT → top CANDIDATE `PIP-204-017` + WHY cards → `ONE_TO_ONE` → verification valid (+6d variance) → gate REVIEW (margin <15, honest).
4. Go to **Planner Decision** → open `DPR-2026-09-18-01` → **Approve** without reason/force → see the **422 refusal** → check force + write a reason → Approve → authorized actual + audit row.
5. Go to **Project Memory** → `erect spool → PIP-204-017` learned; **Audit Trail** → your action with actor + reason + timestamp.

## 5-minute technical walkthrough (what to show and why)

| Minute | Show | Why it matters |
|---|---|---|
| 1 | Overview + Schedule Gantt | Planned L5/L6 reality vs field mess |
| 2 | Field Evidence: paste a DPR line → Understand → Link → Verify | Evidence → event, not report → activity |
| 3 | Reconciliation WHY cards + margin + granularity | Explainability + refusal to guess |
| 4 | Verification errors + graph backbone + risk ATTENTION | Dependencies block automation |
| 5 | Planner Decision + audit + memory | Humans authorize; approvals teach |

## Architecture (30 seconds)

Evidence → validated `FieldEvent` → TF-IDF+fuzz retrieval + 8-signal score → granularity → deterministic P7 verification → confidence gate → human authorization → records-only actuals + audit + approval-only memory. LLM is optional (extraction/summary); matching, verification, gates, learning are deterministic. Full diagram: `docs/ARCHITECTURE.md`.

## Core innovation

The **Execution Event → Timeline-view → Reconciliation** layer. Competitors match report text to activity names; BRIDGE-X first reconstructs *what execution the evidence describes*, then reconciles it against schedule state, dependencies, and prior evidence. That is why it can refuse, detect contradictions, and handle granularity.

## Matching demonstration (terminology mismatch)

Run `DPR-2026-09-18-01` (*"spool erection"*) — or paste *"24 inch pipeline erection at R-210"* and watch the `pipe→spool` alias + WHY signals bridge the wording gap. After approving, a *different* report with the same wording scores higher by exactly the bounded vocab bonus (`learned +N` badge, `[vocab]` WHY lines, base score unchanged).

## Granularity demonstration (1:1 / Partial / 1:Many / New)

- `ONE_TO_ONE`: Demo Clean match — decisive evidence → may propose completion.
- `PARTIAL`: any seeded `partial/*` report with explicit % → progress only, never completion.
- `ONE_TO_MANY`: Demo Ambiguous (`DPR-2026-09-19-19`, *"R204 piping work completed"*) — tight sub-60 cluster, `insufficient_evidence: true`, group never auto-completed. **This is BRIDGE-X refusing to guess.**
- `NEW_UNPLANNED`: any `unmatched/*` report — below floor → proposes a new-activity record, never a silent edit.

## Verification demonstration (contradiction / dependency conflict)

Demo Dependency error (`DPR-2026-09-18-26`): welding claimed complete while predecessor `PIP-204-018` never started → dependency error names the code → gate forced REVIEW → graph backbone `017 → 018 → 019 → 020` shows the broken order → risk flags `PIP-204-019` ATTENTION. Approving requires a forced, reasoned, audited override.

## Human review (approval / remapping)

Planner Decision shows gate, margin, errors, and decision state per item. Approve / reject / remap (re-verifies target) / mark-new / merge — all need actor + reason where consequential; re-decisions are blocked (409) unless forced. `schedule_updates` are records with before/after snapshots; the `activities` plan table is never overwritten.

## Memory demonstration (approved vocabulary influences a future match)

1. Report A (*pipeline erection, R-210*) links `PIP-210-011` at base score, bonus 0.
2. Forced approval learns `line→spool` (+2.0) and `"erect line"→PIP-210-011` (+3.0).
3. Different report B (*pipeline fit-up, R-210*) re-runs: base score byte-identical, bonus +2.0 with `(approved x1, source)` provenance. Thresholds, margins, granularity, verification, gates unchanged.

## Risk demonstration (evidence-based attention)

Overview → Attention Signals: ATTENTION/WATCH/NORMAL items with per-signal reasons (verification conflicts, contradictions, dependency risk, variance, unmatched evidence, repeat-issue patterns). Advisory only — no probabilities, no predictions. Filter by signal; each item traces to stored evidence.

## Synthetic data disclaimer

Every activity, DPR, date, conflict, pattern, and seeded mapping is a synthetic fixture labeled `SYNTHETIC` (UI badges, API `synthetic: true`). Public Oil India material is 4 fetched sources / 49 terminology terms labeled `REAL_PUBLIC` — reference only, never DPRs/schedules/dates/progress. Approvals, reasons, and audit rows you create live are genuine session actions. Never present synthetic DPRs as real OIL DPRs.
