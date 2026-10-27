"""Demo rehearsal: performs the exact demo-script actions in LIVE mode so every
Nemotron response the demo needs is recorded in the replay cache.
Run once (needs NVIDIA_API_KEY); afterwards `make demo` / scripts/demo.ps1 runs fully offline.

The inputs below must match docs/DEMO_SCRIPT.md word for word.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["LLM_MODE"] = "live"
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

from fastapi.testclient import TestClient  # noqa: E402

from unclaimed.api import app  # noqa: E402

MARIA = "HH-001"
ANSWER = {"field": "care_need_months", "value": 7, "note": "Daughter has helped her wash and dress since March 2026"}
PATCH_EXPLANATION = ("From April 2026 the Pension Credit guarantee is £238 a week for a single person "
                     "(gov.uk/pension-credit/what-youll-get). Their income is below that.")

if __name__ == "__main__":
    c = TestClient(app)
    s = c.post("/api/demo/reset").json()
    print(f"reset: {s['assessed']} assessed, £{s['monthly_found']:,.2f}/month")
    r = c.post(f"/api/households/{MARIA}/facts", json=ANSWER).json()
    print("Maria answer changes:", r["changes"])
    patch_target = json.loads((ROOT / "docs" / "demo_patch_target.json").read_text())["household_id"]
    r = c.post(f"/api/households/{patch_target}/decision-corrections",
               json={"benefit": "pension_credit", "expected": "eligible", "explanation": PATCH_EXPLANATION}).json()
    p = r["patch"]
    print("patch:", p["status"], p.get("reason"), p.get("gate"), p.get("ops"))
    print("changes:", r["changes"])
    r = c.post(f"/api/households/{MARIA}/assess").json()  # Maria under the patched pack
    print("Maria after patch:", {d["benefit"]: (d["status"], d["amount_monthly"]) for d in r["decisions"]})
