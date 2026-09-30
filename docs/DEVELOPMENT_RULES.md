# DEVELOPMENT_RULES.md — strict rules for future AI coding agents

1. Do not redesign the architecture without explicit owner approval.
2. Do not implement future features without explicit instruction.
3. Do not silently modify schedule activities — no writer to `activities` may ever be added by the pipeline.
4. AI proposes; deterministic verification validates; humans control consequential decisions.
5. Do not replace deterministic verification with an LLM.
6. Core functionality must not require LLM/API availability unless explicitly approved.
7. Preserve offline functionality (fallback parser + templates + local matching).
8. Never fabricate ML accuracy, probabilities, confidence, or predictions.
9. Do not add generic chatbot/RAG functionality without explicit approval.
10. Do not introduce unnecessary multi-agent architecture.
11. Do not introduce blockchain merely for novelty.
12. Do not introduce computer vision merely for visual appeal.
13. Do not introduce heavy local models conflicting with CPU/offline constraints (no Ollama/7B/VLM/CUDA assumptions).
14. P7 remains authoritative for verification.
15. P15 is contextual/evidence-only — it explains, never decides.
16. P16 is advisory execution intelligence, not a validated predictive model.
17. Only eligible human-approved decisions (approve/remap/curated POST: active, approval_count>0, same project) may teach project vocabulary.
18. Never weaken/delete tests just to make a feature pass.
19. Preserve existing API contracts unless explicitly changing them (update `API_REFERENCE.md` + frontend client + smoke in the same change).
20. Run regression tests after meaningful changes (pytest; plus build + smoke for UI/API changes).
21. Do not remove existing functionality while adding a feature.
22. Keep synthetic data clearly identified as synthetic (UI strings, API notes, tests).
23. Inspect existing code before creating new modules; prefer the established module for the job (`matching/`, `verification/`, `review.py`, `memory.py`).
24. Prefer small, deterministic, explainable changes (bounded constants, provenance, no silent behavior).
25. Every consequential automated behavior must remain auditable (decision + evidence persisted).
26. Never claim a feature exists unless it is actually implemented and tested.

## Feature Freeze

Current feature boundary: **P16**.

Do not begin P17 or invent additional differentiators unless explicitly
instructed by the project owner. Backend version `0.16.0-p16` marks the
frozen baseline; bump it only when shipping an approved phase.

## Safe-change checklist (run before finishing any change)

- [ ] `py -m pytest -q` green in `backend/` (count matches `TESTING_STATUS.md` or grows with new tests only)
- [ ] `npm run build` clean in `frontend/` if UI touched
- [ ] `npm run smoke` green (backend running) if APIs/UI touched
- [ ] No `.env`/keys committed; `.env.example` stays keyless
- [ ] No background jobs left running; no dead files added
- [ ] Docs updated if contracts, schema, thresholds, or demos changed
