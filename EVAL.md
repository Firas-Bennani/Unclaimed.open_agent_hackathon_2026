# Evaluation

_Generated 2026-10-27T15:01:36+00:00 by `python eval/run.py` — every number below comes from `eval/results.json`._

- **Households:** 70 synthetic households × 4 benefits = 280 decisions (248 decidable from the available evidence, 32 that should be escalated).
- **Ground truth:** eval/reference.py on observable facts (plain Python from policy text) + hand-labelled escalations.
- **Models:** reasoning `nvidia/nemotron-3-ultra-550b-a55b`, extraction `nvidia/nemotron-3.5-lightning-30b-a3b`.
- **Baseline:** the same Nemotron model given the policy text and every raw record for the household (SQL rows, CSV row, council account JSON, caseworker note), asked to decide each benefit. No DSL, no fact graph, no arbiter.
- **Latency** is per household: measured live call time (replayed from the cache on re-runs) plus local pipeline time.

| Metric | Standard agent (Nemotron, raw data + policy text) | Unclaimed (both lanes + arbiter) | Ablation: deterministic lane only |
|---|---|---|---|
| Accuracy on decidable cases | 79.4% | 97.6% | 100.0% |
| Wrong "yes" (count) | 24 | 0 | 0 |
| Wrong "yes" rate | 8.6% | 0.0% | 0.0% |
| Wrong "no" (count) | 1 | 0 | 0 |
| Wrong "no" rate | 0.4% | 0.0% | 0.0% |
| Escalations | 58 | 38 | 32 |
| Escalation precision | 29.3% | 84.2% | 100.0% |
| Escalation recall | 53.1% | 100.0% | 100.0% |
| Amount within £0.50 (correct yes) | 77.8% | 100.0% | 100.0% |
| Citation validity | 94.3% | 100.0% | 100.0% |
| Latency per household (s) | 139.7 | 147.6 | 3.5 |
| Tokens per household | 7,170 | 7,249 | 541 |

## Definitions

- *Decidable*: the reference implementation reaches yes/no from the facts a careful human could establish. Escalating a decidable case counts as not correct.
- *Wrong "yes"*: system said eligible when the expected answer was not "yes" (no, or escalate). This is the error that creates overpayment debt.
- *Wrong "no"*: system said not eligible when the expected answer was not "no".
- *Escalation precision / recall*: against the expected escalations (missing, conflicting or stale evidence).
- *Citation validity*: share of decisions whose cited clauses (and, for the baseline, record ids) exist. For Unclaimed, a decision counts as valid only if it cites a clause and the reasoning lane's citations all exist.

## Every disagreement with ground truth

