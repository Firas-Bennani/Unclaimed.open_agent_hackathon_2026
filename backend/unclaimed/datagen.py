"""Seeded synthetic data generator (all data fictional).

Writes four heterogeneous sources into data/generated/:
  dwp.sqlite               "DWP-style income & pensions" (SQL)
  housing_tenancies.csv    "housing association tenancy export" (CSV)
  council_accounts.json    backing data for the mock council-tax REST API
  notes/<HH>.txt           caseworker notes / letters (unstructured text)
  households.json          the caseworker's case list (ids, names, NI, postcode)
and the hidden ground truth to eval/ground_truth.json (never read by the pipeline).

Usage: python -m unclaimed.datagen [--seed 7]
"""
from __future__ import annotations

import csv
import json
import random
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .config import settings

TODAY = settings.assessment_date
WHD_DATE = date(2026, 8, 23)
FRESH = date(2026, 4, 12)  # annual uprating letter date
STALE = date(2024, 6, 3)

FIRST = ["Arthur", "Beryl", "Colin", "Doreen", "Edwin", "Fatima", "Gordon", "Hazel", "Imran", "Joan", "Kenneth", "Lorna",
         "Malcolm", "Nora", "Owen", "Pamela", "Rajesh", "Sheila", "Trevor", "Una", "Vernon", "Winifred", "Yusuf", "Agnes",
         "Bernard", "Carol", "Desmond", "Elsie", "Frank", "Gwen", "Harold", "Irene", "Jasbir", "Kathleen", "Leonard", "Mabel",
         "Norman", "Olive", "Percy", "Rita", "Stanley", "Thelma", "Victor", "Wendy", "Albert", "Brenda", "Cyril", "Dilys",
         "Ernest", "Florence", "Geoffrey", "Hilda", "Ivor", "Jean", "Kwame", "Lilian", "Maureen", "Nigel", "Ophelia", "Patrick"]
LAST = ["Abbott", "Begum", "Clarke", "Davies", "Evans", "Fletcher", "Griffiths", "Hughes", "Iqbal", "Jenkins", "Khan",
        "Lewis", "Morgan", "Nowak", "Owusu", "Patel", "Quinn", "Roberts", "Shah", "Thomas", "Underwood", "Vaughan",
        "Walsh", "Young", "Ahmed", "Bennett", "Campbell", "Doyle", "Ellis", "Fraser"]
PARTNER_FIRST = ["Tom", "Mary", "Ray", "Ann", "Bill", "Jean", "Sid", "Pat", "Len", "Ivy"]
TOWNS = {"England": "Brookfield", "Wales": "Llanfair Ddu", "Scotland": "Glenmorrow", "Northern Ireland": "Ballykeel"}


@dataclass
class Person:
    name: str
    dob: date
    ni: str
    state_pension: float = 0.0
    private_pension: float = 0.0


@dataclass
class Household:
    id: str
    scenario: str
    claimant: Person
    partner: Person | None = None
    country: str = "England"
    postcode: str = ""
    address: str = ""
    savings: float = 0.0
    receives_pc: bool = False
    receives_hb: bool = False
    receives_pip: bool = False
    care_needs: bool = False
    care_months: int | None = None
    care_day_night: bool = False
    gb_since: date = date(1975, 1, 1)
    tenure: str = "rent"  # rent (housing association) | own
    ct_charge: float = 1600.0
    elec_in_name: bool = True
    issues: list[str] = field(default_factory=list)
    expect_escalate: list[str] = field(default_factory=list)  # hand label
    note_extra: str = ""


def spa(dob: date) -> int:
    return 66 if dob < date(1960, 4, 6) else 67


def age(dob: date) -> int:
    return TODAY.year - dob.year - ((TODAY.month, TODAY.day) < (dob.month, dob.day))


