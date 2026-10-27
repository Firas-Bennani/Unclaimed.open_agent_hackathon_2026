"""Reasoning Lane: Nemotron decides independently from rule text + facts and
must cite clause ids and fact ids. Any citation that does not exist
invalidates that benefit's answer (no repair for citations)."""
from __future__ import annotations

import json
import logging
from typing import Literal, Optional

from pydantic import BaseModel

from . import llm
from .config import settings
from .dsl import Rule
from .factgraph import _fmt
from .fields import FIELDS
from .models import Fact, ResolvedFact

log = logging.getLogger("unclaimed.reasoning")


class LaneDecision(BaseModel):
    benefit: str
    decision: Literal["eligible", "not_eligible", "cannot_decide"]
    weekly_amount: Optional[float] = None
    clause_ids: list[str]
    fact_ids: list[str]
    reason: str
    missing_info: Optional[str] = None


class LaneOutput(BaseModel):
    decisions: list[LaneDecision]


SYSTEM = """You are a careful UK welfare-rights adviser checking benefit eligibility for one household.
Decide each benefit ONLY from the rule clauses and the facts given. Rules:
- If a fact the rule needs is missing, out of date, or the sources conflict, answer "cannot_decide" and say what is missing.
- A wrong "eligible" causes overpayment debt: never guess.
- Data freshness policy: a record is current if it is dated within 400 days of the assessment date (pensions are uprated every April, so an April 2026 record is current in October 2026); only older records are out of date.
- Reconciliation policy: an approximate figure from a note (e.g. 'about £5,000') is consistent with a record if it is within 10% of it; that is not a conflict.
- If every condition is met but only the rate is unclear, the household is eligible: give the lower rate.
- Cite the clause ids you relied on (e.g. "PC-4") and the fact ids (e.g. "F3") you relied on. Cite only ids that appear below.
- weekly_amount: the weekly amount in GBP if eligible (for a one-off payment give the one-off amount), else null.
Return JSON: {"decisions":[{"benefit":..., "decision":"eligible|not_eligible|cannot_decide", "weekly_amount":..., "clause_ids":[...], "fact_ids":[...], "reason":"one plain-English sentence", "missing_info": null or "..."}]}"""


def _facts_block(facts: list[Fact], resolved: dict[str, ResolvedFact]) -> tuple[str, dict[str, str]]:
    short: dict[str, str] = {}
    lines = []
    for f in facts:
        if f.field not in FIELDS or f.source == "derived" and f.field not in ("age_years", "state_pension_age", "partner_reached_spa"):
            continue
        sid = f"F{len(short) + 1}"
        short[sid] = f.id
        flags = []
        if f.status == "stale":
            flags.append(f"OUT OF DATE (as of {f.as_of})")
        elif f.as_of:
            flags.append(f"as of {f.as_of}")
        if f.status == "superseded":
            flags.append("superseded by caseworker")
        if f.confidence < 0.8:
            flags.append("approximate")
        if f.note and f.source in ("housing",) and "linked by" in f.note:
            flags.append(f.note)
        lines.append(f"{sid}: {f.field} = {_fmt(f.value)}  [source: {f.source_label}; record {f.record_id}{'; ' + '; '.join(flags) if flags else ''}]")
    conflicts = [f"- {r.field}: {r.explanation}" for r in resolved.values() if r.state == "conflict"]
    missing = [r.field for r in resolved.values() if r.state == "missing"]
    text = "\n".join(lines)
    if conflicts:
        text += "\n\nConflicts detected by the data harness:\n" + "\n".join(conflicts)
    if missing:
        text += "\n\nNo source has: " + ", ".join(sorted(missing))
    return text, short


def _rules_block(pack: dict[str, Rule]) -> str:
    out = []
    for b, r in pack.items():
        out.append(f"## {b} — {r.name} (version {r.version})\n" + "\n".join(f"[{c.id}] {c.text}" for c in r.clauses))
    return "\n\n".join(out)


def run(pack: dict[str, Rule], facts: list[Fact], resolved: dict[str, ResolvedFact]) -> tuple[dict[str, dict], dict]:
    """Returns {benefit: lane_result} and call metadata."""
    fblock, short = _facts_block(facts, resolved)
    user = (f"Assessment date: {settings.assessment_date}\n\n# Rule clauses\n{_rules_block(pack)}\n\n# Facts\n{fblock}\n\n"
            f"Decide these benefits: {', '.join(pack)}.")
    try:
        out, meta = llm.chat_json(settings.reasoning_model, SYSTEM, user, LaneOutput, max_tokens=16000)
    except llm.LLMUnavailable as e:
        return {b: {"status": "unavailable", "error": str(e)} for b in pack}, {"source": "unavailable"}
    except ValueError as e:
        return {b: {"status": "invalid", "error": f"unparseable output: {e}"[:300]} for b in pack}, {"source": "error"}
    info = {"model": meta.model, "source": meta.source, "tokens": meta.prompt_tokens + meta.completion_tokens,
            "latency_s": meta.latency_s, "attempts": meta.attempts, "thinking": meta.reasoning[-4000:]}
    results: dict[str, dict] = {}
    for b, rule in pack.items():
        d = next((x for x in out.decisions if x.benefit == b), None)
        if d is None:
            results[b] = {"status": "invalid", "error": "no decision returned for this benefit"}
            continue
        bad_clauses = [c for c in d.clause_ids if c not in rule.clause_ids()]
        bad_facts = [f for f in d.fact_ids if f not in short]
        res = {
            "status": "invalid" if (bad_clauses or bad_facts or not d.clause_ids) else "ok",
            "decision": d.decision,
            "weekly_amount": d.weekly_amount,
            "clause_ids": d.clause_ids,
            "fact_ids": [short.get(f, f) for f in d.fact_ids],
            "reason": d.reason,
            "missing_info": d.missing_info,
        }
        if res["status"] == "invalid":
            res["error"] = ("cited non-existent " + ", ".join(
                ([f"clauses {bad_clauses}"] if bad_clauses else []) + ([f"facts {bad_facts}"] if bad_facts else [])
            )) if (bad_clauses or bad_facts) else "no clause cited"
        results[b] = res
    return results, info
