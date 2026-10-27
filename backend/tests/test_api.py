from fastapi.testclient import TestClient

from unclaimed.api import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert "data" in r.json()["backends"]


def test_maria_assessment_shape_and_hero_outcomes():
    r = client.post("/api/households/HH-001/assess")
    assert r.status_code == 200
    a = r.json()
    d = {x["benefit"]: x for x in a["decisions"]}
    assert d["pension_credit"]["status"] == "eligible"
    assert d["council_tax_reduction"]["status"] == "eligible"
    assert d["attendance_allowance"]["status"] == "needs_info"
    assert d["attendance_allowance"]["question_field"] == "care_need_months"
    assert d["warm_home_discount"]["status"] == "not_eligible"
    assert {s["source"] for s in a["sources"]} >= {"dwp", "housing", "council", "notes"}
    for x in a["decisions"]:
        assert x["clauses"], "every conclusion carries a rule clause"
        assert all(c["source_url"].startswith("https://") for c in x["clauses"])


def test_answering_question_changes_result_live():
    r = client.post("/api/households/HH-001/facts", json={"field": "care_need_months", "value": 7, "note": "since March"})
    assert r.status_code == 200
    body = r.json()
    aa = next(x for x in body["assessment"]["decisions"] if x["benefit"] == "attendance_allowance")
    assert aa["status"] == "eligible" and aa["amount_weekly"] == 76.7
    assert any(c["benefit"] == "attendance_allowance" and c["to"] == "eligible" for c in body["changes"])


def test_unknown_field_rejected_and_unknown_household_404():
    assert client.post("/api/households/HH-001/facts", json={"field": "shoe_size", "value": 9}).status_code == 422
    assert client.get("/api/households/HH-999").status_code == 404


def test_draft_only_for_eligible():
    assert client.get("/api/households/HH-001/drafts/pension_credit").status_code == 200
    assert client.get("/api/households/HH-001/drafts/warm_home_discount").status_code == 409


def test_household_list():
    r = client.get("/api/households")
    assert r.status_code == 200 and len(r.json()["households"]) >= 60