class Gen:
    def __init__(self, seed: int):
        self.r = random.Random(seed)
        self.n = 0
        self.hh: list[Household] = []
        self.used_names: set[str] = set()

    def name(self) -> str:
        while True:
            n = f"{self.r.choice(FIRST)} {self.r.choice(LAST)}"
            if n not in self.used_names:
                self.used_names.add(n)
                return n

    def dob_for_age(self, a: int) -> date:
        d = TODAY.replace(year=TODAY.year - a) - timedelta(days=self.r.randint(1, 360))
        return d

    def ni(self) -> str:
        self.n += 1
        return f"QQ{100000 + self.n * 37:06d}{'ABCD'[self.n % 4]}"

    def add(self, scenario: str, *, age_: int | None = None, sp: float | None = None, priv: float | None = None,
            partner: bool = False, partner_age: int | None = None, partner_income: float | None = None, **kw) -> Household:
        hid = f"HH-{len(self.hh) + 1:03d}"
        a = age_ if age_ is not None else self.r.randint(67, 88)
        c = Person(self.name(), self.dob_for_age(a), self.ni(),
                   round(sp if sp is not None else self.r.uniform(150, 205), 2),
                   round(priv if priv is not None else self.r.choice([0, 0, self.r.uniform(5, 40)]), 2))
        p = None
        if partner:
            pa = partner_age if partner_age is not None else self.r.randint(67, 86)
            pinc = partner_income if partner_income is not None else self.r.uniform(110, 170)
            p = Person(f"{self.r.choice(PARTNER_FIRST)} {c.name.split()[1]}", self.dob_for_age(pa), self.ni(), round(pinc, 2), 0.0)
        country = kw.pop("country", "England" if self.r.random() < 0.75 else "Wales")
        h = Household(hid, scenario, c, p, country=country, **kw)
        h.postcode = kw.get("postcode") or f"ZZ{self.r.randint(1, 9)} {self.r.randint(1, 9)}{self.r.choice('ABDEFGHJLNPQRSTUWXY')}{self.r.choice('ABDEFGHJLNPQRSTUWXY')}"
        h.address = f"{self.r.randint(1, 120)} {self.r.choice(['Elm', 'Mill', 'Station', 'Church', 'Park', 'Victoria', 'Chapel'])} {self.r.choice(['Road', 'Street', 'Close', 'Lane'])}, {TOWNS[country]}"
        if "ct_charge" not in kw:
            h.ct_charge = round(self.r.uniform(1350, 2300), 2)
        self.hh.append(h)
        return h


