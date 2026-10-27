# STATUS — Unclaimed

_Last update: 2026-10-27 12:35 UTC_

## Done
- Repo, .gitignore (.env), NEEDS_FIRAS.md, DECISIONS.md
- Nemotron key verified (Ultra 550B for reasoning, 3.5 Lightning 30B for extraction)
- Backend core: config, Nemotron client (throttle, backoff, schema repair, record/replay cache), DSL + Kleene evaluator, fact graph (conflicts/staleness/overrides), 4 source adapters + local federated harness, reasoning lane with citation validation, arbiter, SQLite memory, learning loop + regression gate, actions (drafts, decision record), FastAPI
- Synthetic data: 70 households across 13 scenarios (Maria = HH-001), 4 sources
- Independent reference implementation + hand labels (1 disagreement found and resolved)
- Rule compiler: AA and CTR compiled by Nemotron, both pass the examples

- All 4 rules compiled by Nemotron (3 needed one repair; PC repaired from a failing hand-written example)
- 40 tests green; Maria verified live (✅ PC £187.85 · ⚠️ AA · ✅ CTR £95.33 · ❌ WHD, both lanes agree)
- Frontend complete (dashboard, household, trace, evaluation, rules & learning)
- README, DEMO_SCRIPT, SUBMISSION drafted (numbers pending eval)

## In progress
- Full evaluation run (70 households × Unclaimed / baseline / deterministic) — restarted with 420s timeout

## Next
- Tests green → commit → eval run (Unclaimed / baseline / deterministic-only) → EVAL.md
- Demo rehearsal in live mode to fill the replay cache → screenshots → README, demo script, submission

## Risks
- Free-tier latency (~2 min per rule compile); eval runs with 3 workers
- Docker Desktop not starting → no-Docker path is primary
