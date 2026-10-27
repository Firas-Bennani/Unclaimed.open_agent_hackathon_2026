# Sponsor integrations

Unclaimed uses NVIDIA Nemotron live through the NVIDIA API (`NVIDIA_API_KEY`). Two other sponsor integrations sit behind interfaces and run on local fallbacks. The UI header and `/health` report which backend is active, and nothing claims a sponsor service is in use when it isn't.

| Integration | Interface | Fallback in use | Why |
|---|---|---|---|
| Zetaris (AI Data Harness) | `DataHarness` (`backend/unclaimed/harness/`) | `LocalFederatedHarness`: SQL via SQLAlchemy (SQLite or Postgres), CSV via DuckDB, the council REST API, and Nemotron-extracted case notes | Needs a Zetaris workspace and an API token, which weren't available during the build |
| Meterless Gaia (memory) | `Memory` (`backend/unclaimed/memory.py`) | `SqliteMemory`: assessments, corrections, rule patches, active rules | No public memory API was available to integrate against |

## Turning them on

Set these in `.env` (variable names are listed in `.env.example`):

- **Zetaris:** `DATA_BACKEND=zetaris`, `ZETARIS_BASE_URL=<workspace URL>`, `ZETARIS_API_TOKEN=<API token>`. A Zetaris workspace with REST API access and a time-managed API key is required.
- **Gaia:** `MEMORY_BACKEND=gaia`, `GAIA_BASE_URL=<endpoint>`, `GAIA_API_KEY=<key>`. This also needs the Gaia memory API documentation.

Each backend still needs an adapter that implements the matching interface. Until one exists, setting `zetaris` or `gaia` keeps the local fallback and the status says so, for example "local federation (Zetaris requested but not configured)".
