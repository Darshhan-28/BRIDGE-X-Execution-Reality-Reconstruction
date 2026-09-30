# MATCHING_ENGINE.md — contextual schedule linking (P5 + P14)

No LLM, no embeddings, no neural search. CPU-only: scikit-learn TF-IDF +
RapidFuzz token-set ratio. Deterministic given the same DB state.

## 1. Fingerprints (`matching/fingerprint.py`)

Both event and activity become a `Fingerprint{action, object (canonical),
raw_object, discipline, location, size, tag, wbs, name, text, tokens}`.
Static aliases canonicalize both sides before comparison:

```text
pipe/pipes/piping → spool · joint(s) → weld · copper → cable
ct → cable tray · fdn/footing/rcc → foundation
```

Event text weights the action ×2; activity text includes name + WBS code.

## 2. Retrieval (`matching/candidate_retrieval.py`)

TF-IDF vectorizer fit on the 55 activity texts; cosine vs event vector +
`RapidFuzz.token_set_ratio/100`. Kept if discipline/location/object/action
match OR `tfidf ≥ 0.10` OR `fuzz ≥ 40`. `pre_score = 0.5·tfidf + 0.5·lex`,
top-10 proceed. Genuinely unrelated input yields zero candidates.

## 3. Scoring (`matching/scorer.py`)

```text
score = 100 × Σ(wᵢ × signalᵢ),  weights from config.py:
semantic .25 · lexical .20 · discipline .15 · location .12 ·
object .10 · size_tag .08 · WBS .05 · state .05   (sum = 1.0)
```

Signals: semantic=tfidf, lexical=fuzz, discipline/location/object exact
0/1, size_tag=1 on size- or tag-equality, WBS 1.0/0.5/0 (discipline+location
proxy), state from status × event type (completion on Complete→0.2,
progress/start on Complete→0.3, unknown→0.6). Every candidate carries the
8 signals plus ✓/✗/~ WHY lines. Below `UNMATCHED_FLOOR = 45.0` →
`unmatched: true`. Top-k default 3 (max 10); margin = top1−top2.

## 4. P14 Adaptive Vocabulary (`matching/vocabulary_boost.py`)

Eligibility (`memory.load_active_vocabulary`): **active + approval_count>0
+ same project**, which by construction means explicit human
approve/remap/curated origin. Never from LLM output, unreviewed matches,
rejects, merges, mark-news, or raw reports.

- Object hit: event raw object == learned term AND candidate canonical
  object == value → **+2.0**. Action hit: same for actions → **+1.5**.
- Phrase hit: `"{action} {object}"` == learned phrase AND candidate code ==
  mapped activity → **+3.0**. Cap **+5.0**/candidate.
- `score = base_score + vocab_bonus`; base formula, signals, weights,
  ranking/floor/margin/granularity/gate paths unchanged — vocabulary flows
  *through* the gates. Each hit stores `{term, type, value, weight,
  approval_count, source_reports}` and renders
  `[vocab] 'line'->'spool' (approved x1, TXT-…) +2.0` on WHY cards
  (+ `learned +N` badge in the Linker). `match_event(..., db=None)`
  without a session is byte-identical P5 behavior.

## 5. Observed behavior (seeded demo, do not hardcode)

Exact spool → `PIP-204-017` ~89; `pipe` mismatch resolves via static alias;
wrong discipline −~19 pts; R-210 wording flips rack; vague `R204 piping`
clusters ~52 (review-bound); helipad misses the floor. After approving a
`pipeline…R-210` report, a later `pipeline fit-up` report gains +2.0 with
provenance while its base score is unchanged (see `DEMO_SCENARIOS.md`).
