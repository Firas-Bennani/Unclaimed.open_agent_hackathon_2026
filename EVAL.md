# Evaluation

_Generated 2026-10-27T17:02:39+00:00 by `python eval/run.py` — every number below comes from `eval/results.json`._

- **Households:** 70 synthetic households × 4 benefits = 280 decisions (248 decidable from the available evidence, 32 that should be escalated).
- **Ground truth:** eval/reference.py on observable facts (plain Python from policy text) + hand-labelled escalations.
- **Models:** reasoning `nvidia/nemotron-3-ultra-550b-a55b`, extraction `nvidia/nemotron-3.5-lightning-30b-a3b`.
- **Baseline:** the same Nemotron model given the policy text and every raw record for the household (SQL rows, CSV row, council account JSON, caseworker note), asked to decide each benefit. No DSL, no fact graph, no arbiter.
- **Latency** is per household: measured live call time (replayed from the cache on re-runs) plus local pipeline time.

| Metric | Standard agent (Nemotron, raw data + policy text) | Unclaimed (both lanes + arbiter) | Ablation: deterministic lane only |
|---|---|---|---|
| Accuracy on decidable cases | 79.4% | 98.4% | 100.0% |
| Coverage (share of decisions made, not escalated) | 77.9% | 87.1% | 88.6% |
| Selective accuracy (correct among decisions made) | 90.4% | 100.0% | 100.0% |
| Wrong "yes" (count) | 21 | 0 | 0 |
| Wrong "yes" rate | 7.5% | 0.0% | 0.0% |
| Wrong "no" (count) | 0 | 0 | 0 |
| Wrong "no" rate | 0.0% | 0.0% | 0.0% |
| Escalations | 62 | 36 | 32 |
| Escalation precision | 32.3% | 88.9% | 100.0% |
| Escalation recall | 62.5% | 100.0% | 100.0% |
| Amount within £0.50 (correct yes) | 77.2% | 100.0% | 100.0% |
| Citation validity | 98.9% | 100.0% | 100.0% |
| Latency per household (s) | 154.6 | 144.2 | 3.4 |
| Tokens per household | 7,379 | 7,241 | 541 |

## Definitions

- *Decidable*: the reference implementation reaches yes/no from the facts a careful human could establish. Escalating a decidable case counts as not correct.
- *Wrong "yes"*: system said eligible when the expected answer was not "yes" (no, or escalate). This is the error that creates overpayment debt.
- *Wrong "no"*: system said not eligible when the expected answer was not "no".
- *Escalation precision / recall*: against the expected escalations (missing, conflicting or stale evidence).
- *Citation validity*: share of decisions whose cited clauses (and, for the baseline, record ids) exist. For Unclaimed, a decision counts as valid only if it cites a clause and the reasoning lane's citations all exist.

## Why Unclaimed escalated when the evidence was sufficient

4 unnecessary escalation(s). By cause: lanes disagree: 4.

| Household | Scenario | Benefit | Expected | Rule engine | Nemotron | Cause | Nemotron's reason |
|---|---|---|---|---|---|---|---|
| HH-026 | care_eligible | warm_home_discount | yes | yes | cannot_decide | lanes disagree | Claimant lives in England and received a qualifying benefit on 23 August 2026, but there is no dated confirmation that the electricity bill was in their name on that specific date. |
| HH-032 | scotland | council_tax_reduction | no | no | cannot_decide | lanes disagree | The provided Council Tax Reduction model only covers pensioners in England and Wales, but the claimant lives in Scotland. |
| HH-033 | scotland | council_tax_reduction | no | no | cannot_decide | lanes disagree | The provided rule clauses only model the Council Tax Reduction scheme for pensioners in England and Wales; the claimant resides in Scotland, so eligibility cannot be determined from these rules. |
| HH-034 | scotland | council_tax_reduction | no | no | cannot_decide | lanes disagree | The provided Council Tax Reduction model covers only England and Wales, but Beryl lives in Scotland; Scottish scheme rules are not provided. |

**Analysis (hand-written after the run).** All 4 come from the reasoning lane refusing to agree; none come from invalid citations or UNKNOWN facts.
- **HH-032/033/034 (Scotland, CTR):** the rule pack models only the England & Wales pensioner scheme, so the rule engine says "not eligible". Nemotron points out that Scotland has its own scheme, which isn't modelled. That's a fair objection to our labels: the honest answer is "out of scope", not "no". We kept the labels and count these against Unclaimed.
- **HH-026 (WHD):** Nemotron wants evidence that the electricity bill was in the claimant's name *on 23 August 2026*. Our housing export has no date for that field. It's a stricter reading of the rule than ours, not a lane bug.

**Why the deterministic lane alone scores 100% here.** The labels are produced by a reference implementation of the same simplified policy, and on this synthetic set the compiled rules and the notes extraction are both correct (rule examples pass; extraction was validated on all 70 notes). So the rule engine can't be beaten on this set. The reasoning lane is there as an **independent cross-check against rule-compilation and extraction errors**, which this test set doesn't contain. Here it only adds 4 escalations (coverage 87.1% vs 88.6%). We keep it because in production rules get mis-compiled and notes get mis-read, and a second, independent reader is what catches that. We have not shown that benefit on this test set.

