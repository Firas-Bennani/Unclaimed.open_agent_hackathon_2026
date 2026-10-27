# STATUS — Unclaimed

_Last update: 2026-10-27 12:10 UTC_

## Done
- Repo, .gitignore (.env), NEEDS_FIRAS.md, DECISIONS.md
- Nemotron key verified (Ultra 550B for reasoning, 3.5 Lightning 30B for extraction)
- Backend core: config, Nemotron client (throttle, backoff, schema repair, record/replay cache), DSL + Kleene evaluator, fact graph (conflicts/staleness/overrides), 4 source adapters + local federated harness, reasoning lane with citation validation, arbiter, SQLite memory, learning loop + regression gate, actions (drafts, decision record), FastAPI
- Synthetic data: 70 households across 13 scenarios (Maria = HH-001), 4 sources
- Independent reference implementation + hand labels (1 disagreement found and resolved)
- Rule compiler: AA and CTR compiled by Nemotron, both pass the examples

## In progress
- Compiling Pension Credit (with example failures fed back into the repair loop) and Warm Home Discount
- Frontend (forked agent)

## Next
- Tests green → commit → eval run (Unclaimed / baseline / deterministic-only) → EVAL.md
- Demo rehearsal in live mode to fill the replay cache → screenshots → README, demo script, submission

## Risks
- Free-tier latency (~2 min per rule compile); eval runs with 3 workers
- Docker Desktop not starting → no-Docker path is primary
