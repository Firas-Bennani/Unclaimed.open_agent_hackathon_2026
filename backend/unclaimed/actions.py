"""Actions: decision records and pre-filled application drafts (markdown)."""
from __future__ import annotations

from datetime import date

FORM = {
    "pension_credit": ("Pension Credit claim", "Apply online at https://www.gov.uk/pension-credit/how-to-claim or call the Pension Credit claim line."),
    "attendance_allowance": ("Attendance Allowance claim form (AA1)", "Download the AA1 form from https://www.gov.uk/attendance-allowance/how-to-claim."),
    "council_tax_reduction": ("Council Tax Reduction application", "Apply to the local council: https://www.gov.uk/council-tax-reduction."),
    "warm_home_discount": ("Warm Home Discount", "Usually automatic once a qualifying benefit is in payment; otherwise call the Warm Home Discount helpline."),
}
FIELD_ROWS = {
    "pension_credit": ["full_name", "date_of_birth", "country", "has_partner", "weekly_income_total", "savings"],
    "attendance_allowance": ["full_name", "date_of_birth", "needs_care_help", "care_need_months", "care_day_and_night", "in_gb_2_of_last_3_years"],
    "council_tax_reduction": ["full_name", "date_of_birth", "council_tax_annual_net", "weekly_income_total", "savings", "receives_pension_credit"],
    "warm_home_discount": ["full_name", "receives_qualifying_benefit_on_whd_date", "electricity_bill_in_name"],
}


def _v(x) -> str:
    if isinstance(x, bool):
        return "Yes" if x else "No"
    if isinstance(x, float):
        return f"{x:,.2f}"
    return "—" if x is None else str(x)


def _facts_by_id(a: dict) -> dict:
    return {f["id"]: f for f in a["facts"]}


def application_draft(a: dict, benefit: str) -> dict:
    d = next((x for x in a["decisions"] if x["benefit"] == benefit), None)
    if d is None:
        raise ValueError(f"unknown benefit {benefit}")
    if d["status"] != "eligible":
        raise ValueError("drafts are only produced for benefits the household is eligible for")
    title, how = FORM[benefit]
    hh = a["household"]
    facts = _facts_by_id(a)
    lines = [f"# DRAFT — {title}", "",
             f"Prepared by Unclaimed on {date.today().isoformat()} for caseworker review. **Not submitted. Check every answer with the claimant.**", "",
             f"**Claimant:** {hh['name']}  ·  **NI number:** {hh['ni']}  ·  **Postcode:** {hh['postcode']}", "",
             "| Question | Pre-filled answer | Evidence |", "|---|---|---|"]
    for field in FIELD_ROWS[benefit]:
        r = a["resolved"].get(field, {})
        ev = "; ".join(f"{facts[i]['source_label']} `{facts[i]['record_id']}`" for i in r.get("fact_ids", []) if i in facts) or "—"
        val = r.get("value") if r.get("state") == "known" else f"⚠ {r.get('state', 'missing')} — ask claimant"
        lines.append(f"| {field.replace('_', ' ').capitalize()} | {_v(val)} | {ev} |")
    amt = (f"£{d['amount_weekly']:,.2f} a week (≈ £{d['amount_monthly']:,.2f} a month)" if d["amount_weekly"]
           else f"£{d['amount_one_off']:,.2f} one-off" if d["amount_one_off"] else "—")
    lines += ["", f"**Estimated entitlement:** {amt} (rule version {d['rule_version']})", "",
              "**Why we think they qualify:** " + d["reason"], "", "**Rules relied on:**"]
    lines += [f"- [{c['id']}] {c['text']} — {c['source_url']}" for c in d["clauses"]]
    lines += ["", f"**How to submit:** {how}", ""]
    return {"benefit": benefit, "title": title, "markdown": "\n".join(lines)}


def decision_record(a: dict) -> dict:
    """Self-contained, auditable record of the assessment."""
    return {
        "household": a["household"],
        "run_id": a["run_id"],
        "assessed_at": a["assessed_at"],
        "rule_versions": a["rule_versions"],
        "backends": a["backends"],
        "decisions": [{k: d[k] for k in ("benefit", "status", "amount_weekly", "amount_monthly", "amount_one_off", "reason",
                                         "question", "escalation_cause", "clauses", "fact_ids")} for d in a["decisions"]],
        "evidence": [f for f in a["facts"] if any(f["id"] in d["fact_ids"] for d in a["decisions"])],
        "corrections": a.get("corrections", []),
    }
