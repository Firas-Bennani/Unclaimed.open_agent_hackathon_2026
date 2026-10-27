# Needs Firas (human-only items)

I'm continuing with fallbacks for all of these — none of them block the build.

1. **Zetaris access** — Zetaris Cloud / AI Data Harness needs an account, a REST API token (kbase.zetaris.com "time-managed keys") and access to `github.com/zetaris/zetaris-public`. If the hackathon handed out a Zetaris workspace URL + token, paste into `.env`:
   `ZETARIS_BASE_URL=...` and `ZETARIS_API_TOKEN=...`
   Fallback in use: `LocalFederatedHarness` (DuckDB + SQL + REST + notes).
2. **Meterless Gaia access** — Gaia is a proprietary app; I couldn't find a public memory API. If the hackathon provided a Gaia endpoint/key, paste: `GAIA_BASE_URL=...` and `GAIA_API_KEY=...` (plus a docs link).
   Fallback in use: `SqliteMemory`.
3. **GitHub** — ✅ done: repo https://github.com/Firas-Bennani/Unclaimed.open_agent_hackathon_2026
4. **Docker Desktop** — ✅ resolved: `docker compose -p unclaimed up --build` verified end to end.