def build(seed: int = 7) -> list[Household]:
    g = Gen(seed)
    r = g.r

    # ---- Hero: Maria ----
    m = Household("HH-001", "hero", Person("Maria Kowalska", date(1959, 3, 14), "QQ123456A", 176.45, 18.20),
                  country="England", postcode="ZZ1 4AB", address="Flat 3, 18 Weaver Court, Brookfield",
                  savings=3200, care_needs=True, care_months=None, tenure="rent", ct_charge=1525.33, elec_in_name=False,
                  issues=["care_duration_unknown", "stale_housing_income"], expect_escalate=["attendance_allowance"])
    g.hh.append(m)
    g.used_names.add(m.claimant.name)

    # ---- clear eligible singles ----
    for _ in range(8):
        g.add("clear_eligible", savings=round(r.uniform(0, 8000), 0), elec_in_name=True, tenure=r.choice(["rent", "own"]))
    # ---- already receiving Pension Credit (passports to CTR, WHD) ----
    for _ in range(5):
        g.add("already_on_pc", sp=r.uniform(120, 170), priv=0, receives_pc=True, savings=round(r.uniform(0, 5000), 0), elec_in_name=True)
    # ---- couples ----
    for _ in range(4):
        g.add("couple_eligible", partner=True, sp=r.uniform(150, 190), priv=0, savings=round(r.uniform(0, 9000), 0), tenure="own")
    # ---- clearly ineligible (high income/savings); some have qualifying care needs (AA is not means-tested) ----
    for i in range(6):
        care = i < 3
        g.add("clear_ineligible", sp=r.uniform(221, 241), priv=r.uniform(60, 300), savings=round(r.uniform(18000, 90000), 0),
              tenure="own", care_needs=care, care_months=r.randint(8, 40) if care else None, care_day_night=(i == 0))
    # ---- care needs, modest income ----
    for i in range(4):
        g.add("care_eligible", care_needs=True, care_months=r.randint(7, 36), care_day_night=(i % 2 == 0), receives_hb=(i == 1),
              savings=round(r.uniform(0, 6000), 0))
    # ---- under State Pension age ----
    for _ in range(3):
        g.add("under_spa", age_=r.randint(61, 65), sp=0, priv=r.uniform(90, 160), savings=round(r.uniform(0, 4000), 0))
    # ---- Scotland ----
    for _ in range(3):
        g.add("scotland", country="Scotland", savings=round(r.uniform(0, 5000), 0))

    # ---- boundary cases ----
    g.add("boundary", sp=238.00, priv=0, savings=0, note_extra="income exactly at threshold")
    g.add("boundary", sp=237.99, priv=0, savings=0, note_extra="income 1p under threshold")
    g.add("boundary", sp=200.00, priv=0, savings=10000, note_extra="savings exactly 10000")
    g.add("boundary", sp=228.00, priv=0, savings=15000, note_extra="tariff income 10/wk lands exactly on 238")
    g.add("boundary", sp=245.00, priv=0, savings=16000, ct_charge=1820.0, note_extra="CTR capital exactly 16000")
    g.add("boundary", sp=200.00, priv=0, savings=16000.01, note_extra="CTR capital just over 16000")
    g.add("boundary", care_needs=True, care_months=6, note_extra="care exactly 6 months")
    g.add("boundary", care_needs=True, care_months=5, note_extra="care 5 months")
    b = g.add("boundary", sp=180.00, priv=0, note_extra="reaches SPA today")
    b.claimant.dob = TODAY.replace(year=TODAY.year - 66) if TODAY.replace(year=TODAY.year - 66) < date(1960, 4, 6) else date(1960, 4, 5)

    # ---- missing data ----
    g.add("missing", tenure="own", issues=["missing_dwp_pension"], expect_escalate=["pension_credit", "council_tax_reduction"])
    g.add("missing", sp=r.uniform(170, 200), issues=["missing_capital"], expect_escalate=["pension_credit", "council_tax_reduction"])
    g.add("missing", sp=250, priv=40, issues=["missing_capital"], expect_escalate=["council_tax_reduction"])  # PC no anyway; CTR taper depends on capital
    g.add("missing", care_needs=True, care_months=None, issues=["care_duration_unknown"], expect_escalate=["attendance_allowance"])
    g.add("missing", receives_hb=True, issues=["elec_unknown"], tenure="own", expect_escalate=["warm_home_discount"])
    g.add("missing", issues=["missing_council"], expect_escalate=["council_tax_reduction"])
    g.add("missing", sp=150, priv=0, care_needs=True, care_months=None, issues=["care_duration_unknown", "missing_capital"],
          expect_escalate=["attendance_allowance", "pension_credit", "council_tax_reduction"])

    # ---- conflicting sources ----
    g.add("conflict", sp=200, priv=10, tenure="rent", issues=["conflict_income"], expect_escalate=["pension_credit", "council_tax_reduction"])
    g.add("conflict", sp=185, priv=0, tenure="rent", issues=["conflict_income"], expect_escalate=["pension_credit", "council_tax_reduction"])
    g.add("conflict", sp=190, priv=0, savings=4000, issues=["conflict_savings"], expect_escalate=["pension_credit", "council_tax_reduction"])
    g.add("conflict", sp=205, priv=0, savings=2000, issues=["conflict_savings"], expect_escalate=["pension_credit", "council_tax_reduction"])
    g.add("conflict", sp=175, priv=0, issues=["conflict_partner"], expect_escalate=["pension_credit", "council_tax_reduction"])
    g.add("conflict", receives_pc=True, sp=150, priv=0, tenure="rent", issues=["conflict_elec"], expect_escalate=["warm_home_discount"])
    g.add("conflict", receives_hb=True, sp=170, priv=0, tenure="rent", issues=["conflict_elec"], expect_escalate=["warm_home_discount"])

    # ---- stale records ----
    g.add("stale", sp=190, priv=0, tenure="own", issues=["stale_dwp_pension"], expect_escalate=["pension_credit", "council_tax_reduction"])
    g.add("stale", sp=180, priv=12, tenure="own", issues=["stale_dwp_pension"], expect_escalate=["pension_credit", "council_tax_reduction"])
    g.add("stale", sp=195, priv=0, tenure="rent", issues=["stale_dwp_pension_fresh_housing"], expect_escalate=[])
    g.add("stale", sp=178, priv=0, tenure="rent", issues=["stale_housing_income"], expect_escalate=[])
    g.add("stale", sp=260, priv=30, tenure="own", issues=["stale_dwp_pension"], expect_escalate=["pension_credit", "council_tax_reduction"])

    # ---- identity mismatches in the housing export ----
    g.add("id_mismatch", sp=182, priv=0, tenure="rent", issues=["housing_name_variant"], expect_escalate=[])
    g.add("id_mismatch", sp=176, priv=0, tenure="rent", elec_in_name=True, receives_hb=True, issues=["housing_name_variant"], expect_escalate=[])
    g.add("id_mismatch", sp=188, priv=0, tenure="rent", issues=["housing_unlinkable", "missing_dwp_pension"],
          expect_escalate=["pension_credit", "council_tax_reduction"])

    # mix in a few extra eligible/ineligible to reach ~60, varied
    for _ in range(3):
        g.add("clear_eligible", savings=round(r.uniform(11000, 14000), 0), sp=r.uniform(150, 180), priv=0)
    for _ in range(2):
        g.add("clear_ineligible", sp=r.uniform(240, 260), priv=r.uniform(20, 60), savings=round(r.uniform(2000, 9000), 0), elec_in_name=True)
    return g.hh