| Household | Scenario | Benefit | System | Expected | Got |
|---|---|---|---|---|---|
| HH-001 | hero | pension_credit | unclaimed | yes | escalate |
| HH-001 | hero | council_tax_reduction | unclaimed | yes | escalate |
| HH-002 | clear_eligible | warm_home_discount | baseline | no | yes |
| HH-003 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-004 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-005 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-007 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-008 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-009 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-015 | couple_eligible | pension_credit | baseline | yes | escalate |
| HH-015 | couple_eligible | attendance_allowance | baseline | no | escalate |
| HH-015 | couple_eligible | council_tax_reduction | baseline | yes | escalate |
| HH-015 | couple_eligible | warm_home_discount | baseline | no | escalate |
| HH-016 | couple_eligible | attendance_allowance | baseline | no | escalate |
| HH-016 | couple_eligible | warm_home_discount | baseline | no | escalate |
| HH-017 | couple_eligible | attendance_allowance | baseline | no | escalate |
| HH-017 | couple_eligible | warm_home_discount | baseline | no | escalate |
| HH-018 | couple_eligible | attendance_allowance | baseline | no | escalate |
| HH-018 | couple_eligible | warm_home_discount | baseline | no | yes |
| HH-022 | clear_ineligible | warm_home_discount | baseline | no | escalate |
| HH-023 | clear_ineligible | warm_home_discount | baseline | no | escalate |
| HH-025 | care_eligible | warm_home_discount | baseline | no | yes |
| HH-027 | care_eligible | warm_home_discount | baseline | no | yes |
| HH-028 | care_eligible | warm_home_discount | baseline | no | yes |
| HH-032 | scotland | council_tax_reduction | baseline | no | escalate |
| HH-032 | scotland | council_tax_reduction | unclaimed | no | escalate |
| HH-033 | scotland | council_tax_reduction | baseline | no | escalate |
| HH-033 | scotland | council_tax_reduction | unclaimed | no | escalate |
| HH-034 | scotland | council_tax_reduction | baseline | no | escalate |
| HH-034 | scotland | council_tax_reduction | unclaimed | no | escalate |
| HH-036 | boundary | warm_home_discount | baseline | no | escalate |
| HH-037 | boundary | warm_home_discount | baseline | no | escalate |
| HH-040 | boundary | council_tax_reduction | baseline | no | yes |
| HH-040 | boundary | warm_home_discount | baseline | no | escalate |
| HH-041 | boundary | warm_home_discount | baseline | no | escalate |
| HH-042 | boundary | warm_home_discount | baseline | no | escalate |
| HH-043 | boundary | warm_home_discount | baseline | no | escalate |
| HH-044 | missing | warm_home_discount | baseline | no | escalate |
| HH-045 | missing | warm_home_discount | baseline | no | escalate |
| HH-047 | missing | warm_home_discount | baseline | no | yes |
| HH-049 | missing | council_tax_reduction | baseline | escalate | yes |
| HH-049 | missing | warm_home_discount | baseline | no | escalate |
| HH-051 | conflict | pension_credit | baseline | escalate | yes |
| HH-051 | conflict | council_tax_reduction | baseline | escalate | yes |
| HH-051 | conflict | warm_home_discount | baseline | no | yes |
| HH-052 | conflict | pension_credit | baseline | escalate | yes |
| HH-052 | conflict | council_tax_reduction | baseline | escalate | yes |
| HH-052 | conflict | warm_home_discount | baseline | no | escalate |
| HH-053 | conflict | pension_credit | baseline | escalate | yes |
| HH-053 | conflict | council_tax_reduction | baseline | escalate | yes |
| HH-053 | conflict | warm_home_discount | baseline | no | yes |
| HH-054 | conflict | pension_credit | baseline | escalate | yes |
| HH-054 | conflict | council_tax_reduction | baseline | escalate | yes |
| HH-054 | conflict | warm_home_discount | baseline | no | escalate |
| HH-055 | conflict | warm_home_discount | unclaimed | no | escalate |
| HH-056 | conflict | warm_home_discount | baseline | escalate | yes |
| HH-057 | conflict | warm_home_discount | baseline | escalate | yes |
| HH-058 | stale | warm_home_discount | baseline | no | escalate |
| HH-059 | stale | pension_credit | baseline | escalate | yes |
| HH-059 | stale | council_tax_reduction | baseline | escalate | yes |
| HH-059 | stale | warm_home_discount | baseline | no | escalate |
| HH-060 | stale | warm_home_discount | baseline | no | escalate |
| HH-061 | stale | warm_home_discount | baseline | no | escalate |
| HH-062 | stale | pension_credit | baseline | escalate | no |
| HH-062 | stale | council_tax_reduction | baseline | escalate | yes |
| HH-062 | stale | warm_home_discount | baseline | no | escalate |
| HH-063 | id_mismatch | warm_home_discount | baseline | no | escalate |
| HH-065 | id_mismatch | warm_home_discount | baseline | no | escalate |
| HH-066 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-067 | clear_eligible | warm_home_discount | baseline | no | escalate |
| HH-068 | clear_eligible | warm_home_discount | baseline | no | yes |
| HH-070 | clear_ineligible | warm_home_discount | baseline | no | escalate |
