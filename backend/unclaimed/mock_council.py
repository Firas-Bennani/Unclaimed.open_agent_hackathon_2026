"""Mock REST API: "council tax account service" (synthetic data).

Run standalone:  uvicorn unclaimed.mock_council:app --port 8100
Also mounted in the main API under /mock-council.
"""
from __future__ import annotations

import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query

from .config import settings

app = FastAPI(title="Council Tax Account Service (mock)")


@lru_cache(maxsize=1)
def _accounts() -> list[dict]:
    return json.loads((settings.data_dir / "council_accounts.json").read_text(encoding="utf-8"))


@app.get("/accounts")
def search_accounts(postcode: str = Query(...), surname: str | None = None) -> list[dict]:
    pc = postcode.replace(" ", "").upper()
    out = [a for a in _accounts() if a["postcode"].replace(" ", "").upper() == pc]
    if surname:
        out = [a for a in out if a["liable_name"].upper().endswith(surname.upper())]
    return out


@app.get("/accounts/{account_id}")
def get_account(account_id: str) -> dict:
    for a in _accounts():
        if a["account_id"] == account_id:
            return a
    raise HTTPException(404, "account not found")
