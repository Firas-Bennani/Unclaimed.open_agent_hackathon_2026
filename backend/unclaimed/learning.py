"""Learning loop: a caseworker's decision correction becomes a candidate rule
patch (proposed by Nemotron) that is accepted only if the regression suite
shows no regressions.

Regression suite = every labelled household (deterministic lane vs the
independent reference labels) + the hand-written rule examples."""
from __future__ import annotations

import copy
import json
import logging
import sys
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from . import llm
from .config import settings
from .dsl import Env, Rule, validate_rule
from .engine import BENEFITS, env_from_values, run_deterministic
from .factgraph import resolve
from .harness import get_harness
from .memory import get_memory
from .pipeline import active_pack, assess, households

log = logging.getLogger("unclaimed.learning")
STATUS_TO_REF = {"TRUE": "yes", "FALSE": "no", "UNKNOWN": "escalate"}


class PatchOp(BaseModel):
    op: Literal["replace"]
    path: str
    value: Any


class PatchProposal(BaseModel):
    rationale: str
    ops: list[PatchOp]
    new_version: str


SYSTEM = """You maintain a benefit rule written in a JSON DSL. A caseworker says the rule produced a wrong decision.
Propose the smallest JSON-Patch ("replace" ops only, RFC 6901 paths into the rule JSON) that fixes the rule so it matches
the policy. Only change what the caseworker's evidence justifies; never loosen unrelated conditions. Update the text of
any clause whose figures you change, and set a new version string.
Every path must already exist in the rule JSON shown (in an "if" expression, "if", "then" and "else" are sibling keys).
Return JSON: {"rationale": "...", "ops": [{"op":"replace","path":"/...","value":...}], "new_version": "..."}"""


@lru_cache(maxsize=1)
def _labels() -> dict[str, dict]:
    sys.path.insert(0, str(settings.root / "eval"))
    from reference import decide_all  # noqa: E402  (independent ground truth)

    gt = json.loads((settings.root / "eval" / "ground_truth.json").read_text(encoding="utf-8"))
    return {g["id"]: decide_all(g["observable"]) for g in gt}


_env_cache: dict[str, Env] = {}


def suite_envs() -> dict[str, Env]:
    """Facts for every household (no caseworker overrides), gathered once per process."""
    if not _env_cache:
        harness = get_harness()
        for hh in households():
            facts, _ = harness.gather(hh)
            env, _, _ = resolve(facts)
            _env_cache[hh["id"]] = env
    return _env_cache


def _examples(benefit: str) -> list[dict]:
    p = settings.rules_dir / "examples" / f"{benefit}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def run_suite(rule: Rule) -> dict:
    labels = _labels()
    per_case: dict[str, bool] = {}
    for hid, env in suite_envs().items():
        out = run_deterministic(rule, env)
        per_case[hid] = STATUS_TO_REF[out["status"]] == labels[hid][rule.benefit]["decision"]
    for ex in _examples(rule.benefit):
        out = run_deterministic(rule, env_from_values(ex["facts"]))
        ok = out["status"] == ex["expected_status"]
        if ok and "expected_amount" in ex:
            ok = abs((out["amount"] or 0) - ex["expected_amount"]) <= 0.01
        per_case[f"example: {ex['name']}"] = ok
    return {"passed": sum(per_case.values()), "total": len(per_case), "cases": per_case}


def _apply(rule_json: dict, ops: list[PatchOp]) -> dict:
    doc = copy.deepcopy(rule_json)
    for op in ops:
        parts = [p.replace("~1", "/").replace("~0", "~") for p in op.path.strip("/").split("/")]
        target = doc
        for p in parts[:-1]:
            target = target[int(p)] if isinstance(target, list) else target[p]
        last = parts[-1]
        if isinstance(target, list):
            target[int(last)] = op.value
        else:
            if last not in target:
                raise KeyError(f"path {op.path} does not exist")
            target[last] = op.value
    return doc


