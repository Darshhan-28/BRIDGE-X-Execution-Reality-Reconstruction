# VERIFICATION_ENGINE.md — P7 is authoritative

> P7 verification remains authoritative. P15 explains context, P16 advises
> attention — neither duplicates, replaces, nor overrides this engine.

Deterministic, offline, no LLM. Implemented in `backend/app/verification/`
(8 files), executed by `pipeline.verify_proposal()` on every match run and
persisted to `verification_results`. Returns `{valid, warnings[], errors[],
reasons[], checks{}, variance{}, gate{}}`.

## Checks (errors block automation; warnings annotate)

| Check | Error when | Warning when |
|---|---|---|
| `temporal.py` | date missing/unparseable; completion/progress dated in the future; event before `actual_start` | stored finish<start; date needed normalization |
| `dependencies.py` | `propose_complete` with any unfinished FS predecessor (`status≠Complete and progress<100`) | `propose_progress` with unfinished preds (early progress); predecessor row missing |
| `state_machine.py` | `propose_complete/progress` on already-Complete (duplicate) | first progress Not Started→In Progress |
| `duplicates.py` | normalized raw text identical to another report (double-counting) | claim text empty |
| `contradictions.py` | same-activity top-1 links clash: completion vs later start/status, or two completion dates (both evidences cited) | — |
| `variance.py` | never (informational) | never — reports `planned_duration_days`, `finish_variance_days`, `elapsed_to_claim_days`, verdict behind/ahead/on plan |

`ONE_TO_MANY`/`NEW_UNPLANNED` skip per-activity checks (valid with a note);
missing target is an error.

## Confidence gate (`confidence_gate.decide`)

```text
verification errors      → REVIEW (MEDIUM, forced=True)
top score < 60           → UNMATCHED (LOW)
top ≥ 85 AND margin ≥ 15 → PROPOSE (HIGH)
else (60–85 or margin<15)→ REVIEW (MEDIUM)
```

Thresholds live in `config.py` (`HIGH_THRESHOLD`, `MEDIUM_THRESHOLD`,
`MIN_MARGIN`); groups/unplanned can never PROPOSE even on scores.

## Proposal rules

Granularity proposes `propose_complete` (ONE_TO_ONE + completion),
`propose_progress` (PARTIAL), `propose_new_activity` (NEW_UNPLANNED), or
`planner_review`. Review may approve clean PROPOSE items directly;
anything else needs `force=true` + written reason.

## What verification may / may not change

- MAY: write `verification_results` rows (evidence + gate decision).
- NEVER: activity status/dates/progress, relationships, review decisions,
  gates, or schedule updates. It has no writer to those tables. The
  `activities` table is provably untouched by the whole pipeline
  (see `test_approve_clean_propose_no_schedule_overwrite`,
  `test_graph_never_mutates_schedule`).
