# Submission text (ready to paste)

**Project title:** Unclaimed

**Tagline:** Find benefits. Prove decisions.

**Team:** One-Man Agent Show (Firas)

**Track:** Track 3: Reasoning Architecture

## Problem
Billions in UK public support go unclaimed every year: Pension Credit, Attendance Allowance, Council Tax Reduction, the Warm Home Discount. The rules are complex and scattered, the facts sit in separate systems (DWP records, housing exports, council tax accounts, caseworkers' notes), and welfare-rights caseworkers check eligibility by hand. Mistakes hurt both ways. A wrong "yes" creates overpayment debt. A wrong "no" leaves a pensioner without money they're owed.

## Solution
Unclaimed is a reasoning architecture for caseworkers that turns scattered data and policy text into decisions it can prove:
1. **Rule Compiler:** Nemotron compiles GOV.UK policy text into a constrained, versioned JSON rule DSL. Schema, semantic checks and hand-written rule examples are all part of the repair loop.
2. **Data Harness:** federates four heterogeneous synthetic sources (SQL, CSV, REST API, free-text notes extracted by Nemotron with verbatim quotes) into a fact graph with full provenance. Conflicting or stale facts become UNKNOWN, never silently chosen.
3. **Two independent lanes:** a deterministic engine with Kleene three-valued logic and a proof trace, plus a Nemotron reasoning lane that must cite existing clause and fact ids.
4. **Arbiter:** decides only when both lanes agree and nothing is unknown. Otherwise it escalates with one precise question.
5. **Memory and learning:** caseworker answers are stored with provenance and the case re-runs live. A decision correction becomes a Nemotron-proposed rule patch, accepted only if the regression suite shows zero regressions.
6. **Actions:** an auditable decision record and pre-filled application drafts.

Every ✅/❌ links to the GOV.UK clause and the exact source records (system, record id, field, value, date).

## Results (real runs, `EVAL.md`)
<!-- EVAL_HEADLINE -->

## Sponsor technology
- **NVIDIA Nemotron (live):** `nemotron-3-ultra-550b-a55b` compiles the rules, runs the reasoning lane and proposes rule patches. `nemotron-3.5-lightning-30b-a3b` (thinking off) extracts facts from notes. All calls go through a throttled client with backoff, schema repair and a record/replay cache, which also powers Demo mode.
- **Zetaris:** the Data Harness is built behind a federated-query interface. Without Zetaris credentials it runs on our local federation (SQLite/Postgres + DuckDB/CSV + REST + text). This is stated honestly in the UI and README.
- **Meterless Gaia:** case memory, corrections and rule patches sit behind a memory interface. Without a Gaia API it runs on SQLite. Also stated honestly.

## Tech stack
Python 3, FastAPI, pydantic, DuckDB, SQLAlchemy (SQLite/Postgres), NVIDIA Nemotron via the OpenAI-compatible API, React + Vite + TypeScript + Tailwind, Playwright (UI checks), pytest, Docker Compose.

## What's next
Real Zetaris and Gaia connectors, more schemes (Housing Benefit, Carer's Allowance, Scottish benefits), council-specific CTR schemes, PDF form filling, and a pilot with a welfare-rights charity on anonymised historic cases.

## Repo / run
Repo: https://github.com/Firas-Bennani/Unclaimed.open_agent_hackathon_2026
Run (offline demo): `python -m pip install -r backend/requirements.txt; cd frontend; npm install; cd ..; powershell -File scripts/demo.ps1` → http://localhost:8000

All data is synthetic. Not legal advice. Rules are simplified from GOV.UK guidance.
