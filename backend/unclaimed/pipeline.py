"""End-to-end assessment of one household: harness -> fact graph -> two lanes -> arbiter -> memory."""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache

from . import arbiter, reasoning
from .config import settings
from .dsl import Rule
from .engine import BENEFITS, default_pack, run_deterministic
from .factgraph import resolve
from .harness import get_harness
from .memory import get_memory
from .models import Decision, Fact

log = logging.getLogger("unclaimed.pipeline")


@lru_cache(maxsize=1)
def _index() -> tuple[dict, ...]:
    return tuple(json.loads((settings.data_dir / "households.json").read_text(encoding="utf-8")))


def households() -> list[dict]:
    return list(_index())


def household(hid: str) -> dict:
    for h in _index():
        if h["id"] == hid:
            return h
    raise KeyError(hid)


def active_pack() -> dict[str, Rule]:
    pack = default_pack()
    for b, rec in get_memory().active_rules().items():
        pack[b] = Rule.model_validate(rec["rule"])
    return pack


def overrides_for(hid: str) -> list[Fact]:
    out = []
    for c in get_memory().corrections(hid):
        if c["kind"] != "fact":
            continue
        out.append(Fact(id=f"caseworker:{c['id']}:{c['target']}", field=c["target"], value=c["value"], source="caseworker",
                        source_label="Caseworker correction", record_id=f"correction:{c['id']}",
                        as_of=datetime.fromisoformat(c["created_at"]).date(), extraction_method="caseworker",
                        note=c["note"] or None))
    return out


def _decisive_clauses(rule: Rule, det: dict, lane: dict) -> list[dict]:
    ids: list[str] = []

    def walk(t):
        if t["kind"] == "leaf":
            if t["clause"] and t["clause"] not in ids and (det["status"] == "TRUE" or t["result"] == det["status"]):
                ids.append(t["clause"])
        for ch in t.get("children", []):
            if det["status"] == "TRUE" or ch["result"] == det["status"]:
                walk(ch)

    walk(det["trace"])
    if det["status"] == "TRUE" and rule.amount.clause not in ids:
        ids.append(rule.amount.clause)
    out = []
    for cid in ids:
        c = rule.clause(cid)
        if c:
            out.append({"id": c.id, "text": c.text, "source_url": c.source_url, "cited_by": "rule engine"})
    for cid in lane.get("clause_ids") or []:
        c = rule.clause(cid)
        if c and cid not in ids:
            out.append({"id": c.id, "text": c.text, "source_url": c.source_url, "cited_by": "Nemotron"})
    return out


def _decisive_fact_ids(det: dict) -> list[str]:
    ids: list[str] = []

    def walk(t):
        if t["kind"] == "leaf" and (det["status"] == "TRUE" or t["result"] == det["status"]):
            ids.extend(i for i in t["fact_ids"] if i not in ids)
        for ch in t.get("children", []):
            if det["status"] == "TRUE" or ch["result"] == det["status"]:
                walk(ch)

    walk(det["trace"])
    return ids


def assess(hid: str, *, pack: dict[str, Rule] | None = None, use_reasoning: bool = True, save: bool = True) -> dict:
    t0 = time.time()
    hh = household(hid)
    pack = pack or active_pack()
    harness = get_harness()
    facts, hits = harness.gather(hh)
    env, resolved, all_facts = resolve(facts, overrides_for(hid))
    t_harness = time.time()
    det = {b: run_deterministic(pack[b], env) for b in BENEFITS}
    t_det = time.time()
    if use_reasoning:
        lanes, lane_meta = reasoning.run(pack, all_facts, resolved)
    else:
        lanes, lane_meta = {b: {"status": "unavailable", "error": "disabled"} for b in BENEFITS}, {"source": "disabled"}
    t_llm = time.time()

    decisions: list[Decision] = []
    for b in BENEFITS:
        rule, d, lane = pack[b], det[b], lanes[b]
        a = arbiter.arbitrate(rule, d, lane)
        weekly = monthly = one_off = None
        if a["status"] == "eligible" and d["amount"] is not None:
            if d["amount_unit"] == "weekly":
                weekly, monthly = d["amount"], round(d["amount"] * 52 / 12, 2)
            else:
                one_off = d["amount"]
        decisions.append(Decision(
            benefit=b, benefit_name=rule.name, status=a["status"], amount_weekly=weekly, amount_monthly=monthly,
            amount_one_off=one_off, amount_is_minimum=d["amount_is_minimum"], already_receiving=bool(d["already_receiving"]),
            reason=a["reason"], question=a["question"], question_field=a["question_field"], escalation_cause=a["cause"],
            rule_version=rule.version, clauses=_decisive_clauses(rule, d, lane),
            fact_ids=list(dict.fromkeys(_decisive_fact_ids(d) + (lane.get("fact_ids") or []))),
            deterministic=d, reasoning=lane, arbiter=a,
        ))

    found_monthly = round(sum(x.amount_monthly or 0 for x in decisions if not x.already_receiving), 2)
    payload = {
        "run_id": uuid.uuid4().hex[:12],
        "household": hh,
        "assessed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "backends": backends(),
        "sources": [h.model_dump() for h in hits],
        "facts": [f.model_dump(mode="json") for f in all_facts],
        "resolved": {k: v.model_dump(mode="json") for k, v in resolved.items()},
        "decisions": [x.model_dump(mode="json") for x in decisions],
        "totals": {
            "eligible": sum(x.status == "eligible" for x in decisions),
            "not_eligible": sum(x.status == "not_eligible" for x in decisions),
            "needs_info": sum(x.status == "needs_info" for x in decisions),
            "monthly_found": found_monthly,
            "one_off_found": sum(x.amount_one_off or 0 for x in decisions if not x.already_receiving),
        },
        "rule_versions": {b: pack[b].version for b in BENEFITS},
        "reasoning_meta": lane_meta,
        "timing_ms": {"harness": round((t_harness - t0) * 1000), "deterministic": round((t_det - t_harness) * 1000),
                      "reasoning": round((t_llm - t_det) * 1000), "total": round((time.time() - t0) * 1000)},
        "corrections": get_memory().corrections(hid),
    }
    if save:
        get_memory().save_assessment(hid, payload)
    return payload


def backends() -> dict:
    from . import llm

    if settings.llm_mode == "live" and settings.nvidia_api_key:
        nem = "Nemotron ✓ live (+cache)"
    elif settings.llm_mode == "replay":
        nem = "Nemotron ✓ replay cache"
    else:
        nem = "Nemotron offline stub"
    return {"llm": nem, "data": get_harness().status, "memory": get_memory().status,
            "models": {"reasoning": settings.reasoning_model, "extraction": settings.extraction_model},
            "llm_available": llm.available()}