**Run history (all kept in `eval/`).** Run 1 (46/70, `results_superseded_run1.json`) showed two real faults: notes extraction dropped negative statements, and the reasoning lane treated April-2026 records as stale. Run 2 (`results_superseded_run2.json`, `EVAL_superseded_run2.md`) showed the reasoning lane reading £3,200 (DWP) vs "about £3,000" (note) as a conflict. The fixes were general policies given to the reasoning lane *and* the baseline (freshness: 400 days; an approximate note within 10% of a record is not a conflict), plus a better extraction prompt. No household-specific rules were added. This file is run 3, with every household scored on the same code version.

## Every disagreement with ground truth

| Household | Scenario | Benefit | System | Expected | Got |
|---|---|---|---|---|---|
| HH-002 | clear_eligible | warm_home_discount | baseline | no | yes |
| HH-003 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-004 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-005 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-006 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-007 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-008 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-009 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-015 | couple_eligible | attendance_allowance | baseline | no | escalate |
| HH-015 | couple_eligible | warm_home_discount | baseline | no | escalate |
| HH-016 | couple_eligible | attendance_allowance | baseline | no | escalate |
| HH-016 | couple_eligible | warm_home_discount | baseline | no | escalate |
| HH-017 | couple_eligible | attendance_allowance | baseline | no | escalate |
| HH-017 | couple_eligible | warm_home_discount | baseline | no | escalate |
| HH-018 | couple_eligible | attendance_allowance | baseline | no | escalate |
| HH-018 | couple_eligible | warm_home_discount | baseline | no | escalate |
| HH-019 | clear_ineligible | warm_home_discount | baseline | no | escalate |
| HH-023 | clear_ineligible | warm_home_discount | baseline | no | escalate |
| HH-025 | care_eligible | warm_home_discount | baseline | no | escalate |
| HH-026 | care_eligible | warm_home_discount | unclaimed | yes | escalate |
| HH-027 | care_eligible | warm_home_discount | baseline | no | escalate |
| HH-028 | care_eligible | warm_home_discount | baseline | no | escalate |
| HH-030 | under_spa | warm_home_discount | baseline | no | escalate |
| HH-032 | scotland | council_tax_reduction | baseline | no | escalate |
| HH-032 | scotland | council_tax_reduction | unclaimed | no | escalate |
| HH-033 | scotland | council_tax_reduction | baseline | no | yes |
| HH-033 | scotland | council_tax_reduction | unclaimed | no | escalate |
| HH-034 | scotland | council_tax_reduction | baseline | no | escalate |
| HH-034 | scotland | council_tax_reduction | unclaimed | no | escalate |
| HH-036 | boundary | warm_home_discount | baseline | no | escalate |
| HH-037 | boundary | warm_home_discount | baseline | no | yes |
| HH-040 | boundary | council_tax_reduction | baseline | no | yes |
| HH-040 | boundary | warm_home_discount | baseline | no | yes |
| HH-041 | boundary | warm_home_discount | baseline | no | yes |
| HH-042 | boundary | warm_home_discount | baseline | no | escalate |
| HH-043 | boundary | warm_home_discount | baseline | no | escalate |
| HH-044 | missing | warm_home_discount | baseline | no | escalate |
| HH-045 | missing | warm_home_discount | baseline | no | escalate |
| HH-047 | missing | warm_home_discount | baseline | no | escalate |
| HH-049 | missing | council_tax_reduction | baseline | escalate | yes |
| HH-049 | missing | warm_home_discount | baseline | no | escalate |
| HH-050 | missing | warm_home_discount | baseline | no | escalate |
| HH-051 | conflict | pension_credit | baseline | escalate | yes |
| HH-051 | conflict | council_tax_reduction | baseline | escalate | yes |
| HH-051 | conflict | warm_home_discount | baseline | no | escalate |
| HH-052 | conflict | pension_credit | baseline | escalate | yes |
| HH-052 | conflict | council_tax_reduction | baseline | escalate | yes |
| HH-052 | conflict | warm_home_discount | baseline | no | escalate |
| HH-053 | conflict | pension_credit | baseline | escalate | yes |
| HH-053 | conflict | council_tax_reduction | baseline | escalate | yes |
| HH-054 | conflict | pension_credit | baseline | escalate | yes |
| HH-054 | conflict | council_tax_reduction | baseline | escalate | yes |
| HH-054 | conflict | warm_home_discount | baseline | no | yes |
| HH-055 | conflict | warm_home_discount | baseline | no | escalate |
| HH-056 | conflict | warm_home_discount | baseline | escalate | yes |
| HH-058 | stale | warm_home_discount | baseline | no | escalate |
| HH-059 | stale | pension_credit | baseline | escalate | yes |
| HH-059 | stale | council_tax_reduction | baseline | escalate | yes |
| HH-059 | stale | warm_home_discount | baseline | no | escalate |
| HH-060 | stale | warm_home_discount | baseline | no | escalate |
| HH-061 | stale | warm_home_discount | baseline | no | yes |
| HH-062 | stale | warm_home_discount | baseline | no | escalate |
| HH-063 | id_mismatch | warm_home_discount | baseline | no | yes |
| HH-065 | id_mismatch | warm_home_discount | baseline | no | escalate |
| HH-066 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-067 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-068 | clear_eligible | warm_home_discount | baseline | no | escalate |
