"""Fact Graph: merges facts from all sources, derives values, and detects
conflicts and staleness. Conflicting or stale-only facts become UNKNOWN —
the system never silently picks a side."""
from __future__ import annotations

from datetime import date
from typing import Any

from .config import settings
from .dsl import Env
from .fields import FIELD_NAMES
from .models import Fact, ResolvedFact

TIME_SENSITIVE = {"weekly_income_total", "savings"}
SOURCE_SHORT = {"dwp": "DWP", "housing": "Housing export", "council": "Council tax", "notes": "Caseworker notes",
                "caseworker": "Caseworker", "derived": "Derived"}


def _age(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def _spa(dob: date) -> int:
    return 66 if dob < date(1960, 4, 6) else 67


def _agree(a: Fact, b: Fact) -> bool:
    x, y = a.value, b.value
    if isinstance(x, bool) or isinstance(y, bool) or isinstance(x, str) or isinstance(y, str):
        return x == y
    approx = min(a.confidence, b.confidence) < 0.8
    tol = max(1.0, (0.1 if approx else 0.005) * max(abs(x), abs(y)))
    return abs(x - y) <= tol


def _fmt(v: Any) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float) and not v.is_integer():
        return f"£{v:,.2f}"
    if isinstance(v, (int, float)):
        return f"{v:,.0f}"
    return str(v)


def _derive(facts: list[Fact]) -> list[Fact]:
    out: list[Fact] = []
    today = settings.assessment_date
    dob = next((f for f in facts if f.field == "date_of_birth"), None)
    if dob:
        d = date.fromisoformat(str(dob.value))
        out.append(Fact(id=f"derived:age_years<{dob.id}", field="age_years", value=_age(d, today), source="derived",
                        source_label="Derived", record_id=dob.record_id, extraction_method="derivation",
                        note=f"age on {today} from date of birth {d}"))
        out.append(Fact(id=f"derived:state_pension_age<{dob.id}", field="state_pension_age", value=_spa(d), source="derived",
                        source_label="Derived", record_id=dob.record_id, extraction_method="derivation",
                        note="66 if born before 6 Apr 1960, else 67 (simplified)"))
    pdob = next((f for f in facts if f.field == "partner_date_of_birth"), None)
    if pdob:
        d = date.fromisoformat(str(pdob.value))
        out.append(Fact(id=f"derived:partner_reached_spa<{pdob.id}", field="partner_reached_spa",
                        value=_age(d, today) >= _spa(d), source="derived", source_label="Derived", record_id=pdob.record_id,
                        extraction_method="derivation", note=f"partner born {d}"))
    return out


def resolve(facts: list[Fact], overrides: list[Fact] | None = None) -> tuple[Env, dict[str, ResolvedFact], list[Fact]]:
    """Returns the evaluation environment, per-field resolution, and all facts (incl. derived/overrides)."""
    today = settings.assessment_date
    all_facts = list(facts) + _derive(facts) + list(overrides or [])
    resolved: dict[str, ResolvedFact] = {}
    by_field: dict[str, list[Fact]] = {}
    for f in all_facts:
        by_field.setdefault(f.field, []).append(f)

    for field in sorted(FIELD_NAMES):
        cands = by_field.get(field, [])
        cw = [f for f in cands if f.source == "caseworker"]
        if cw:
            win = cw[-1]
            for f in cands:
                if f is not win:
                    f.status = "superseded"
            resolved[field] = ResolvedFact(field=field, value=win.value, state="known", fact_ids=[win.id],
                                           explanation=f"set by caseworker: {win.note or _fmt(win.value)}")
            continue
        fresh, stale = [], []
        for f in cands:
            if field in TIME_SENSITIVE and f.as_of and (today - f.as_of).days > settings.stale_after_days:
                f.status = "stale"
                stale.append(f)
            else:
                fresh.append(f)
        if not fresh:
            if stale:
                s = max(stale, key=lambda f: f.as_of)
                resolved[field] = ResolvedFact(field=field, state="stale", fact_ids=[f.id for f in stale],
                                               explanation=f"only record is out of date: {SOURCE_SHORT[s.source]} {_fmt(s.value)} as of {s.as_of}")
            else:
                resolved[field] = ResolvedFact(field=field, state="missing", explanation="no source has this information")
            continue
        if all(_agree(fresh[0], f) for f in fresh[1:]) and all(_agree(a, b) for a in fresh for b in fresh):
            best = max(fresh, key=lambda f: (f.confidence, f.as_of or date.min))
            expl = " = ".join(f"{SOURCE_SHORT[f.source]} {_fmt(f.value)}" for f in fresh)
            if stale:
                expl += f" (older record ignored: {', '.join(SOURCE_SHORT[f.source] + ' ' + _fmt(f.value) + ' as of ' + str(f.as_of) for f in stale)})"
            resolved[field] = ResolvedFact(field=field, value=best.value, state="known", fact_ids=[f.id for f in fresh],
                                           explanation=expl)
        else:
            parts = [f"{SOURCE_SHORT[f.source]} says {_fmt(f.value)}" + (f" ({f.as_of})" if f.as_of else "") for f in fresh]
            resolved[field] = ResolvedFact(field=field, state="conflict", fact_ids=[f.id for f in fresh],
                                           explanation="sources disagree: " + "; ".join(parts))

    # A single person has no partner to have reached SPA.
    if resolved["partner_reached_spa"].state != "known" and resolved["has_partner"].state == "known" and resolved["has_partner"].value is False:
        resolved["partner_reached_spa"] = ResolvedFact(field="partner_reached_spa", value=False, state="known",
                                                       fact_ids=resolved["has_partner"].fact_ids, explanation="no partner")

    values = {k: (r.value if r.state == "known" else None) for k, r in resolved.items()}
    fact_ids = {k: r.fact_ids for k, r in resolved.items()}
    reasons = {k: f"{r.state}: {r.explanation}" for k, r in resolved.items() if r.state != "known"}
    return Env(values, fact_ids, reasons), resolved, all_facts
