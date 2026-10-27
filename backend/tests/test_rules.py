import pytest

from unclaimed.compiler import check_examples
from unclaimed.dsl import validate_rule
from unclaimed.engine import BENEFITS, load_rule


@pytest.mark.parametrize("benefit", BENEFITS)
def test_compiled_rule_is_valid_and_cited(benefit):
    rule = load_rule(benefit)
    assert validate_rule(rule) == []
    assert all(c.source_url.startswith("https://www.gov.uk") or "legislation.gov.uk" in c.source_url for c in rule.clauses)


@pytest.mark.parametrize("benefit", BENEFITS)
def test_compiled_rule_passes_hand_written_examples(benefit):
    assert check_examples(load_rule(benefit)) == []
