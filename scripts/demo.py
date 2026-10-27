"""One-command demo: replay mode, reset memory, seed the demo rule pack,
assess every household from the replay cache, then serve UI + API on :8000."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("LLM_MODE", "replay")
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

import uvicorn  # noqa: E402

from unclaimed import api  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print("Resetting demo state and assessing all households from the replay cache...")
    summary = api.demo_reset()
    print(f"{summary['assessed']} households assessed · £{summary['monthly_found']:,.2f}/month found")
    print(f"Open http://localhost:{port}")
    uvicorn.run(api.app, host="127.0.0.1", port=port, log_level="warning")
