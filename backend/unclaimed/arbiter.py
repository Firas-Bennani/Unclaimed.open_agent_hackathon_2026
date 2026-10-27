"""Arbiter: combines the deterministic and reasoning lanes. It decides only when
both lanes agree and nothing is UNKNOWN; otherwise it escalates with one
precise question. Bias: escalation beats a wrong "yes"."""
from __future__ import annotations

from .dsl import Rule
from .factgraph import _fmt
from .fields import FIELDS

OP_WORDS = {">=": "at least", "<=": "at most", ">": "more than", "<": "below", "==": "equal to", "!=": "not",
            "in": "one of", "not_in": "not one of"}
FIELD_LABEL = {
    "weekly_income_total": "weekly income", "savings": "savings", "age_years": "age", "country": "country",
    "has_partner": "lives with a partner", "partner_reached_spa": "partner has reached State Pension age",
    "needs_care_help": "needs help with personal care", "care_need_months": "months needing help",
    "care_day_and_night": "needs help day and night", "in_gb_2_of_last_3_years": "in Great Britain 2 of the last 3 years",
    "receives_dla_or_pip": "gets DLA/PIP", "council_tax_liable": "liable for council tax",
    "electricity_bill_in_name": "name is on the electricity bill",
    "receives_qualifying_benefit_on_whd_date": "was getting a qualifying benefit on 23 August 2026",
    "receives_pension_credit": "gets Pension Credit",
}
UNKNOWN_CAUSE = {"missing": "missing information", "conflict": "sources disagree", "stale": "out-of-date record"}


def _label(name: str) -> str:
    return FIELD_LABEL.get(name, name.replace("_", " "))


def _leaves(t: dict, result: str | None = None):
    if t["kind"] == "leaf":
        if result is None or t["result"] == result:
            yield t
    for ch in t.get("children", []):
        if ch["result"] == t["result"] or result is None:
            yield from _leaves(ch, result)


def _leaf_sentence(leaf: dict, rule: Rule) -> str:
    right = leaf["right"]
    rv = right["value"] if isinstance(right, dict) and "ref" in right else right
    subj = _label(leaf["subject"])
    if isinstance(leaf["left"], bool) or isinstance(rv, bool):
        verb = "is" if leaf["left"] == rv else "is not"
        if leaf["result"] == "FALSE" and leaf["op"] == "==":
            return f"Rule {leaf['clause']}: requires '{subj}' to be {_fmt(rv)}, but it is {_fmt(leaf['left'])}."
        return f"'{subj}' {verb} {_fmt(rv)} (rule {leaf['clause']})."
    if isinstance(rv, list):
        rv = ", ".join(rv)
    neg = "" if leaf["result"] == "TRUE" else "not "
    return f"{subj.capitalize()} is {_fmt(leaf['left'])}, which is {neg}{OP_WORDS[leaf['op']]} {_fmt(rv)} (rule {leaf['clause']})."


def explain(rule: Rule, det: dict) -> str:
    if det["status"] == "TRUE":
        amt = det["amount"]
        if amt is None:
            return f"Meets every condition for {rule.name}."
        if det["amount_unit"] == "one_off":
            return f"Meets every condition for {rule.name}: a one-off £{amt:,.2f}."
        prefix = "at least " if det["amount_is_minimum"] else ""
        return f"Meets every condition for {rule.name}: {prefix}£{amt:,.2f} a week (about £{amt * 52 / 12:,.2f} a month)."
    if det["status"] == "FALSE":
        failing = list(_leaves(det["trace"], "FALSE"))
        return " ".join(_leaf_sentence(l, rule) for l in failing[:2]) or f"Does not meet the conditions for {rule.name}."
    return ""


def _question(rule: Rule, field: str) -> str:
    q = rule.questions.get(field)
    if q:
        return q
    return f"Can you confirm the household's {FIELDS.get(field, ('', field))[1].lower()}?"


def arbitrate(rule: Rule, det: dict, lane: dict) -> dict:
    """Returns {status, reason, question, question_field, cause, agreement}."""
    lane_status = lane.get("status")
    lane_dec = lane.get("decision")
    det_map = {"TRUE": "eligible", "FALSE": "not_eligible", "UNKNOWN": "cannot_decide"}
    det_dec = det_map[det["status"]]

    if det["status"] == "UNKNOWN":
        unk = det["unknown_fields"][0] if det["unknown_fields"] else {"field": "?", "reason": "missing"}
        reason_kind = unk["reason"].split(":")[0]
        detail = unk["reason"].split(":", 1)[1].strip() if ":" in unk["reason"] else ""
        return {
            "status": "needs_info",
            "reason": f"Cannot decide yet: {UNKNOWN_CAUSE.get(reason_kind, reason_kind)} about {_label(unk['field'])}" + (f" ({detail})." if detail else "."),
            "question": _question(rule, unk["field"]),
            "question_field": unk["field"],
            "cause": f"deterministic lane UNKNOWN ({reason_kind})",
            "agreement": lane_dec == "cannot_decide" if lane_status == "ok" else None,
        }
    if lane_status == "unavailable":
        return {"status": "eligible" if det["status"] == "TRUE" else "not_eligible", "reason": explain(rule, det),
                "question": None, "question_field": None, "cause": "single lane (reasoning lane unavailable)", "agreement": None}
    if lane_status == "invalid":
        f = _decisive_field(det)
        return {"status": "needs_info",
                "reason": f"The second check failed validation ({lane.get('error')}), so this is not confirmed. Rule engine says: {explain(rule, det)}",
                "question": _question(rule, f), "question_field": f, "cause": "invalid citation in reasoning lane", "agreement": False}
    if lane_dec == det_dec:
        return {"status": det_dec, "reason": explain(rule, det), "question": None, "question_field": None,
                "cause": None, "agreement": True}
    f = _decisive_field(det)
    return {
        "status": "needs_info",
        "reason": f"The two independent checks disagree (rule engine: {det_dec.replace('_', ' ')}; Nemotron: {lane_dec.replace('_', ' ')}). "
                  f"Nemotron: \"{lane.get('reason', '')}\"",
        "question": _question(rule, f),
        "question_field": f,
        "cause": "lanes disagree",
        "agreement": False,
    }


def _decisive_field(det: dict) -> str:
    target = "FALSE" if det["status"] == "FALSE" else "TRUE"
    for leaf in _leaves(det["trace"], target):
        if leaf["subject_kind"] == "field":
            return leaf["subject"]
        fields = det["derived"].get(leaf["subject"], {}).get("fields", [])
        if fields:
            return fields[0]
    return "weekly_income_total"
