"""Constrained rule DSL + Kleene three-valued evaluator with proof traces.

Conditions:  {"all":[...]} | {"any":[...]} | {"not":C} | leaf
Leaf:        {"field":"age_years","op":">=","value":66 | {"field":"x"} | {"derived":"x"},"clause":"PC-2"}
Expressions: {"const":n} | {"field":f} | {"derived":d} | {"op":"add|sub|mul|div|max|min|ceil|floor","args":[...]}
             | {"if":C,"then":E,"else":E}
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .fields import FIELD_NAMES

Op = Literal[">=", "<=", ">", "<", "==", "!=", "in", "not_in"]
ArithOp = Literal["add", "sub", "mul", "div", "max", "min", "ceil", "floor"]


class Tri(str, Enum):
    T = "TRUE"
    F = "FALSE"
    U = "UNKNOWN"


# ---------- schema ----------
class Expr(BaseModel):
    const: Optional[float] = None
    field: Optional[str] = None
    derived: Optional[str] = None
    op: Optional[ArithOp] = None
    args: Optional[list["Expr"]] = None
    if_: Optional["Cond"] = Field(default=None, alias="if")
    then: Optional["Expr"] = None
    else_: Optional["Expr"] = Field(default=None, alias="else")

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @model_validator(mode="after")
    def _one_kind(self):
        kinds = [self.const is not None, self.field is not None, self.derived is not None, self.op is not None, self.if_ is not None]
        if sum(kinds) != 1:
            raise ValueError("expression must be exactly one of const/field/derived/op/if")
        if self.op and not self.args:
            raise ValueError(f"op {self.op} needs args")
        if self.if_ is not None and (self.then is None or self.else_ is None):
            raise ValueError("if needs then and else")
        return self


class Cond(BaseModel):
    all: Optional[list["Cond"]] = None
    any: Optional[list["Cond"]] = None
    not_: Optional["Cond"] = Field(default=None, alias="not")
    field: Optional[str] = None
    derived: Optional[str] = None
    op: Optional[Op] = None
    value: Optional[Any] = None
    clause: Optional[str] = None

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @model_validator(mode="after")
    def _one_kind(self):
        leaf = self.field is not None or self.derived is not None
        kinds = [self.all is not None, self.any is not None, self.not_ is not None, leaf]
        if sum(kinds) != 1:
            raise ValueError("condition must be exactly one of all/any/not/leaf")
        if leaf and (self.op is None or not self.clause):
            raise ValueError("leaf condition needs op and clause")
        return self


class Clause(BaseModel):
    id: str
    text: str
    source_url: str


class Source(BaseModel):
    url: str
    title: str
    retrieved: str


class Derived(BaseModel):
    name: str
    expr: Expr
    clause: str


class Amount(BaseModel):
    expr: Expr
    unit: Literal["weekly", "one_off"]
    clause: str
    min_if_unknown: Optional[float] = None


class Rule(BaseModel):
    id: str
    benefit: str
    name: str
    version: str
    jurisdiction: list[str]
    sources: list[Source]
    clauses: list[Clause]
    derived: list[Derived] = []
    eligibility: Cond
    amount: Amount
    questions: dict[str, str] = {}
    already_receiving_field: Optional[str] = None
    notes: str = ""

    def clause_ids(self) -> set[str]:
        return {c.id for c in self.clauses}

    def clause(self, cid: str) -> Clause | None:
        return next((c for c in self.clauses if c.id == cid), None)


Expr.model_rebuild()
Cond.model_rebuild()


# ---------- semantic validation ----------
def _walk_cond(c: Cond):
    yield c
    for sub in (c.all or []) + (c.any or []):
        yield from _walk_cond(sub)
    if c.not_:
        yield from _walk_cond(c.not_)


def _walk_expr(e: Expr):
    yield e
    for a in e.args or []:
        yield from _walk_expr(a)
    for sub in (e.then, e.else_):
        if sub:
            yield from _walk_expr(sub)
    if e.if_:
        yield from _walk_cond(e.if_)


def validate_rule(rule: Rule) -> list[str]:
    """Checks a schema-valid rule for unknown fields, clauses and derived refs."""
    errs: list[str] = []
    cids = rule.clause_ids()
    dnames: list[str] = []
    for d in rule.derived:
        for node in _walk_expr(d.expr):
            if node.derived and node.derived not in dnames:
                errs.append(f"derived '{d.name}' references '{node.derived}' before it is defined")
        dnames.append(d.name)
        if d.clause not in cids:
            errs.append(f"derived '{d.name}' cites unknown clause {d.clause}")
    nodes = list(_walk_cond(rule.eligibility)) + list(_walk_expr(rule.amount.expr))
    for d in rule.derived:
        nodes += list(_walk_expr(d.expr))
    for n in nodes:
        if n.field is not None and n.field not in FIELD_NAMES:
            errs.append(f"unknown field '{n.field}'")
        if n.derived is not None and n.derived not in dnames:
            errs.append(f"unknown derived value '{n.derived}'")
        if isinstance(n, Cond):
            if n.clause and n.clause not in cids:
                errs.append(f"condition cites unknown clause {n.clause}")
            if isinstance(n.value, dict) and not ({"field"} == set(n.value) or {"derived"} == set(n.value)):
                try:
                    sub = Expr.model_validate(n.value)
                except Exception as e:
                    errs.append(f"invalid comparison expression: {e}")
                    continue
                for m in _walk_expr(sub):
                    if m.field is not None and m.field not in FIELD_NAMES:
                        errs.append(f"unknown field '{m.field}'")
                    if m.derived is not None and m.derived not in dnames:
                        errs.append(f"unknown derived value '{m.derived}'")
            elif isinstance(n.value, dict):
                if "field" in n.value and n.value["field"] not in FIELD_NAMES:
                    errs.append(f"unknown field '{n.value['field']}' in comparison value")
                if "derived" in n.value and n.value["derived"] not in dnames:
                    errs.append(f"unknown derived '{n.value['derived']}' in comparison value")
    if rule.amount.clause not in cids:
        errs.append(f"amount cites unknown clause {rule.amount.clause}")
    for f in rule.questions:
        if f not in FIELD_NAMES:
            errs.append(f"question for unknown field '{f}'")
    return errs


# ---------- evaluation ----------
class Env:
    """Resolved facts for one household: value or None (unknown) + provenance."""

    def __init__(self, values: dict[str, Any], fact_ids: dict[str, list[str]], unknown_reason: dict[str, str]):
        self.values = values
        self.fact_ids = fact_ids
        self.unknown_reason = unknown_reason
        self.derived: dict[str, Any] = {}
        self.derived_trace: dict[str, dict] = {}


def eval_expr(e: Expr, env: Env):
    if e.const is not None:
        return e.const
    if e.field is not None:
        v = env.values.get(e.field)
        return float(v) if isinstance(v, bool) else v
    if e.derived is not None:
        return env.derived.get(e.derived)
    if e.if_ is not None:
        c, _ = eval_cond(e.if_, env)
        if c == Tri.T:
            return eval_expr(e.then, env)
        if c == Tri.F:
            return eval_expr(e.else_, env)
        return None
    vals = [eval_expr(a, env) for a in e.args]
    if any(v is None for v in vals):
        return None
    if e.op == "add":
        return sum(vals)
    if e.op == "sub":
        return vals[0] - sum(vals[1:])
    if e.op == "mul":
        return math.prod(vals)
    if e.op == "div":
        return vals[0] / vals[1] if vals[1] else None
    if e.op == "max":
        return max(vals)
    if e.op == "min":
        return min(vals)
    if e.op == "ceil":
        return float(math.ceil(round(vals[0], 9)))
    if e.op == "floor":
        return float(math.floor(round(vals[0], 9)))
    raise ValueError(e.op)


_CMP = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


def _operand(v, env: Env):
    if isinstance(v, dict) and set(v) == {"field"}:
        return env.values.get(v["field"]), v["field"]
    if isinstance(v, dict) and set(v) == {"derived"}:
        return env.derived.get(v["derived"]), v["derived"]
    if isinstance(v, dict) and set(v) == {"const"}:
        return v["const"], None
    if isinstance(v, dict):  # an arithmetic expression as the comparison value
        return eval_expr(Expr.model_validate(v), env), "expression"
    return v, None


def eval_cond(c: Cond, env: Env) -> tuple[Tri, dict]:
    if c.all is not None or c.any is not None:
        kind = "all" if c.all is not None else "any"
        results = [eval_cond(s, env) for s in (c.all if kind == "all" else c.any)]
        vals = [r for r, _ in results]
        if kind == "all":
            res = Tri.F if Tri.F in vals else (Tri.U if Tri.U in vals else Tri.T)
        else:
            res = Tri.T if Tri.T in vals else (Tri.U if Tri.U in vals else Tri.F)
        return res, {"kind": kind, "result": res.value, "clause": c.clause, "children": [t for _, t in results]}
    if c.not_ is not None:
        r, t = eval_cond(c.not_, env)
        res = {Tri.T: Tri.F, Tri.F: Tri.T, Tri.U: Tri.U}[r]
        return res, {"kind": "not", "result": res.value, "clause": c.clause, "children": [t]}
    name = c.field or c.derived
    left = env.values.get(c.field) if c.field else env.derived.get(c.derived)
    right, right_name = _operand(c.value, env)
    res = Tri.U if left is None or right is None else (Tri.T if _CMP[c.op](left, right) else Tri.F)

    def ids_for(n: str | None) -> list[str]:
        if n == "expression":
            return sorted({i for f in _expr_fields(Expr.model_validate(c.value), {}) for i in env.fact_ids.get(f, [])})
        if not n:
            return []
        return list(env.fact_ids.get(n, [])) or list(env.derived_trace.get(n, {}).get("fact_ids", []))

    trace = {
        "kind": "leaf",
        "clause": c.clause,
        "subject": name,
        "subject_kind": "field" if c.field else "derived",
        "op": c.op,
        "left": left,
        "right": right if right_name is None else {"ref": right_name, "value": right,
                                                   **({"fields": sorted(_expr_fields(Expr.model_validate(c.value), {}))} if right_name == "expression" else {})},
        "result": res.value,
        "fact_ids": ids_for(name) + ids_for(right_name),
    }
    return res, trace


def _expr_fields(e: Expr, deps: dict[str, set[str]]) -> set[str]:
    out: set[str] = set()
    for n in _walk_expr(e):
        if n.field:
            out.add(n.field)
        if n.derived:
            out |= deps.get(n.derived, set())
        if isinstance(n, Cond) and isinstance(n.value, dict) and "field" in n.value:
            out.add(n.value["field"])
    return out


def evaluate(rule: Rule, env: Env) -> dict:
    """Runs a rule. Returns status, amount, trace and the unknown fields that matter."""
    deps: dict[str, set[str]] = {}
    for d in rule.derived:
        val = eval_expr(d.expr, env)
        deps[d.name] = _expr_fields(d.expr, deps)
        env.derived[d.name] = None if val is None else round(val, 4)
        env.derived_trace[d.name] = {
            "value": env.derived[d.name],
            "clause": d.clause,
            "fields": sorted(deps[d.name]),
            "fact_ids": sorted({i for f in deps[d.name] for i in env.fact_ids.get(f, [])}),
        }
    status, trace = eval_cond(rule.eligibility, env)
    blocking = _blocking_unknowns(trace, deps, env) if status == Tri.U else []
    amount = None
    amount_is_minimum = False
    if status == Tri.T:
        amount = eval_expr(rule.amount.expr, env)
        if amount is None and rule.amount.min_if_unknown is not None:
            amount, amount_is_minimum = rule.amount.min_if_unknown, True
        if amount is not None:
            amount = round(amount, 2)
    already = env.values.get(rule.already_receiving_field) if rule.already_receiving_field else None
    return {
        "status": status.value,
        "amount": amount,
        "amount_unit": rule.amount.unit,
        "amount_is_minimum": amount_is_minimum,
        "already_receiving": already,
        "trace": trace,
        "derived": env.derived_trace,
        "unknown_fields": blocking,
    }


def _blocking_unknowns(trace: dict, deps: dict[str, set[str]], env: Env) -> list[dict]:
    """Fields whose absence makes the result UNKNOWN (from leaves that evaluated to U)."""
    out: dict[str, str] = {}

    def names_for(n: str, kind: str) -> list[str]:
        return [n] if kind == "field" else sorted(deps.get(n, set()))

    def visit(t):
        if t["result"] != Tri.U.value:
            return
        if t["kind"] == "leaf":
            names = names_for(t["subject"], t["subject_kind"])
            if isinstance(t["right"], dict) and "ref" in t["right"]:
                ref = t["right"]["ref"]
                if ref == "expression":
                    for f in t["right"].get("fields", []):
                        names += names_for(f, "derived" if f in deps else "field")
                else:
                    names += names_for(ref, "derived" if ref in deps else "field")
            for n in names:
                if env.values.get(n) is None:
                    out[n] = env.unknown_reason.get(n, "missing")
        for ch in t.get("children", []):
            visit(ch)

    visit(trace)
    return [{"field": f, "reason": r} for f, r in out.items()]
