"""Rule pack loading and the deterministic lane (DSL + Kleene logic)."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .config import settings
from .dsl import Env, Rule, evaluate

BENEFITS = ["pension_credit", "attendance_allowance", "council_tax_reduction", "warm_home_discount"]


def env_from_values(values: dict[str, Any], fact_ids: dict[str, list[str]] | None = None, reasons: dict[str, str] | None = None) -> Env:
    return Env(dict(values), fact_ids or {}, reasons or {})


@lru_cache(maxsize=None)
def _load_file(path: str) -> Rule:
    return Rule.model_validate(json.loads(open(path, encoding="utf-8").read()))


def load_rule(benefit: str) -> Rule:
    return _load_file(str(settings.rules_dir / "compiled" / f"{benefit}.json"))


def default_pack() -> dict[str, Rule]:
    return {b: load_rule(b) for b in BENEFITS}


def run_deterministic(rule: Rule, env: Env) -> dict:
    return evaluate(rule, Env(env.values, env.fact_ids, env.unknown_reason))
