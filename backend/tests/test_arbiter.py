from unclaimed import reasoning
from unclaimed.arbiter import arbitrate
from unclaimed.dsl import evaluate
from unclaimed.engine import env_from_values, load_rule
from unclaimed.models import Fact, ResolvedFact

MARIA = {"country": "England", "age_years": 67, "state_pension_age": 66, "has_partner": False, "partner_reached_spa": False,
         "weekly_income_total": 194.65, "savings": 3200}


def det(values):
    return evaluate(load_rule("pension_credit"), env_from_values(values))


def lane(decision, status="ok"):
    return {"status": status, "decision": decision, "reason": "because", "clause_ids": ["PC-4"], "fact_ids": []}


def test_agreement_decides():
    a = arbitrate(load_rule("pension_credit"), det(MARIA), lane("eligible"))
    assert a["status"] == "eligible" and a["agreement"] is True and "£43.35" in a["reason"]


def test_disagreement_escalates_with_question():
    a = arbitrate(load_rule("pension_credit"), det(MARIA), lane("not_eligible"))
    assert a["status"] == "needs_info" and a["question"] and a["cause"] == "lanes disagree"


def test_unknown_escalates_with_field_question():
    a = arbitrate(load_rule("pension_credit"), det({**MARIA, "weekly_income_total": None}), lane("eligible"))
    assert a["status"] == "needs_info" and a["question_field"] == "weekly_income_total"


def test_invalid_citation_escalates():
    a = arbitrate(load_rule("pension_credit"), det(MARIA), {"status": "invalid", "error": "cited non-existent clauses ['PC-99']"})
    assert a["status"] == "needs_info" and "invalid citation" in a["cause"]


def test_reasoning_lane_unavailable_uses_single_lane():
    a = arbitrate(load_rule("pension_credit"), det(MARIA), {"status": "unavailable"})
    assert a["status"] == "eligible" and "single lane" in a["cause"]


def test_reasoning_lane_rejects_nonexistent_citations(monkeypatch):
    pack = {"pension_credit": load_rule("pension_credit")}
    facts = [Fact(id="dwp:x:weekly_income_total", field="weekly_income_total", value=194.65, source="dwp",
                  source_label="DWP", record_id="x", extraction_method="sql")]
    resolved = {"weekly_income_total": ResolvedFact(field="weekly_income_total", value=194.65, state="known")}

    def fake(model, system, user, schema, **kw):
        out = schema.model_validate({"decisions": [{"benefit": "pension_credit", "decision": "eligible", "weekly_amount": 43.35,
                                                     "clause_ids": ["PC-4", "PC-99"], "fact_ids": ["F1", "F7"], "reason": "r"}]})
        return out, reasoning.llm.LLMMeta(model, True, 0, 0, 0, 1, "cache")

    monkeypatch.setattr(reasoning.llm, "chat_json", fake)
    res, _ = reasoning.run(pack, facts, resolved)
    r = res["pension_credit"]
    assert r["status"] == "invalid" and "PC-99" in r["error"] and "F7" in r["error"]
    assert r["fact_ids"][0] == "dwp:x:weekly_income_total"