# ---------------- truth & observability ----------------
def truth_facts(h: Household) -> dict:
    inc = h.claimant.state_pension + h.claimant.private_pension + (h.partner.state_pension + h.partner.private_pension if h.partner else 0)
    on_whd = h.receives_pc or h.receives_hb
    return {
        "full_name": h.claimant.name,
        "age_years": age(h.claimant.dob),
        "state_pension_age": spa(h.claimant.dob),
        "country": h.country,
        "has_partner": h.partner is not None,
        "partner_reached_spa": bool(h.partner and age(h.partner.dob) >= spa(h.partner.dob)),
        "weekly_income_total": round(inc, 2),
        "savings": h.savings,
        "receives_pension_credit": h.receives_pc,
        "receives_housing_benefit": h.receives_hb,
        "receives_qualifying_benefit_on_whd_date": on_whd,
        "receives_dla_or_pip": h.receives_pip,
        "needs_care_help": h.care_needs,
        "care_need_months": h.care_months if h.care_needs else None,
        "care_day_and_night": h.care_day_night if h.care_needs else False,
        "in_gb_2_of_last_3_years": (TODAY - h.gb_since).days >= 730,
        "council_tax_liable": True,
        "council_tax_annual_net": round(h.ct_charge * (0.75 if h.partner is None else 1.0), 2),
        "electricity_bill_in_name": h.elec_in_name,
        "tenure": h.tenure,
    }


def observable_facts(h: Household) -> dict:
    """What a careful human could establish from the four sources (None = cannot know)."""
    f = truth_facts(h)
    iss = set(h.issues)
    if {"missing_dwp_pension"} & iss and not (h.tenure == "rent" and "housing_unlinkable" not in iss):
        f["weekly_income_total"] = None
    if "missing_capital" in iss:
        f["savings"] = None
    if "conflict_income" in iss or "stale_dwp_pension" in iss:
        f["weekly_income_total"] = None
    if "conflict_savings" in iss:
        f["savings"] = None
    if "conflict_partner" in iss:
        f["has_partner"] = None
        f["partner_reached_spa"] = None
    if "care_duration_unknown" in iss:
        f["care_need_months"] = None
        f["care_day_and_night"] = None
    if "elec_unknown" in iss or "conflict_elec" in iss:
        f["electricity_bill_in_name"] = None
    if "missing_council" in iss:
        f["council_tax_liable"] = None
        f["council_tax_annual_net"] = None
    if not h.care_needs:
        f["care_need_months"] = None
        f["care_day_and_night"] = None
    return f


