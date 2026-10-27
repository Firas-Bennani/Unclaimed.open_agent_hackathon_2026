"""FastAPI backend.  Run: uvicorn unclaimed.api:app --port 8000 (from backend/)."""
from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import actions, learning, pipeline
from .config import settings
from .fields import FIELDS
from .memory import get_memory
from .mock_council import app as council_app

logging.basicConfig(level=logging.INFO, format='{"t":"%(asctime)s","lvl":"%(levelname)s","log":"%(name)s","msg":"%(message)s"}')
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("unclaimed.api")

app = FastAPI(title="Unclaimed API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/mock-council", council_app)

_bulk = {"running": False, "done": 0, "total": 0}


def _summary(hh: dict, a: dict | None) -> dict:
    out = {**hh, "assessed": a is not None}
    if a:
        out["totals"] = a["totals"]
        out["statuses"] = {d["benefit"]: d["status"] for d in a["decisions"]}
        out["assessed_at"] = a["assessed_at"]
    return out


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "backends": pipeline.backends(), "demo_mode": settings.llm_mode == "replay",
            "llm_mode": settings.llm_mode, "households": len(pipeline.households())}


@app.get("/api/households")
def list_households() -> dict:
    latest = get_memory().all_latest()
    items = [_summary(h, latest.get(h["id"])) for h in pipeline.households()]
    assessed = [i for i in items if i["assessed"]]
    return {
        "households": items,
        "counts": {
            "eligible": sum(i["totals"]["eligible"] for i in assessed),
            "not_eligible": sum(i["totals"]["not_eligible"] for i in assessed),
            "needs_info": sum(i["totals"]["needs_info"] for i in assessed),
        },
        "monthly_found": round(sum(i["totals"]["monthly_found"] for i in assessed), 2),
        "one_off_found": round(sum(i["totals"]["one_off_found"] for i in assessed), 2),
        "assessed": len(assessed),
        "bulk": _bulk,
    }


def _get_hh(hid: str) -> dict:
    try:
        return pipeline.household(hid)
    except KeyError:
        raise HTTPException(404, f"unknown household {hid}")


@app.get("/api/households/{hid}")
def get_household(hid: str) -> dict:
    _get_hh(hid)
    return get_memory().latest_assessment(hid) or pipeline.assess(hid)


@app.post("/api/households/{hid}/assess")
def reassess(hid: str) -> dict:
    _get_hh(hid)
    return pipeline.assess(hid)


class Answer(BaseModel):
    field: str
    value: Any
    note: str = ""


def _diff(before: dict | None, after: dict) -> list[dict]:
    if not before:
        return []
    old = {d["benefit"]: d for d in before["decisions"]}
    return [{"benefit": d["benefit"], "from": old[d["benefit"]]["status"], "to": d["status"],
             "from_amount": old[d["benefit"]]["amount_monthly"], "to_amount": d["amount_monthly"]}
            for d in after["decisions"] if d["benefit"] in old and
            (old[d["benefit"]]["status"] != d["status"] or old[d["benefit"]]["amount_monthly"] != d["amount_monthly"])]


@app.post("/api/households/{hid}/facts")
def correct_fact(hid: str, body: Answer) -> dict:
    """Answer a question or correct a fact: stored with caseworker provenance, then re-run."""
    _get_hh(hid)
    if body.field not in FIELDS:
        raise HTTPException(422, f"unknown field {body.field}")
    before = get_memory().latest_assessment(hid)
    get_memory().add_correction(hid, "fact", body.field, body.value, body.note)
    after = pipeline.assess(hid)
    return {"assessment": after, "changes": _diff(before, after)}


class DecisionCorrection(BaseModel):
    benefit: str
    expected: Literal["eligible", "not_eligible"]
    explanation: str


@app.post("/api/households/{hid}/decision-corrections")
def correct_decision(hid: str, body: DecisionCorrection) -> dict:
    _get_hh(hid)
    before = get_memory().latest_assessment(hid)
    patch = learning.propose_and_gate(hid, body.benefit, body.expected, body.explanation)
    after = pipeline.assess(hid) if patch.get("status") == "accepted" else before
    return {"patch": patch, "assessment": after, "changes": _diff(before, after) if after else []}


@app.get("/api/households/{hid}/drafts/{benefit}")
def draft(hid: str, benefit: str) -> dict:
    a = get_household(hid)
    try:
        return actions.application_draft(a, benefit)
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/api/households/{hid}/record")
def decision_record(hid: str) -> dict:
    return actions.decision_record(get_household(hid))


@app.get("/api/patches")
def patches() -> list[dict]:
    return get_memory().patches()


@app.get("/api/rules")
def rules() -> dict:
    pack = pipeline.active_pack()
    active = get_memory().active_rules()
    return {b: {"version": r.version, "name": r.name, "origin": active.get(b, {}).get("origin", "compiled"),
                "rule": json.loads(r.model_dump_json(by_alias=True, exclude_none=True))} for b, r in pack.items()}


@app.get("/api/eval")
def eval_results() -> dict:
    p = settings.root / "eval" / "results.json"
    if not p.exists():
        raise HTTPException(404, "evaluation not run yet")
    return json.loads(p.read_text(encoding="utf-8"))


class DemoMode(BaseModel):
    demo_mode: bool


@app.post("/api/settings/demo-mode")
def set_demo_mode(body: DemoMode) -> dict:
    settings.llm_mode = "replay" if body.demo_mode else "live"
    return health()


def _assess_all() -> None:
    hhs = pipeline.households()
    _bulk.update(running=True, done=0, total=len(hhs))
    def one(h: dict) -> None:
        try:
            pipeline.assess(h["id"])
        except Exception:
            log.exception("assessment failed for %s", h["id"])
        _bulk["done"] += 1

    try:
        with ThreadPoolExecutor(max_workers=max(1, settings.llm_concurrency)) as ex:
            list(ex.map(one, hhs))
    finally:
        _bulk["running"] = False


@app.post("/api/assess-all")
def assess_all() -> dict:
    if not _bulk["running"]:
        threading.Thread(target=_assess_all, daemon=True).start()
    return _bulk


@app.post("/api/demo/reset")
def demo_reset() -> dict:
    """Clears memory, seeds the demo rule pack, and re-assesses every household (from the replay cache)."""
    get_memory().reset()
    learning.demo_seed_pack()
    _assess_all()
    return list_households()


_dist = settings.root / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = _dist / path
        return FileResponse(f if path and f.is_file() else _dist / "index.html")
