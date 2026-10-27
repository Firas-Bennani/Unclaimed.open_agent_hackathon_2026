import pytest
from pydantic import ValidationError

from unclaimed.dsl import Cond, Rule, Tri, eval_cond, evaluate, validate_rule
from unclaimed.engine import env_from_values


def leaf(field, op, value, clause="C-1"):
    return {"field": field, "op": op, "value": value, "clause": clause}


def make_rule(elig, amount=None, derived=None):
    return Rule.model_validate({
        "id": "t", "benefit": "t", "name": "Test", "version": "1", "jurisdiction": ["England"],
        "sources": [{"url": "https://example.org", "title": "t", "retrieved": "2026-10-27"}],
        "clauses": [{"id": "C-1", "text": "x", "source_url": "https://example.org"},
                    {"id": "C-2", "text": "y", "source_url": "https://example.org"}],
        "derived": derived or [],
        "eligibility": elig,
        "amount": amount or {"expr": {"const": 10}, "unit": "weekly", "clause": "C-2"},
    })


@pytest.mark.parametrize("a,b,all_,any_", [
    (True, True, Tri.T, Tri.T), (True, False, Tri.F, Tri.T), (True, None, Tri.U, Tri.T),
    (False, None, Tri.F, Tri.U), (None, None, Tri.U, Tri.U), (False, False, Tri.F, Tri.F),
])
def test_kleene_truth_tables(a, b, all_, any_):
    env = env_from_values({"needs_care_help": a, "electricity_bill_in_name": b})
    parts = [leaf("needs_care_help", "==", True), leaf("electricity_bill_in_name", "==", True)]
    assert eval_cond(Cond.model_validate({"all": parts}), env)[0] == all_
    assert eval_cond(Cond.model_validate({"any": parts}), env)[0] == any_


def test_not_unknown_stays_unknown():
    env = env_from_values({"needs_care_help": None})
    c = Cond.model_validate({"not": leaf("needs_care_help", "==", True)})
    assert eval_cond(c, env)[0] == Tri.U


def test_leaf_requires_clause():
    with pytest.raises(ValidationError):
        Cond.model_validate({"field": "savings", "op": ">", "value": 1})


def test_condition_must_be_one_kind():
    with pytest.raises(ValidationError):
        Cond.model_validate({"all": [], "field": "savings", "op": ">", "value": 1, "clause": "C-1"})


def test_unknown_op_rejected():
    with pytest.raises(ValidationError):
        Cond.model_validate(leaf("savings", "~=", 1))


def test_semantic_validation_catches_unknown_field_and_clause():
    r = make_rule({"all": [leaf("shoe_size", ">", 3), leaf("savings", "<", 5, clause="NOPE")]})
    errs = validate_rule(r)
    assert any("shoe_size" in e for e in errs)
    assert any("NOPE" in e for e in errs)


def test_derived_and_amount_with_unknown_reports_blocking_field():
    r = make_rule(
        {"derived": "assessed", "op": "<", "value": 238, "clause": "C-1"},
        amount={"expr": {"op": "sub", "args": [{"const": 238}, {"derived": "assessed"}]}, "unit": "weekly", "clause": "C-2"},
        derived=[{"name": "assessed", "clause": "C-1", "expr": {"op": "add", "args": [{"field": "weekly_income_total"}, {"field": "savings"}]}}],
    )
    out = evaluate(r, env_from_values({"weekly_income_total": 200, "savings": None}, reasons={"savings": "conflict: x"}))
    assert out["status"] == "UNKNOWN"
    assert out["unknown_fields"] == [{"field": "savings", "reason": "conflict: x"}]
    out = evaluate(r, env_from_values({"weekly_income_total": 200, "savings": 0}))
    assert out["status"] == "TRUE" and out["amount"] == 38


def test_expression_as_comparison_value():
    r = make_rule(leaf("weekly_income_total", "<", {"op": "add", "args": [{"const": 200}, {"field": "savings"}]}))
    assert evaluate(r, env_from_values({"weekly_income_total": 210, "savings": 20}))["status"] == "TRUE"
    out = evaluate(r, env_from_values({"weekly_income_total": 210, "savings": None}))
    assert out["status"] == "UNKNOWN" and out["unknown_fields"][0]["field"] == "savings"
