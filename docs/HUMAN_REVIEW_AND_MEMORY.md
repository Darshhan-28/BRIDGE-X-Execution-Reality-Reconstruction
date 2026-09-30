# HUMAN_REVIEW_AND_MEMORY.md

## Human Review (`app/review.py`)

> Human-approved decisions are the trusted learning signal — and the only
> path to a schedule update.

- **Queue** (`GET /api/review/queue?bucket=`): every pipeline run becomes
  an item with gate, top score/margin, granularity, verification errors,
  and decision state; buckets CONFLICT (contradiction/duplicate errors) /
  HIGH (PROPOSE) / MEDIUM (valid REVIEW) / LOW (invalid REVIEW) /
  UNMATCHED, sorted in that order.
- **Approve** → creates an approved `schedule_updates` row (before/after
  snapshot, `forced` flag). Clean path requires valid + PROPOSE; anything
  else needs `force=true` + written reason (422), re-decisions 409.
- **Reject** → reason mandatory, no update. **Remap** → new target is
  re-verified (invalid needs force); teaches vocabulary like approve.
  **Mark-new** → proposal record only, never an activity row.
  **Merge** → appends `merged_evidence` to the target update, no schedule change.
- **Audit:** every action writes `audit_events` (actor, action, IDs,
  before/after, timestamp, reason); UI shows a filterable timeline + JSON export.
- **Schedule safety:** no writer to `activities` exists anywhere in the
  pipeline; tests assert statuses byte-identical after approvals.

## Memory (`app/memory.py`)

- **Project vocabulary** (`project_vocabulary`): learned ONLY from
  approve/remap (+ planner-curated POST). Object mappings when field≠
  schedule wording (`pipe→spool`); action reinforcement only when terms
  already agree (forced remaps can't teach false equivalences);
  phrase→activity (`"erect pipe"→PIP-204-017`). Key
  `(project,term,type,value)` dedups by incrementing `approval_count` and
  appending source reports, with approver/timestamp provenance.
- **Eligibility for matching (P14):** active + `approval_count>0` +
  same project; bounded bonus (+2.0/+1.5/+3.0, cap +5.0) with provenance —
  see `MATCHING_ENGINE.md`.
- **Synthetic execution history** (`execution_history`, always synthetic):
  per-pattern planned/actual durations and issues via
  `GET /api/memory/patterns`; feeds P16 REPEATED signals, always labeled.
- **What does NOT teach:** LLM output, unreviewed matches, rejects, merges,
  mark-news, raw reports — each pinned by a dedicated regression test.
