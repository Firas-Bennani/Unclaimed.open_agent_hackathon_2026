# STATUS — Unclaimed

_Last update: 2026-10-27 17:30 UTC · READY_

## Done
- Backend: Nemotron client (throttle, backoff, schema repair, record/replay cache, thinking toggle), Rule DSL + Kleene evaluator, Nemotron rule compiler (examples in the repair loop), data harness over 4 sources, fact graph (conflicts / staleness / caseworker overrides), reasoning lane with citation validation, arbiter, SQLite memory, learning loop (Nemotron patch with a bounded repair loop + regression gate), actions, FastAPI.
- Frontend: dashboard, household view (Why? drawer, answer box, Correct this, drafts), trace, evaluation, rules & learning.
- **Evaluation (run 3, final, all 70 households on one code version):** Unclaimed 98.4% accuracy on decidable cases, 0 wrong "yes", 0 wrong "no", 100% escalation recall, 88.9% escalation precision, coverage 87.1%, selective accuracy 100%. Standard agent: 79.4%, 21 wrong "yes", 62.5% recall. The deterministic lane alone scores 100%, explained honestly in README and EVAL.md. Runs 1–2 are kept in `eval/` with the bugs they exposed (see DECISIONS.md).
- **Demo:** rehearsal recorded (`docs/rehearsal.log`). Offline replay verified end to end: all 280 decisions have the reasoning lane served from cache, Maria's answer replays, the HH-036 patch replays (accepted, 77/81 → 80/81, 0 regressions). Screenshots in `docs/screenshots/` (dashboard, household, household_why, trace, evaluation, learning, rules). DEMO_SCRIPT figures updated.
- **Docker:** `docker compose -p unclaimed up --build` verified at 17:25 UTC. Postgres (DWP source), separate council-api container (REST), app on :8000 in replay mode, UI 200, Maria correct. Then shut down with `docker compose -p unclaimed down`. Other containers on the machine were not touched.
- Tests: 43 passed. GitHub: https://github.com/Firas-Bennani/Unclaimed.open_agent_hackathon_2026 (single author: Firas Bennani).

## Firas TODO (human-only)
1. Record the video following `docs/DEMO_SCRIPT.md`. Start with `powershell -File scripts/demo.ps1`, then open http://localhost:8000.
2. Paste `docs/SUBMISSION.md` into the hackathon form.
3. Optional: Zetaris / Gaia credentials (see NEEDS_FIRAS.md). Both run on honest local fallbacks.

## Known limitations
- Zetaris and Meterless Gaia: interface + local fallback only (no credentials / public API).
- Rules simplified (see README). Scottish CTR and partner benefits for WHD are not modelled. Nemotron flags these, and they account for the 4 unnecessary escalations.
