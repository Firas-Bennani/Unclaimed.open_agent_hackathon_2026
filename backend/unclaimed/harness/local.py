"""LocalFederatedHarness: SQL (SQLite/Postgres) + CSV via DuckDB + REST API + notes."""
from __future__ import annotations

import logging
import time
from datetime import date
from functools import cached_property

import duckdb
import httpx
from sqlalchemy import bindparam, create_engine, text

from ..config import settings
from ..models import Fact, SourceHit
from . import notes as notes_mod

log = logging.getLogger("unclaimed.harness")

LABELS = {
    "dwp": "DWP income & pensions (SQL)",
    "housing": "Housing association tenancy export (CSV)",
    "council": "Council tax account service (REST)",
    "notes": "Caseworker notes (text)",
}


def _d(s) -> date | None:
    return date.fromisoformat(str(s)[:10]) if s else None


class LocalFederatedHarness:
    name = "local"

    def __init__(self):
        self.status = "local federation"

    @cached_property
    def _sql(self):
        return create_engine(settings.dwp_url)

    @cached_property
    def _council(self) -> httpx.Client:
        if settings.council_api_url:
            return httpx.Client(base_url=settings.council_api_url, timeout=10)
        from fastapi.testclient import TestClient

        from ..mock_council import app

        return TestClient(app)

    # ---------- sources ----------
    def _dwp(self, hh: dict, facts: list[Fact]) -> SourceHit:
        t0 = time.time()
        ni = hh["ni"]
        q = "persons/pensions/benefits/capital WHERE ni = :ni (+ partner)"
        with self._sql.connect() as c:
            person = c.execute(text("SELECT * FROM persons WHERE ni = :ni"), {"ni": ni}).mappings().first()
            if person is None:
                return SourceHit(source="dwp", label=LABELS["dwp"], backend=settings.dwp_url.split(":")[0], query=q,
                                 records=0, latency_ms=(time.time() - t0) * 1000)
            partner = None
            if person["partner_ni"]:
                partner = c.execute(text("SELECT * FROM persons WHERE ni = :ni"), {"ni": person["partner_ni"]}).mappings().first()
            nis = [ni] + ([partner["ni"]] if partner else [])
            pensions = [dict(r) for r in c.execute(text("SELECT * FROM pensions WHERE ni IN :nis").bindparams(
                bindparam("nis", expanding=True)), {"nis": nis}).mappings()]
            benefits = [dict(r) for r in c.execute(text("SELECT * FROM benefits WHERE ni = :ni"), {"ni": ni}).mappings()]
            capital = [dict(r) for r in c.execute(text("SELECT * FROM capital WHERE ni = :ni ORDER BY as_of DESC"), {"ni": ni}).mappings()]
        pid = f"persons:{ni}"
        add = lambda f, v, rid, as_of=None, **kw: facts.append(Fact(
            id=f"dwp:{rid}:{f}", field=f, value=v, source="dwp", source_label=LABELS["dwp"], record_id=rid,
            as_of=as_of, extraction_method="sql", **kw))
        add("full_name", person["full_name"], pid)
        add("date_of_birth", person["dob"], pid)
        add("country", person["country"], pid)
        add("has_partner", partner is not None, pid)
        since = _d(person["gb_resident_since"])
        add("in_gb_2_of_last_3_years", (settings.assessment_date - since).days >= 730, pid,
            note=f"resident in GB since {since}")
        if partner:
            add("partner_date_of_birth", partner["dob"], f"persons:{partner['ni']}")
        if pensions and len(pensions) == len(nis):
            total = round(sum(p["state_pension_weekly"] + p["private_pension_weekly"] for p in pensions), 2)
            rid = "+".join(p["record_id"] for p in pensions)
            add("weekly_income_total", total, f"pensions:{rid}", _d(min(p["as_of"] for p in pensions)),
                note=" + ".join(f"SP £{p['state_pension_weekly']:.2f} + private £{p['private_pension_weekly']:.2f}" for p in pensions))
        in_pay = {b["benefit"]: b for b in benefits if b["status"] == "IN_PAYMENT"}
        brid = ",".join(b["record_id"] for b in benefits) or "none"

        def on(code: str, day: date) -> bool:
            b = in_pay.get(code)
            return bool(b and _d(b["start_date"]) <= day and (not b["end_date"] or _d(b["end_date"]) >= day))

        add("receives_pension_credit", "PENSION_CREDIT" in in_pay, f"benefits:{brid}")
        add("receives_housing_benefit", "HOUSING_BENEFIT" in in_pay, f"benefits:{brid}")
        add("receives_dla_or_pip", bool({"PIP", "DLA", "ADP"} & set(in_pay)), f"benefits:{brid}")
        whd = date(2026, 8, 23)
        add("receives_qualifying_benefit_on_whd_date", on("PENSION_CREDIT", whd) or on("HOUSING_BENEFIT", whd),
            f"benefits:{brid}", note="PC or HB in payment on 23 Aug 2026")
        if capital:
            add("savings", capital[0]["savings"], f"capital:{capital[0]['record_id']}", _d(capital[0]["as_of"]))
        n = 1 + bool(partner) + len(pensions) + len(benefits) + len(capital)
        return SourceHit(source="dwp", label=LABELS["dwp"], backend=settings.dwp_url.split(":")[0].split("+")[0], query=q,
                         records=n, latency_ms=round((time.time() - t0) * 1000, 1))

    def _housing(self, hh: dict, facts: list[Fact]) -> SourceHit:
        t0 = time.time()
        path = (settings.data_dir / "housing_tenancies.csv").as_posix()
        q = "read_csv(housing_tenancies.csv) WHERE ni_number = ? OR (tenant_dob = ? AND postcode = ?)"
        con = duckdb.connect()
        rows = con.execute(
            f"SELECT * FROM read_csv('{path}', all_varchar=true) WHERE ni_number = ? OR (tenant_dob = ? AND replace(postcode,' ','') = ?)",
            [hh["ni"], hh["dob"], hh["postcode"].replace(" ", "")],
        ).fetchall()
        cols = [d[0] for d in con.description]
        con.close()
        for row in rows:
            r = dict(zip(cols, row))
            rid = f"tenancy:{r['tenancy_ref']}"
            by_ni = r["ni_number"] == hh["ni"]
            conf = 1.0 if by_ni else 0.8
            note = None if by_ni else f"linked by date of birth + postcode; name on record '{r['tenant_name']}' differs from '{hh['name']}'"
            add = lambda f, v, as_of=None: facts.append(Fact(
                id=f"housing:{r['tenancy_ref']}:{f}", field=f, value=v, source="housing", source_label=LABELS["housing"],
                record_id=rid, as_of=as_of, extraction_method="csv", confidence=conf, note=note))
            add("tenure", "rent")
            add("weekly_income_total", float(r["declared_weekly_income"]), _d(r["income_declared_on"]))
            if r["electricity_in_tenant_name"] in ("Y", "N"):
                add("electricity_bill_in_name", r["electricity_in_tenant_name"] == "Y")
            add("has_partner", int(r["household_size"]) > 1)
        return SourceHit(source="housing", label=LABELS["housing"], backend="duckdb/csv", query=q, records=len(rows),
                         latency_ms=round((time.time() - t0) * 1000, 1))

    def _council_src(self, hh: dict, facts: list[Fact]) -> SourceHit:
        t0 = time.time()
        surname = hh["name"].split()[-1]
        q = f"GET /accounts?postcode={hh['postcode']}&surname={surname}"
        try:
            resp = self._council.get("/accounts", params={"postcode": hh["postcode"], "surname": surname})
            resp.raise_for_status()
            accounts = resp.json()
        except Exception as e:  # network/API failures become a visible failed source, never a crash
            return SourceHit(source="council", label=LABELS["council"], backend="rest", query=q, records=0,
                             latency_ms=round((time.time() - t0) * 1000, 1), ok=False, error=str(e)[:200])
        for a in accounts:
            rid = f"account:{a['account_id']}"
            as_of = _d(a["as_of"])
            net = round(a["annual_charge"] * (0.75 if a["single_person_discount"] else 1.0), 2)
            add = lambda f, v, note=None: facts.append(Fact(
                id=f"council:{a['account_id']}:{f}", field=f, value=v, source="council", source_label=LABELS["council"],
                record_id=rid, as_of=as_of, extraction_method="rest_api", note=note))
            add("council_tax_liable", True, note=f"liable party {a['liable_name']}")
            add("council_tax_annual_net", net, note=f"band {a['band']}, £{a['annual_charge']:.2f}" + (" less 25% single person discount" if a["single_person_discount"] else ""))
            add("country", a["country"])
        return SourceHit(source="council", label=LABELS["council"], backend="rest", query=q, records=len(accounts),
                         latency_ms=round((time.time() - t0) * 1000, 1))

    def _notes(self, hh: dict, facts: list[Fact]) -> SourceHit:
        t0 = time.time()
        p = settings.data_dir / "notes" / f"{hh['id']}.txt"
        if not p.exists():
            return SourceHit(source="notes", label=LABELS["notes"], backend="files", query=p.name, records=0, latency_ms=0)
        txt = p.read_text(encoding="utf-8")
        extracted, meta = notes_mod.extract(txt)
        for i, ef in enumerate(extracted):
            v = notes_mod.coerce(ef.field, ef.value)
            if v is None:
                continue
            facts.append(Fact(
                id=f"notes:{hh['id']}:{ef.field}:{i}", field=ef.field, value=v, source="notes", source_label=LABELS["notes"],
                record_id=f"note:{p.name}", as_of=settings.assessment_date.replace(day=14), extraction_method=meta["method"],
                confidence=0.7 if ef.approximate else 0.85, quote=ef.quote, note="approximate" if ef.approximate else None))
        backend = f"files + {meta['method']}" + (" (cache)" if meta.get("cache_hit") else "")
        return SourceHit(source="notes", label=LABELS["notes"], backend=backend, query=p.name, records=len(extracted),
                         latency_ms=round((time.time() - t0) * 1000, 1), tokens=meta.get("tokens", 0),
                         llm_latency_s=meta.get("latency_s", 0.0))

    def gather(self, household: dict) -> tuple[list[Fact], list[SourceHit]]:
        facts: list[Fact] = []
        hits: list[SourceHit] = []
        for fn in (self._dwp, self._housing, self._council_src, self._notes):
            try:
                hits.append(fn(household, facts))
            except Exception as e:
                log.exception("source %s failed", fn.__name__)
                hits.append(SourceHit(source=fn.__name__.strip("_"), label=fn.__name__, backend="?", query="", records=0,
                                      latency_ms=0, ok=False, error=str(e)[:200]))
        return facts, hits