# ---------------- writers ----------------
def _write_dwp(hh: list[Household], path: Path) -> None:
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE persons (ni TEXT PRIMARY KEY, full_name TEXT, dob TEXT, partner_ni TEXT, postcode TEXT, country TEXT, gb_resident_since TEXT);
        CREATE TABLE pensions (record_id TEXT PRIMARY KEY, ni TEXT, state_pension_weekly REAL, private_pension_weekly REAL, as_of TEXT);
        CREATE TABLE benefits (record_id TEXT PRIMARY KEY, ni TEXT, benefit TEXT, status TEXT, start_date TEXT, end_date TEXT);
        CREATE TABLE capital (record_id TEXT PRIMARY KEY, ni TEXT, savings REAL, as_of TEXT, source_claim TEXT);
        """
    )
    pid = bid = cid = 0
    for h in hh:
        iss = set(h.issues)
        people = [h.claimant] + ([h.partner] if h.partner else [])
        for i, p in enumerate(people):
            partner_ni = None
            if h.partner and "conflict_partner" not in iss:
                partner_ni = h.partner.ni if i == 0 else h.claimant.ni
            con.execute("INSERT INTO persons VALUES (?,?,?,?,?,?,?)",
                        (p.ni, p.name, p.dob.isoformat(), partner_ni, h.postcode, h.country, h.gb_since.isoformat()))
            if "missing_dwp_pension" in iss:
                continue
            stale = "stale_dwp_pension" in iss or "stale_dwp_pension_fresh_housing" in iss
            pid += 1
            con.execute("INSERT INTO pensions VALUES (?,?,?,?,?)",
                        (f"PEN-{pid:05d}", p.ni, p.state_pension, p.private_pension, (STALE if stale else FRESH).isoformat()))
        for flag, code in ((h.receives_pc, "PENSION_CREDIT"), (h.receives_hb, "HOUSING_BENEFIT"), (h.receives_pip, "PIP")):
            if flag:
                bid += 1
                con.execute("INSERT INTO benefits VALUES (?,?,?,?,?,?)",
                            (f"BEN-{bid:05d}", h.claimant.ni, code, "IN_PAYMENT", "2023-05-01", None))
        if h.scenario == "clear_ineligible" and h.id.endswith("5"):
            bid += 1  # an ended award: must not count as "in payment"
            con.execute("INSERT INTO benefits VALUES (?,?,?,?,?,?)",
                        (f"BEN-{bid:05d}", h.claimant.ni, "HOUSING_BENEFIT", "ENDED", "2019-01-01", "2021-03-31"))
        if "missing_capital" not in iss:
            cid += 1
            con.execute("INSERT INTO capital VALUES (?,?,?,?,?)",
                        (f"CAP-{cid:05d}", h.claimant.ni, h.savings, "2025-11-02", "annual review"))
    con.commit()
    con.close()


def _variant(name: str) -> str:
    first, last = name.split(" ", 1)
    return f"{first[0]}. {last}{'e' if not last.endswith('e') else ''}"


def _write_housing(hh: list[Household], path: Path) -> None:
    cols = ["tenancy_ref", "tenant_name", "tenant_dob", "ni_number", "postcode", "household_size",
            "declared_weekly_income", "income_declared_on", "electricity_in_tenant_name", "tenancy_start"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i, h in enumerate(hh):
            if h.tenure != "rent":
                continue
            iss = set(h.issues)
            t = truth_facts(h)
            income = t["weekly_income_total"]
            declared_on = FRESH - timedelta(days=30)
            if "conflict_income" in iss:
                income = round(income + 31.5, 2)
            if "stale_housing_income" in iss:
                income, declared_on = round(income - 3.65, 2), STALE
            name, ni, dob = h.claimant.name, h.claimant.ni, h.claimant.dob.isoformat()
            if "housing_name_variant" in iss:
                name, ni = _variant(name), ""
            if "housing_unlinkable" in iss:
                name, ni, dob = _variant(name), "", (h.claimant.dob - timedelta(days=400)).isoformat()
            elec = "Y" if h.elec_in_name else "N"
            if "conflict_elec" in iss:
                elec = "Y" if not h.elec_in_name else "N"
            if "elec_unknown" in iss:
                elec = ""
            w.writerow([f"TEN-{4100 + i}", name, dob, ni, h.postcode, 2 if h.partner else 1, f"{income:.2f}",
                        declared_on.isoformat(), elec, "2015-09-01"])


def _write_council(hh: list[Household], path: Path) -> None:
    accounts = []
    for i, h in enumerate(hh):
        if "missing_council" in h.issues or h.country == "Northern Ireland":
            continue
        accounts.append({
            "account_id": f"CT-{70000 + i * 13}",
            "liable_name": h.claimant.name.upper(),
            "postcode": h.postcode,
            "address": h.address,
            "country": h.country,
            "band": "ABCDE"[i % 5],
            "annual_charge": h.ct_charge,
            "single_person_discount": h.partner is None,
            "adults_in_property": 2 if h.partner else 1,
            "as_of": "2026-04-01",
        })
    path.write_text(json.dumps(accounts, indent=1), encoding="utf-8")


def _note(h: Household) -> str:
    first = h.claimant.name.split()[0]
    iss = set(h.issues)
    lines = [f"Caseworker notes - {h.claimant.name} ({h.id})", f"Home visit, {(TODAY - timedelta(days=13)).strftime('%d %B %Y')}.", ""]
    if h.id == "HH-001":
        lines += [
            "Maria lives alone in a one-bedroom housing association flat. She is warm and chatty but tires quickly.",
            "She uses a walking stick and finds the stairs to the bins hard. Her daughter comes round to help her wash and get dressed on bad days.",
            "Maria did not say how long she has needed this help and there is no care assessment on file.",
            "Electricity is included in her rent - the electricity bill is in the housing association's name, not hers.",
            "She has a small amount saved, about £3,000, for her funeral.",
        ]
        return "\n".join(lines) + "\n"
    if h.care_needs:
        if "care_duration_unknown" in iss:
            lines.append(f"{first} needs help getting in and out of the bath and with dressing. Unclear how long this has been the case - follow up.")
        else:
            when = "both during the day and at night" if h.care_day_night else "during the day"
            lines.append(f"{first} has needed help with washing, dressing and medication {when} for about {h.care_months} months since a health decline.")
    else:
        lines.append(f"{first} manages personal care independently and did not report any difficulties.")
    if h.partner and "conflict_partner" not in iss:
        lines.append(f"Lives with partner {h.partner.name.split()[0]}.")
    elif not h.partner and "conflict_partner" in iss:
        lines.append(f"{first} mentioned that her partner Ray moved in with her last spring.")
    elif not h.partner:
        lines.append(f"{first} lives alone.")
    if "conflict_savings" in iss:
        lines.append(f"{first} said there is around £{h.savings + 9000:,.0f} in a building society account after selling a car.")
    elif "missing_capital" not in iss and h.savings and r_choice(h, 2) == 0:
        lines.append(f"Savings of about £{h.savings:,.0f} mentioned.")
    if "conflict_elec" in iss or ("elec_unknown" not in iss and r_choice(h, 3) == 0):
        lines.append("The electricity account is in " + ("their own name." if h.elec_in_name else "her son's name, he pays it online."))
    if h.note_extra:
        lines.append("")
    return "\n".join(lines) + "\n"


def r_choice(h: Household, n: int) -> int:
    return sum(map(ord, h.id)) % n


def write_all(seed: int = 7) -> list[Household]:
    out = settings.data_dir
    (out / "notes").mkdir(parents=True, exist_ok=True)
    hh = build(seed)
    _write_dwp(hh, out / "dwp.sqlite")
    _write_housing(hh, out / "housing_tenancies.csv")
    _write_council(hh, out / "council_accounts.json")
    for h in hh:
        (out / "notes" / f"{h.id}.txt").write_text(_note(h), encoding="utf-8")
    index = [{"id": h.id, "name": h.claimant.name, "ni": h.claimant.ni, "dob": h.claimant.dob.isoformat(),
              "postcode": h.postcode, "partner_ni": h.partner.ni if h.partner else None} for h in hh]
    (out / "households.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    gt = []
    for h in hh:
        d = asdict(h)
        gt.append({"id": h.id, "scenario": h.scenario, "issues": h.issues, "expect_escalate": h.expect_escalate,
                   "truth": truth_facts(h), "observable": observable_facts(h), "profile": json.loads(json.dumps(d, default=str))})
    gt_path = settings.root / "eval" / "ground_truth.json"
    gt_path.parent.mkdir(exist_ok=True)
    gt_path.write_text(json.dumps(gt, indent=1, default=str), encoding="utf-8")
    return hh


if __name__ == "__main__":
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 7
    hh = write_all(seed)
    print(f"generated {len(hh)} households into {settings.data_dir}")
