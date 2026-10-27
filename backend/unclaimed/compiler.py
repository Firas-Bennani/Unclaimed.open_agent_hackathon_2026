"""Rule Compiler: policy text -> constrained JSON DSL, via Nemotron.

Usage:  python -m unclaimed.compiler [benefit ...]
Writes rules/compiled/<benefit>.json after schema + semantic validation
(repair loop, max 2 retries) and checks it against rules/examples/<benefit>.json.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

from .config import settings
from .dsl import Rule, validate_rule
from .fields import FIELDS
from .llm import chat_json

log = logging.getLogger("unclaimed.compiler")

DSL_SPEC = """You compile UK benefit policy text into a JSON rule in a constrained DSL.

Rule object keys:
  id (string, e.g. "pension_credit"), benefit (same as id), name, version (string), jurisdiction (list of countries),
  sources: [{url, title, retrieved}],
  clauses: [{id, text, source_url}]  -- one per [ID] paragraph in the policy text; copy the id exactly, text = short faithful summary,
  derived: [{name, expr, clause}]    -- named intermediate numbers, in dependency order,
  eligibility: Condition,
  amount: {expr, unit: "weekly" | "one_off", clause, min_if_unknown (number or null)},
  questions: {field_name: "one precise plain-English question a caseworker could ask the claimant to establish that field"},
  already_receiving_field: field name or null,
  notes: string

Condition (exactly one form):
  {"all": [Condition, ...]}  {"any": [Condition, ...]}  {"not": Condition}
  {"field": <field>, "op": one of >= <= > < == != in not_in, "value": literal | {"field": <field>} | {"derived": <name>}, "clause": <clause id>}
  {"derived": <name>, "op": ..., "value": ..., "clause": <clause id>}
Every leaf condition MUST cite the clause id that justifies it. Booleans compare with "==" true/false. Lists for "in".

Expression (exactly one form):
  {"const": number} | {"field": <field>} | {"derived": <name>}
  {"op": "add"|"sub"|"mul"|"div"|"max"|"min"|"ceil"|"floor", "args": [Expression, ...]}
  {"if": Condition, "then": Expression, "else": Expression}

Use ONLY the field names listed below. Do not invent fields.
Missing facts evaluate to UNKNOWN (three-valued logic), and arithmetic with an UNKNOWN value is UNKNOWN. Where policy allows a
decision without a fact (e.g. income alone already exceeds a limit and savings can only add to it), add a separate condition so
the rule still decides. Return ONLY the JSON object."""


def _field_catalogue() -> str:
    return "\n".join(f"- {k} ({t}): {d}" for k, (t, d) in FIELDS.items())


def parse_source(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    meta_raw, body = m.group(1), m.group(2)
    meta: dict = {"sources": []}
    for line in meta_raw.splitlines():
        if line.startswith("  - url:"):
            meta["sources"].append({"url": line.split(":", 1)[1].strip()})
        elif line.startswith("    title:"):
            meta["sources"][-1]["title"] = line.split(":", 1)[1].strip()
        elif ":" in line and not line.startswith(" ") and not line.startswith("sources"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body


def compile_benefit(benefit: str) -> tuple[Rule, dict]:
    meta, body = parse_source(settings.rules_dir / "sources" / f"{benefit}.md")
    user = (
        f"Benefit id: {benefit}\nName: {meta['name']}\nJurisdiction: {meta['jurisdiction']}\n"
        f"Retrieved: {meta['retrieved']}\nSources: {json.dumps(meta['sources'])}\n\n"
        f"Available fields:\n{_field_catalogue()}\n\nPolicy text:\n{body}\n\n"
        "Use version \"2026-27\". Include a question for every field the eligibility condition depends on."
    )
    # Examples are part of the repair loop: a failing example is fed back to the model as an error.
    rule, meta_llm = chat_json(settings.reasoning_model, DSL_SPEC, user, Rule,
                               validate=lambda r: validate_rule(r) or check_examples(r), max_tokens=8000)
    return rule, {"model": meta_llm.model, "attempts": meta_llm.attempts, "tokens": meta_llm.prompt_tokens + meta_llm.completion_tokens}


def check_examples(rule: Rule) -> list[str]:
    from .engine import env_from_values
    from .dsl import evaluate

    path = settings.rules_dir / "examples" / f"{rule.benefit}.json"
    if not path.exists():
        return []
    failures = []
    for ex in json.loads(path.read_text(encoding="utf-8")):
        out = evaluate(rule, env_from_values(ex["facts"]))
        if out["status"] != ex["expected_status"]:
            failures.append(f"{ex['name']}: expected {ex['expected_status']} got {out['status']}")
        elif "expected_amount" in ex and abs((out["amount"] or 0) - ex["expected_amount"]) > 0.01:
            failures.append(f"{ex['name']}: expected amount {ex['expected_amount']} got {out['amount']}")
    return failures


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    benefits = argv or [p.stem for p in sorted((settings.rules_dir / "sources").glob("*.md"))]
    out_dir = settings.rules_dir / "compiled"
    out_dir.mkdir(parents=True, exist_ok=True)
    rc = 0
    for b in benefits:
        rule, info = compile_benefit(b)
        failures = check_examples(rule)
        target = out_dir / (f"{b}.json" if not failures else f"{b}.candidate.json")
        target.write_text(rule.model_dump_json(by_alias=True, exclude_none=True, indent=2), encoding="utf-8")
        log.info("%s -> %s (%s) example failures: %s", b, target.name, info, failures or "none")
        rc |= bool(failures)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
