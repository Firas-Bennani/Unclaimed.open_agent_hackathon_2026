"""Independent reference implementation, written directly from the policy text in
rules/sources/*.md. It does NOT use the DSL, the engine, the harness or any LLM.

Input: a dict of facts where None means "cannot be established".
Output per benefit: "yes" | "no" | "escalate" (and the weekly / one-off amount for "yes").
"""
from __future__ import annotations

import math

PC_SINGLE, PC_COUPLE = 238.00, 363.25
AA_LOWER, AA_HIGHER = 76.70, 114.60
CTR_CAPITAL_LIMIT = 16000
WHD_AMOUNT = 150.0


def _tariff(savings: float) -> float:
    if savings <= 10000:
        return 0.0
    return float(math.ceil((savings - 10000) / 500))


def pension_credit(f: dict):
    if f["country"] is None:
        return "escalate", None
    if f["country"] not in ("England", "Scotland", "Wales"):
        return "no", None
    if f["age_years"] is None:
        return "escalate", None
    if f["age_years"] < f["state_pension_age"]:
        return "no", None
    if f["has_partner"] is None:
        return "escalate", None
    if f["has_partner"]:
        if f["partner_reached_spa"] is None:
            return "escalate", None
        if not f["partner_reached_spa"]:
            return "no", None
    threshold = PC_COUPLE if f["has_partner"] else PC_SINGLE
    income = f["weekly_income_total"]
    if income is None:
        return "escalate", None
    if income >= threshold:  # tariff income can only add to income
        return "no", None
    if f["savings"] is None:
        return "escalate", None
    assessed = income + _tariff(f["savings"])
    if assessed < threshold:
        return "yes", round(threshold - assessed, 2)
    return "no", None


def attendance_allowance(f: dict):
    # Every condition must hold; any definite failure is a "no" even if other facts are unknown.
    checks = [
        None if f["country"] is None else f["country"] in ("England", "Wales"),
        None if f["age_years"] is None else f["age_years"] >= f["state_pension_age"],
        f["needs_care_help"],
        None if f["care_need_months"] is None else f["care_need_months"] >= 6,
        f["in_gb_2_of_last_3_years"],
        None if f["receives_dla_or_pip"] is None else not f["receives_dla_or_pip"],
    ]
    if any(c is False for c in checks):
        return "no", None
    if any(c is None for c in checks):
        return "escalate", None
    return "yes", AA_HIGHER if f["care_day_and_night"] else AA_LOWER


def council_tax_reduction(f: dict):
    basic = [
        None if f["country"] is None else f["country"] in ("England", "Wales"),
        None if f["age_years"] is None else f["age_years"] >= f["state_pension_age"],
        f["council_tax_liable"],
    ]
    if any(c is False for c in basic):
        return "no", None
    if f["receives_pension_credit"] is True and all(c is True for c in basic):
        if f["council_tax_annual_net"] is None:
            return "yes", None
        return "yes", round(f["council_tax_annual_net"] / 52, 2)
    # income-based route
    if f["savings"] is not None and f["savings"] > CTR_CAPITAL_LIMIT:
        income_route = False
    elif None in (f["savings"], f["weekly_income_total"], f["council_tax_annual_net"], f["has_partner"]):
        income_route = None
    else:
        applicable = PC_COUPLE if f["has_partner"] else PC_SINGLE
        weekly_charge = f["council_tax_annual_net"] / 52
        excess = max(0.0, f["weekly_income_total"] + _tariff(f["savings"]) - applicable)
        reduction = max(0.0, weekly_charge - 0.2 * excess)
        income_route = reduction > 0
    if f["receives_pension_credit"] is None and income_route is not True:
        return ("escalate", None) if not any(c is False for c in basic) else ("no", None)
    if income_route is False:
        return "no", None
    if income_route is None or any(c is None for c in basic):
        return "escalate", None
    return "yes", round(reduction, 2)


def warm_home_discount(f: dict):
    checks = [
        None if f["country"] is None else f["country"] in ("England", "Wales"),
        f["receives_qualifying_benefit_on_whd_date"],
        f["electricity_bill_in_name"],
    ]
    if any(c is False for c in checks):
        return "no", None
    if any(c is None for c in checks):
        return "escalate", None
    return "yes", WHD_AMOUNT


REFERENCE = {
    "pension_credit": pension_credit,
    "attendance_allowance": attendance_allowance,
    "council_tax_reduction": council_tax_reduction,
    "warm_home_discount": warm_home_discount,
}


def decide_all(facts: dict) -> dict:
    return {b: dict(zip(("decision", "amount"), fn(facts))) for b, fn in REFERENCE.items()}
