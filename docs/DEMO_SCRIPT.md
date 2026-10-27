# Demo script (~3 minutes)

**Before recording**

1. `powershell -File scripts/demo.ps1` (or `make demo`). This builds the UI, resets memory, seeds the demo rule pack and assesses all 70 households from the replay cache. Wait for `Open http://localhost:8000`.
2. Open http://localhost:8000 in a browser at 1440×900, zoom 100%. Check that the header shows **Demo mode ON** and the badges *Nemotron ✓ replay cache · Data: local federation · Memory: SQLite*.
3. For a clean re-take, click **Reset demo** on the dashboard (takes a few seconds).

Type the inputs below exactly as written. The replay cache was recorded with these exact strings (`scripts/rehearse.py`). With different text, Demo mode has no recorded answer and the reasoning lane shows "unavailable".

---

## 1 · Problem + user (0:00–0:20) — Dashboard

**Show:** the Dashboard (Caseload).

> "Every year, billions in pension top-ups, disability and council-tax support go unclaimed. The rules are scattered across documents, the facts sit in separate systems, and caseworkers check by hand. Unclaimed is for the welfare-rights caseworker. Here are 70 synthetic households, checked against four UK schemes, and the money we found per month."

Point at the **£/month found** tile and the **Needs info** count.

## 2 · Maria (0:20–1:20) — Household view

**Click:** the **Maria Kowalska** row (DEMO CASE) → **Open**.

> "Maria is 67, lives alone, rents, small pension. Four schemes, four different answers."

- **Pension Credit ✅ £187.85/month.** Click **Why?**
  > "Every result is proven. Here's the GOV.UK clause, with its link, and here are the exact records: DWP pension record, as of April 2026. Notice the housing export said £191, but that record is from 2024, so it was flagged out of date and ignored."
- **Council Tax Reduction ✅ £95.33/month.**
  > "Council tax: the account came from the council's REST API, single-person discount applied."
- **Warm Home Discount ❌.** Click **Why?**
  > "A clear no, with the reason: she wasn't getting a qualifying benefit on 23 August, and her electricity bill is in the housing association's name. Once her Pension Credit starts, she'll qualify next year."
- **Attendance Allowance ⚠️ Needs info.**
  > "Here it refuses to guess. The notes say her daughter helps her wash and dress, but not for how long, and the rule needs six months. So it asks one precise question."

## 3 · Correct → rerun → rule patch (1:20–2:00)

**Type in the Attendance Allowance answer box:** months = `7`, note = `Daughter has helped her wash and dress since March 2026` → **Save answer**.

> "The answer is stored in memory with caseworker provenance, and the case re-runs. Attendance Allowance flips to eligible, at least £76.70 a week. Maria's total goes up."

**Go back** (← All households) → search `HH-036` → open **Hilda Ellis**. Pension Credit shows ❌ (income £237.99/week, rule pack 2025-26).

**Click:** Pension Credit → **Correct this** → tab **The decision is wrong** → correct decision **Eligible** → explanation:

`From April 2026 the Pension Credit guarantee is £238 a week for a single person (gov.uk/pension-credit/what-youll-get). Their income is below that.`

→ **Propose rule patch**.

> "A decision correction becomes a rule patch. Nemotron proposes the smallest change, the new 2026-27 rate, and it's only accepted if the full regression suite passes: every labelled household plus the rule examples. Zero regressions, cases fixed: accepted. Hilda now gets Pension Credit."

Point at **Regression gate** (before → after, regressions 0) and **Proposed changes**.

## 4 · Trace view (2:00–2:20)

**Go to** Maria → **View trace →**.

> "This is the architecture. Four sources hit: SQL, CSV, REST, notes extracted by Nemotron with quotes. One fact graph with conflicts and staleness. Then two independent lanes: a deterministic rule engine with three-valued logic, and Nemotron reasoning from the clause text. The arbiter only decides when they agree, every citation exists, and nothing is unknown."

## 5 · Evaluation (2:20–2:40)

**Click:** **Evaluation** in the nav.

> "We measured it. Same Nemotron model, given the raw data and the policy: that's a standard agent. Look at the wrong yes's, the errors that create overpayment debt, and escalation recall: knowing when not to answer."

Read the two headline numbers from the table (they are in EVAL.md).

## 6 · Pitch (2:40–2:50)

> "Unclaimed finds benefits households are entitled to. It makes decisions it can prove, refuses to guess when evidence is missing, and gets better with every correction. Find benefits. Prove decisions."
