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
        out, meta = llm.chat_json(settings.reasoning_model, BASE_SYSTEM, user, BaseOut, max_tokens=6000)
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
        print(f"{hh['id']} done", flush=True)
        return row

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        rows = list(ex.map(one, hhs))
    summary = {s: metrics(rows, s) for s in systems}
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_households": len(rows),
        "benefits": BENEFITS,
        "models": {"reasoning": settings.reasoning_model, "extraction": settings.extraction_model},
        "ground_truth": "eval/reference.py on observable facts (plain Python from policy text) + hand-labelled escalations",
        "wall_time_s": round(time.time() - t0, 1),
        "summary": summary,
        "errors": {s: [r["id"] for r in rows if s in r and "error" in r[s]] for s in systems},
        "rows": rows,
    }
    (ROOT / "eval" / "results.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
