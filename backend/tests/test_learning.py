import json

from unclaimed import learning
from unclaimed.memory import get_memory


def _paths_with(doc, value, prefix=""):
    """JSON-pointer paths of every numeric leaf equal to `value`."""
    if isinstance(doc, dict):
        for k, v in doc.items():
            yield from _paths_with(v, value, f"{prefix}/{k}")
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            yield from _paths_with(v, value, f"{prefix}/{i}")
    elif isinstance(doc, (int, float)) and not isinstance(doc, bool) and abs(doc - value) < 1e-9:
        yield prefix


def _fake_llm(ops):
    def fake(model, system, user, schema, validate=None, **kw):
        p = schema.model_validate({"rationale": "test", "ops": ops, "new_version": "2026-27-test"})
        assert validate is None or validate(p) == []
        return p, learning.llm.LLMMeta(model, True, 0, 0, 0, 1, "cache")
    return fake


def _seeded_rule_json():
    learning.demo_seed_pack()
    return get_memory().active_rules()["pension_credit"]["rule"]


def test_patch_restoring_current_rates_is_accepted(monkeypatch):
    rule = _seeded_rule_json()
    ops = [{"op": "replace", "path": p, "value": 238.0} for p in _paths_with(rule, 227.1)]
    ops += [{"op": "replace", "path": p, "value": 363.25} for p in _paths_with(rule, 346.6)]
    assert ops
    monkeypatch.setattr(learning.llm, "chat_json", _fake_llm(ops))
    rec = learning.propose_and_gate("HH-036", "pension_credit", "eligible", "2026-27 rates")
    assert rec["status"] == "accepted", rec
    assert rec["gate"]["regressions"] == [] and rec["gate"]["target_fixed"]
    assert get_memory().active_rules()["pension_credit"]["rule"]["version"] == "2026-27-test"


def test_patch_that_causes_regressions_is_rejected(monkeypatch):
    rule = _seeded_rule_json()
    # Absurdly generous threshold: fixes the target but breaks many correct "no" decisions.
    ops = [{"op": "replace", "path": p, "value": 900.0} for p in _paths_with(rule, 227.1)]
    monkeypatch.setattr(learning.llm, "chat_json", _fake_llm(ops))
    rec = learning.propose_and_gate("HH-036", "pension_credit", "eligible", "make everyone eligible")
    assert rec["status"] == "rejected" and rec["gate"]["regressions"]
    assert get_memory().active_rules()["pension_credit"]["rule"]["version"] == "2025-26"


def test_unappliable_patch_is_rejected(monkeypatch):
    _seeded_rule_json()
    monkeypatch.setattr(learning.llm, "chat_json", lambda *a, **k: (learning.PatchProposal.model_validate(
        {"rationale": "x", "ops": [{"op": "replace", "path": "/derived/99/nope", "value": 1}], "new_version": "x"}),
        learning.llm.LLMMeta("m", True, 0, 0, 0, 1, "cache")))
    rec = learning.propose_and_gate("HH-036", "pension_credit", "eligible", "x")
    assert rec["status"] == "rejected" and "valid rule" in rec["reason"]
    assert json.dumps(rec)  # record is serialisable for the UI