def propose_and_gate(household_id: str, benefit: str, expected: str, explanation: str) -> dict:
    """expected: eligible | not_eligible."""
    mem = get_memory()
    correction = mem.add_correction(household_id, "decision", benefit, expected, explanation)
    pack = active_pack()
    rule = pack[benefit]
    rule_json = json.loads(rule.model_dump_json(by_alias=True, exclude_none=True))
    current = mem.latest_assessment(household_id) or assess(household_id, use_reasoning=False, save=False)
    dec = next(d for d in current["decisions"] if d["benefit"] == benefit)
    facts = {k: v["value"] for k, v in current["resolved"].items() if v["state"] == "known"}
    user = (f"Rule JSON:\n{json.dumps(rule_json, indent=1)}\n\nHousehold facts: {json.dumps(facts, default=str)}\n"
            f"Rule engine decision: {dec['status']} — {dec['reason']}\n"
            f"Caseworker says the correct decision is: {expected}. Caseworker's explanation: \"{explanation}\"")
    patch_id = uuid.uuid4().hex[:10]
    record: dict = {"id": patch_id, "benefit": benefit, "household_id": household_id, "correction_id": correction["id"],
                    "from_version": rule.version, "explanation": explanation, "expected": expected}
    def check(p: PatchProposal) -> list[str]:
        """Apply/validation errors are fed back to the model (bounded repair loop, as in the compiler)."""
        try:
            candidate = _apply(rule_json, p.ops)
            candidate["version"] = p.new_version
            return validate_rule(Rule.model_validate(candidate))
        except Exception as e:  # bad path, wrong type, schema violation
            return [f"patch cannot be applied: {type(e).__name__}: {e}"]

    try:
        proposal, meta = llm.chat_json(settings.reasoning_model, SYSTEM, user, PatchProposal, validate=check, max_tokens=6000)
        record["llm"] = {"model": meta.model, "source": meta.source, "tokens": meta.prompt_tokens + meta.completion_tokens}
    except (llm.LLMUnavailable, ValueError) as e:
        record.update(status="failed", reason=f"could not get a patch proposal: {e}"[:300])
        mem.save_patch(record)
        return record
    record.update(rationale=proposal.rationale, ops=[o.model_dump() for o in proposal.ops], to_version=proposal.new_version)
    try:
        new_json = _apply(rule_json, proposal.ops)
        new_json["version"] = proposal.new_version
        new_rule = Rule.model_validate(new_json)
        errs = validate_rule(new_rule)
        if errs:
            raise ValueError("; ".join(errs))
    except Exception as e:
        record.update(status="rejected", reason=f"patch does not produce a valid rule: {e}"[:300])
        mem.save_patch(record)
        return record

    before, after = run_suite(rule), run_suite(new_rule)
    regressions = [k for k, ok in before["cases"].items() if ok and not after["cases"][k]]
    fixes = [k for k, ok in before["cases"].items() if not ok and after["cases"][k]]
    target_env = suite_envs().get(household_id)
    target_after = run_deterministic(new_rule, target_env)["status"] if target_env else None
    target_ok = {"eligible": "TRUE", "not_eligible": "FALSE"}.get(expected) == target_after
    accepted = not regressions and target_ok and after["passed"] >= before["passed"]
    record.update(
        gate={"before": {"passed": before["passed"], "total": before["total"]},
              "after": {"passed": after["passed"], "total": after["total"]},
              "regressions": regressions, "fixes": fixes, "target_fixed": target_ok},
        status="accepted" if accepted else "rejected",
        reason=("no regressions; " + f"{len(fixes)} case(s) fixed") if accepted else
        (f"{len(regressions)} regression(s)" if regressions else "does not fix the reported case"),
    )
    if accepted:
        mem.set_active_rule(benefit, json.loads(new_rule.model_dump_json(by_alias=True, exclude_none=True)), f"patch {patch_id}")
    mem.save_patch(record)
    return record


def demo_seed_pack() -> None:
    """Demo start state: Pension Credit pack still on 2025-26 rates (£227.10 / £346.60),
    so the learning loop can be shown live. Clearly labelled in the UI and README."""
    rule = json.loads((settings.rules_dir / "compiled" / "pension_credit.json").read_text(encoding="utf-8"))
    text = (json.dumps(rule, ensure_ascii=False).replace("£363.25", "£346.60").replace("£238", "£227.10")
            .replace("363.25", "346.6").replace("238.0", "227.1"))
    old = json.loads(text)
    old["version"] = "2025-26"
    old["notes"] = "Demo starting pack: previous year's (2025-26) Guarantee Credit rates."
    Rule.model_validate(old)
    get_memory().set_active_rule("pension_credit", old, "demo seed: 2025-26 rates")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for b in BENEFITS:
        r = run_suite(active_pack()[b])
        print(b, f"{r['passed']}/{r['total']}", [k for k, v in r["cases"].items() if not v][:10])
