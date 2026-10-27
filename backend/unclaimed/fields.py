"""Canonical fact catalogue shared by the harness, the DSL and the prompts."""
from __future__ import annotations

FIELDS: dict[str, tuple[str, str]] = {
    # name: (type, description)
    "full_name": ("str", "Claimant's full name"),
    "date_of_birth": ("date", "Claimant's date of birth"),
    "age_years": ("number", "Claimant's age in whole years on the assessment date (derived from date_of_birth)"),
    "state_pension_age": ("number", "Claimant's State Pension age in years (derived from date_of_birth; simplified)"),
    "country": ("str", "Country of residence: England, Wales, Scotland or Northern Ireland"),
    "has_partner": ("bool", "Claimant lives with a partner"),
    "partner_reached_spa": ("bool", "Partner has reached State Pension age (false if no partner)"),
    "weekly_income_total": ("number", "Total weekly income in GBP: State Pension + private/occupational pensions + other income, for claimant and partner"),
    "savings": ("number", "Savings and investments (capital) in GBP, claimant and partner"),
    "receives_pension_credit": ("bool", "Pension Credit currently in payment"),
    "receives_housing_benefit": ("bool", "Housing Benefit currently in payment"),
    "receives_qualifying_benefit_on_whd_date": ("bool", "Pension Credit, Housing Benefit, Universal Credit or income-related ESA was in payment on 23 August 2026"),
    "receives_dla_or_pip": ("bool", "Disability Living Allowance, PIP or Adult Disability Payment in payment"),
    "needs_care_help": ("bool", "Needs help with personal care or supervision because of a disability or health condition"),
    "care_need_months": ("number", "How many months the claimant has needed that help"),
    "care_day_and_night": ("bool", "Needs help both during the day and at night"),
    "in_gb_2_of_last_3_years": ("bool", "Has been in Great Britain for at least 2 of the last 3 years"),
    "council_tax_liable": ("bool", "Claimant is liable to pay council tax for the home"),
    "council_tax_annual_net": ("number", "Annual council tax charge in GBP after any single person discount"),
    "electricity_bill_in_name": ("bool", "Claimant's (or partner's) name is on the electricity bill"),
    "tenure": ("str", "rent or own"),
}

FIELD_NAMES = set(FIELDS)
