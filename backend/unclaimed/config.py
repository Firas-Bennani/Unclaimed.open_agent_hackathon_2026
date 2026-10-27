"""Runtime configuration loaded from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    root: Path = ROOT
    nvidia_api_key: str = field(default_factory=lambda: _env("NVIDIA_API_KEY"))
    nvidia_base_url: str = field(default_factory=lambda: _env("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"))
    reasoning_model: str = field(default_factory=lambda: _env("NEMOTRON_REASONING_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"))
    extraction_model: str = field(default_factory=lambda: _env("NEMOTRON_EXTRACTION_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b"))
    # "live" = call API (and record), "replay" = cache only (demo mode), "stub" = deterministic offline stub
    llm_mode: str = field(default_factory=lambda: _env("LLM_MODE", "live"))
    llm_concurrency: int = field(default_factory=lambda: int(_env("LLM_CONCURRENCY", "3")))
    cache_dir: Path = field(default_factory=lambda: Path(_env("LLM_CACHE_DIR", str(ROOT / "data" / "llm_cache"))))
    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", str(ROOT / "data" / "generated"))))
    rules_dir: Path = field(default_factory=lambda: ROOT / "rules")
    dwp_db_url: str = field(default_factory=lambda: _env("DWP_DB_URL", ""))
    council_api_url: str = field(default_factory=lambda: _env("COUNCIL_API_URL", ""))  # empty = in-process
    data_backend: str = field(default_factory=lambda: _env("DATA_BACKEND", "local"))  # local | zetaris
    zetaris_base_url: str = field(default_factory=lambda: _env("ZETARIS_BASE_URL"))
    zetaris_api_token: str = field(default_factory=lambda: _env("ZETARIS_API_TOKEN"))
    memory_backend: str = field(default_factory=lambda: _env("MEMORY_BACKEND", "sqlite"))  # sqlite | gaia
    memory_db: Path = field(default_factory=lambda: Path(_env("MEMORY_DB", str(ROOT / "data" / "memory.db"))))
    gaia_base_url: str = field(default_factory=lambda: _env("GAIA_BASE_URL"))
    gaia_api_key: str = field(default_factory=lambda: _env("GAIA_API_KEY"))
    assessment_date: date = field(default_factory=lambda: date.fromisoformat(_env("ASSESSMENT_DATE", "2026-10-27")))
    stale_after_days: int = field(default_factory=lambda: int(_env("STALE_AFTER_DAYS", "400")))

    @property
    def dwp_url(self) -> str:
        return self.dwp_db_url or f"sqlite:///{(self.data_dir / 'dwp.sqlite').as_posix()}"


settings = Settings()
