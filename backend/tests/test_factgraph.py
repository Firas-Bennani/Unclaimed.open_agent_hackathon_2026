from datetime import date

from unclaimed.factgraph import resolve
from unclaimed.models import Fact


def fact(field, value, source="dwp", as_of=date(2026, 4, 1), conf=1.0, fid=None):
    return Fact(id=fid or f"{source}:{field}:{value}", field=field, value=value, source=source, source_label=source,
                record_id="r1", as_of=as_of, extraction_method="sql", confidence=conf)


def test_agreeing_sources_are_known():
    env, res, _ = resolve([fact("weekly_income_total", 200.0), fact("weekly_income_total", 200.4, "housing")])
    assert res["weekly_income_total"].state == "known"
    assert env.values["weekly_income_total"] == 200.0
    assert len(res["weekly_income_total"].fact_ids) == 2


def test_conflicting_sources_become_unknown():
    env, res, _ = resolve([fact("weekly_income_total", 200.0), fact("weekly_income_total", 231.5, "housing")])
    assert res["weekly_income_total"].state == "conflict"
    assert env.values["weekly_income_total"] is None
    assert "disagree" in env.unknown_reason["weekly_income_total"]


def test_approximate_note_within_tolerance_is_not_a_conflict():
    _, res, _ = resolve([fact("savings", 3200.0), fact("savings", 3000.0, "notes", conf=0.7)])
    assert res["savings"].state == "known" and res["savings"].value == 3200.0


def test_stale_only_record_is_unknown_and_fresh_supersedes_stale():
    _, res, _ = resolve([fact("weekly_income_total", 190.0, as_of=date(2024, 6, 3))])
    assert res["weekly_income_total"].state == "stale"
    _, res, facts = resolve([fact("weekly_income_total", 190.0, "housing", as_of=date(2024, 6, 3)),
                             fact("weekly_income_total", 194.65)])
    assert res["weekly_income_total"].state == "known" and res["weekly_income_total"].value == 194.65
    assert any(f.status == "stale" for f in facts)


def test_bool_conflict():
    _, res, _ = resolve([fact("electricity_bill_in_name", True, "housing"), fact("electricity_bill_in_name", False, "notes")])
    assert res["electricity_bill_in_name"].state == "conflict"


def test_caseworker_override_wins_and_supersedes():
    cw = fact("weekly_income_total", 210.0, "caseworker", fid="caseworker:1")
    env, res, facts = resolve([fact("weekly_income_total", 200.0), fact("weekly_income_total", 231.5, "housing")], [cw])
    assert res["weekly_income_total"].state == "known" and env.values["weekly_income_total"] == 210.0
    assert res["weekly_income_total"].fact_ids == ["caseworker:1"]


def test_derived_age_and_single_partner_spa():
    env, res, _ = resolve([fact("date_of_birth", "1959-03-14"), fact("has_partner", False)])
    assert env.values["age_years"] == 67 and env.values["state_pension_age"] == 66
    assert env.values["partner_reached_spa"] is False
