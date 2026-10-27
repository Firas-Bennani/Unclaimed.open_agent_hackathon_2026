"""Evaluation: Unclaimed vs a "standard agent" baseline, against independent ground truth.

  python eval/run.py [--limit N] [--systems unclaimed,baseline,deterministic]

Ground truth = eval/reference.py (plain Python from the policy text) applied to
the facts a careful human could establish (eval/ground_truth.json), with
hand-labelled expected escalations cross-checked (see DECISIONS.md).
Writes eval/results.json and EVAL.md. All LLM calls go through the
record/replay cache, so re-runs are free and reproducible.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))

from pydantic import BaseModel  # noqa: E402

from reference import decide_all  # noqa: E402
from unclaimed import llm  # noqa: E402
from unclaimed.compiler import parse_source  # noqa: E402
from unclaimed.config import settings  # noqa: E402
from unclaimed.engine import BENEFITS, default_pack  # noqa: E402
from unclaimed.pipeline import assess, households  # noqa: E402

MAP = {"eligible": "yes", "not_eligible": "no", "needs_info": "escalate", "cannot_decide": "escalate"}


# ---------------- baseline: "standard agent" ----------------
class BaseDecision(BaseModel):
    benefit: str
    decision: Literal["eligible", "not_eligible", "cannot_decide"]
    weekly_amount: Optional[float] = None
    clause_ids: list[str] = []
    record_ids: list[str] = []
    reason: str = ""


class BaseOut(BaseModel):
    decisions: list[BaseDecision]


BASE_SYSTEM = """You are an AI assistant helping a UK welfare-rights caseworker. Using the policy text and the household's raw
records, decide for each benefit whether the household is eligible. Give the weekly amount if eligible (one-off amount for a
one-off payment). Cite the policy paragraph ids (e.g. "PC-4") and the record ids you relied on. If you cannot tell, say cannot_decide.
Return JSON: {"decisions":[{"benefit":..., "decision":"eligible|not_eligible|cannot_decide", "weekly_amount":..., "clause_ids":[...], "record_ids":[...], "reason":"..."}]}"""


def _policy_text() -> tuple[str, dict[str, set[str]]]:
    parts, ids = [], {}
    for b in BENEFITS:
        meta, body = parse_source(settings.rules_dir / "sources" / f"{b}.md")
        parts.append(f"## {b}: {meta['name']}\n{body.strip()}")
        ids[b] = {line[1:line.index("]")] for line in body.splitlines() if line.startswith("[")}
    return "\n\n".join(parts), ids


def raw_records(hh: dict) -> tuple[str, set[str]]:
    """Every raw record for the household, unprocessed (same lookups as the harness)."""
    d = settings.data_dir
    con = sqlite3.connect(d / "dwp.sqlite")
    con.row_factory = sqlite3.Row
    rows, ids = [], set()
    person = con.execute("SELECT * FROM persons WHERE ni=?", (hh["ni"],)).fetchone()
    nis = [hh["ni"]] + ([person["partner_ni"]] if person and person["partner_ni"] else [])
    for ni in nis:
        p = con.execute("SELECT * FROM persons WHERE ni=?", (ni,)).fetchone()
        if p:
            rows.append(f"DWP persons record persons:{ni}: {dict(p)}")
            ids.add(f"persons:{ni}")
        for t in ("pensions", "benefits", "capital"):
            for r in con.execute(f"SELECT * FROM {t} WHERE ni=?", (ni,)):
                rows.append(f"DWP {t} record {r['record_id']}: {dict(r)}")
                ids.add(r["record_id"])
    con.close()
    with open(d / "housing_tenancies.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["ni_number"] == hh["ni"] or (r["tenant_dob"] == hh["dob"] and r["postcode"].replace(" ", "") == hh["postcode"].replace(" ", "")):
                rows.append(f"Housing association tenancy export row {r['tenancy_ref']}: {r}")
                ids.add(r["tenancy_ref"])
    surname = hh["name"].split()[-1].upper()
    for a in json.loads((d / "council_accounts.json").read_text(encoding="utf-8")):
        if a["postcode"].replace(" ", "") == hh["postcode"].replace(" ", "") and a["liable_name"].endswith(surname):
            rows.append(f"Council tax account {a['account_id']}: {a}")
            ids.add(a["account_id"])
    note = d / "notes" / f"{hh['id']}.txt"
    if note.exists():
        rows.append(f"Caseworker note note:{note.name}:\n{note.read_text(encoding='utf-8')}")
        ids.add(f"note:{note.name}")
    return "\n".join(rows), ids


def run_baseline(hh: dict, policy: str, clause_ids: dict[str, set[str]]) -> dict:
    data, rec_ids = raw_records(hh)
    user = f"Assessment date: {settings.assessment_date}\n\n# Policy\n{policy}\n\n# Household records\n{data}\n\nDecide: {', '.join(BENEFITS)}."
    t0 = time.time()
    try:
        out, meta = llm.chat_json(settings.reasoning_model, BASE_SYSTEM, user, BaseOut, max_tokens=16000)
    except (llm.LLMUnavailable, ValueError) as e:
        return {"error": str(e)[:200]}
    res = {}
    for b in BENEFITS:
        d = next((x for x in out.decisions if x.benefit == b), None)
        if d is None:
            res[b] = {"decision": "escalate", "amount": None, "citation_valid": False, "missing": True}
            continue
        valid = bool(d.clause_ids) and all(c in clause_ids[b] for c in d.clause_ids) and all(
            any(r == i or r.endswith(i) or i.endswith(r) for i in rec_ids) for r in d.record_ids)
        res[b] = {"decision": MAP[d.decision], "amount": d.weekly_amount, "citation_valid": valid}
    return {"benefits": res, "latency_s": meta.latency_s, "tokens": meta.prompt_tokens + meta.completion_tokens,
            "wall_s": round(time.time() - t0, 2)}


def run_unclaimed(hh: dict, use_reasoning: bool) -> dict:
    a = assess(hh["id"], pack=default_pack(), use_reasoning=use_reasoning, save=False)
    res = {}
    for d in a["decisions"]:
        amt = d["amount_weekly"] if d["amount_weekly"] is not None else d["amount_one_off"]
        res[d["benefit"]] = {"decision": MAP[d["status"]], "amount": amt,
                             "citation_valid": d["reasoning"].get("status") != "invalid" and bool(d["clauses"]),
                             "lane_status": d["reasoning"].get("status"), "cause": d["escalation_cause"]}
    notes = next((s for s in a["sources"] if s["source"] == "notes"), {})
    rm = a["reasoning_meta"]
    llm_latency = (rm.get("latency_s") or 0) + (notes.get("llm_latency_s") or 0)
    pipeline_s = (a["timing_ms"]["harness"] + a["timing_ms"]["deterministic"]) / 1000
    return {"benefits": res, "latency_s": round(llm_latency + pipeline_s, 2),
            "tokens": (rm.get("tokens") or 0) + (notes.get("tokens") or 0)}


# ---------------- metrics ----------------
def metrics(rows: list[dict], system: str) -> dict:
    items = [(r["expected"][b], r[system]["benefits"][b], r["truth"][b]) for r in rows if system in r and "benefits" in r[system] for b in BENEFITS]
    n = len(items)
    if not n:
        return {}
    decidable = [(e, p, t) for e, p, t in items if e["decision"] != "escalate"]
    correct = sum(p["decision"] == e["decision"] for e, p, _ in decidable)
    wrong_yes = sum(p["decision"] == "yes" and e["decision"] != "yes" for e, p, _ in items)
    wrong_no = sum(p["decision"] == "no" and e["decision"] != "no" for e, p, _ in items)
    pred_esc = [(e, p) for e, p, _ in items if p["decision"] == "escalate"]
    exp_esc = [(e, p) for e, p, _ in items if e["decision"] == "escalate"]
    tp = sum(e["decision"] == "escalate" for e, _ in pred_esc)
    yes_ok = [(e, p) for e, p, _ in decidable if e["decision"] == "yes" and p["decision"] == "yes" and e["amount"] is not None]
    amt_ok = sum(p["amount"] is not None and abs(p["amount"] - e["amount"]) <= 0.5 for e, p in yes_ok)
    hh_rows = [r[system] for r in rows if system in r and "benefits" in r[system]]
    return {
        "decisions": n,
        "decidable": len(decidable),
        "accuracy_decidable": round(correct / len(decidable), 4),
        "wrong_yes": wrong_yes, "wrong_yes_rate": round(wrong_yes / n, 4),
        "wrong_no": wrong_no, "wrong_no_rate": round(wrong_no / n, 4),
        "escalations": len(pred_esc),
        "escalation_precision": round(tp / len(pred_esc), 4) if pred_esc else None,
        "escalation_recall": round(tp / len(exp_esc), 4) if exp_esc else None,
        "amount_accuracy": round(amt_ok / len(yes_ok), 4) if yes_ok else None,
        "citation_validity": round(sum(p.get("citation_valid", False) for _, p, _ in items) / n, 4),
        "latency_s_mean": round(sum(h["latency_s"] for h in hh_rows) / len(hh_rows), 2),
        "tokens_mean": round(sum(h["tokens"] for h in hh_rows) / len(hh_rows)),
        "households": len(hh_rows),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--systems", default="unclaimed,baseline,deterministic")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    systems = args.systems.split(",")

    gt = {g["id"]: g for g in json.loads((ROOT / "eval" / "ground_truth.json").read_text(encoding="utf-8"))}
    hhs = households()
    if args.limit:
        hhs = hhs[: args.limit]
    policy, clause_ids = _policy_text()

    def one(hh: dict) -> dict:
        g = gt[hh["id"]]
        row = {"id": hh["id"], "name": hh["name"], "scenario": g["scenario"], "issues": g["issues"],
               "expected": decide_all(g["observable"]), "truth": decide_all(g["truth"])}
        if "deterministic" in systems:
            row["deterministic"] = run_unclaimed(hh, use_reasoning=False)
        if "unclaimed" in systems:
            row["unclaimed"] = run_unclaimed(hh, use_reasoning=True)
        if "baseline" in systems:
            row["baseline"] = run_baseline(hh, policy, clause_ids)
        with lock:
            done.append(row)
            write(done, partial=len(done) < len(hhs))
        print(f"{hh['id']} done ({len(done)}/{len(hhs)})", flush=True)
        return row

    lock = threading.Lock()
    done: list[dict] = []
    t0 = time.time()

    def write(rows: list[dict], partial: bool) -> dict:
        rows = sorted(rows, key=lambda r: r["id"])
        out = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "partial": partial,
            "n_households": len(rows),
            "n_planned": len(hhs),
            "benefits": BENEFITS,
            "models": {"reasoning": settings.reasoning_model, "extraction": settings.extraction_model},
            "ground_truth": "eval/reference.py on observable facts (plain Python from policy text) + hand-labelled escalations",
            "wall_time_s": round(time.time() - t0, 1),
            "summary": {s: metrics(rows, s) for s in systems},
            "errors": {s: [r["id"] for r in rows if s in r and "error" in r[s]] for s in systems},
            "rows": rows,
        }
        tmp = ROOT / "eval" / "results.json.tmp"
        tmp.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
        tmp.replace(ROOT / "eval" / "results.json")
        return out

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(one, hhs))
    out = write(done, partial=False)
    summary = out["summary"]
    write_eval_md(out)
    print(json.dumps(summary, indent=1))


LABELS = {"unclaimed": "Unclaimed (both lanes + arbiter)", "baseline": "Standard agent (Nemotron, raw data + policy text)",
          "deterministic": "Ablation: deterministic lane only"}
ROWS = [("accuracy_decidable", "Accuracy on decidable cases", "pct"), ("wrong_yes", "Wrong \"yes\" (count)", "int"),
        ("wrong_yes_rate", "Wrong \"yes\" rate", "pct"), ("wrong_no", "Wrong \"no\" (count)", "int"),
        ("wrong_no_rate", "Wrong \"no\" rate", "pct"), ("escalations", "Escalations", "int"),
        ("escalation_precision", "Escalation precision", "pct"), ("escalation_recall", "Escalation recall", "pct"),
        ("amount_accuracy", "Amount within £0.50 (correct yes)", "pct"), ("citation_validity", "Citation validity", "pct"),
        ("latency_s_mean", "Latency per household (s)", "num"), ("tokens_mean", "Tokens per household", "int")]


def _f(v, kind):
    if v is None:
        return "—"
    return f"{v * 100:.1f}%" if kind == "pct" else (f"{v:,.0f}" if kind == "int" else f"{v:,.1f}")


def write_eval_md(out: dict) -> None:
    systems = [s for s in ("baseline", "unclaimed", "deterministic") if out["summary"].get(s)]
    any_s = out["summary"][systems[0]]
    lines = ["# Evaluation", "",
             f"_Generated {out['generated_at']} by `python eval/run.py` — every number below comes from `eval/results.json`._", "",
             f"- **Households:** {out['n_households']} synthetic households × 4 benefits = {any_s['decisions']} decisions "
             f"({any_s['decidable']} decidable from the available evidence, {any_s['decisions'] - any_s['decidable']} that should be escalated).",
             f"- **Ground truth:** {out['ground_truth']}.",
             f"- **Models:** reasoning `{out['models']['reasoning']}`, extraction `{out['models']['extraction']}`.",
             "- **Baseline:** the same Nemotron model given the policy text and every raw record for the household (SQL rows, CSV row, "
             "council account JSON, caseworker note), asked to decide each benefit. No DSL, no fact graph, no arbiter.",
             "- **Latency** is per household: measured live call time (replayed from the cache on re-runs) plus local pipeline time.", "",
             "| Metric | " + " | ".join(LABELS[s] for s in systems) + " |", "|---|" + "---|" * len(systems)]
    for key, label, kind in ROWS:
        lines.append(f"| {label} | " + " | ".join(_f(out["summary"][s].get(key), kind) for s in systems) + " |")
    lines += ["", "## Definitions", "",
              "- *Decidable*: the reference implementation reaches yes/no from the facts a careful human could establish. Escalating a decidable case counts as not correct.",
              "- *Wrong \"yes\"*: system said eligible when the expected answer was not \"yes\" (no, or escalate). This is the error that creates overpayment debt.",
              "- *Wrong \"no\"*: system said not eligible when the expected answer was not \"no\".",
              "- *Escalation precision / recall*: against the expected escalations (missing, conflicting or stale evidence).",
              "- *Citation validity*: share of decisions whose cited clauses (and, for the baseline, record ids) exist. For Unclaimed, a decision counts as valid only if it cites a clause and the reasoning lane's citations all exist.", ""]
    errs = {k: v for k, v in out["errors"].items() if v}
    if errs:
        lines += ["## Errors", "", *[f"- {k}: {len(v)} household(s) failed: {', '.join(v)}" for k, v in errs.items()], ""]
    mistakes = []
    for r in out["rows"]:
        for s in systems:
            if "benefits" not in r.get(s, {}):
                continue
            for b, p in r[s]["benefits"].items():
                e = r["expected"][b]["decision"]
                if p["decision"] != e:
                    mistakes.append(f"| {r['id']} | {r['scenario']} | {b} | {s} | {e} | {p['decision']} |")
    lines += ["## Every disagreement with ground truth", "", "| Household | Scenario | Benefit | System | Expected | Got |", "|---|---|---|---|---|---|", *mistakes]
    (ROOT / "EVAL.md").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")


if __name__ == "__main__":
    main()
