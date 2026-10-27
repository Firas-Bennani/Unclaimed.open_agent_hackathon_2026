# STATUS — Unclaimed

_Last update: 2026-10-27 12:55 UTC · paused at Firas's request_

## Done
- Repo, .gitignore (.env), NEEDS_FIRAS.md, DECISIONS.md
- Nemotron key verified: `nemotron-3-ultra-550b-a55b` (reasoning, compiler, patches), `nemotron-3.5-lightning-30b-a3b` (notes extraction, thinking off)
- Backend: Nemotron client (throttle, backoff, 420s timeout, schema repair, record/replay cache, thinking toggle), DSL + Kleene evaluator, fact graph (conflicts / staleness / caseworker overrides), 4 sources + local federated harness, reasoning lane with citation validation, arbiter, SQLite memory, learning loop + regression gate, actions (drafts, decision record), FastAPI
- All 4 rules compiled by Nemotron and passing the hand-written examples. Examples are part of the compiler's repair loop (see `rules/compiled/COMPILE_LOG.txt`).
- Synthetic data: 70 households, 13 scenarios, Maria = HH-001. Independent reference implementation + hand labels (1 disagreement found and resolved, logged).
- 40 pytest tests green (offline / replay mode)
- Maria verified live: ✅ PC £187.85/mo · ⚠️ AA (asks for months of care) · ✅ CTR £95.33/mo · ❌ WHD. Both lanes agree.
- Frontend complete (dashboard, household + Why? + answer box + Correct this + drafts, trace, evaluation, rules & learning); `npm run build` clean
- Drafts: README (eval section pending), docs/DEMO_SCRIPT.md, docs/SUBMISSION.md, scripts (demo.py/.ps1, rehearse.py, test.ps1, eval.ps1), Makefile, docker-compose, Dockerfile

## Where I stopped
- **Evaluation run in progress** (`python eval/run.py --workers 6`, LLM_CONCURRENCY=6, log in `eval/run.log`): 30/70 households done at 12:54 UTC, about 1 per minute. When it finishes it writes `eval/results.json` and `EVAL.md`.
  - It keeps running in the background. If it has been stopped, rerun the same command; every completed Nemotron call is cached, so it resumes cheaply.

## Next (in order)
1. Once the eval finishes: read `EVAL.md`, fill `<!-- EVAL -->` in README and `<!-- EVAL_HEADLINE -->` in docs/SUBMISSION.md with the real numbers, commit.
2. `python scripts/rehearse.py` (live) to record the demo's Nemotron responses: demo reset with the 2025-26 PC pack, Maria's AA answer, the HH-036 rule patch, Maria re-assessed. Then update the figures in DEMO_SCRIPT.md (under the 2025-26 pack Maria's PC shows a lower amount until the patch).
3. `scripts/demo.ps1` → verify replay end to end → `python frontend/scripts/screenshots.py` → check the screenshots → add them to README.
4. Final test pass, commit, push (needs a GitHub repo: see NEEDS_FIRAS.md), handoff message.

## Risks
- Free-tier latency/5xx (handled by backoff). Eval ~70 min total; rehearsal ~70 more reasoning calls.
- Docker Desktop not starting → no-Docker path is primary.
- Zetaris / Gaia: fallbacks only (no credentials/API), stated honestly.
