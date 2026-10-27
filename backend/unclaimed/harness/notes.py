"""Fact extraction from unstructured caseworker notes.

Nemotron (small model) extracts facts with the exact quote as evidence; any
fact whose quote is not found verbatim in the note is discarded. A rule-based
extractor is the offline fallback.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel

from .. import llm
from ..config import settings

log = logging.getLogger("unclaimed.notes")

NOTE_FIELDS = {
    "needs_care_help": "bool: needs help with personal care (washing, dressing, medication) or supervision because of disability/health",
    "care_need_months": "number: how many months they have needed that help. ONLY if a duration is stated; otherwise omit",
    "care_day_and_night": "bool: needs help both day and night (false if only during the day). ONLY if stated",
    "electricity_bill_in_name": "bool: the claimant's (or partner's) own name is on the electricity bill/account",
    "savings": "number: savings/capital amount in GBP if stated",
    "has_partner": "bool: lives with a partner",
}


class ExtractedFact(BaseModel):
    field: Literal["needs_care_help", "care_need_months", "care_day_and_night", "electricity_bill_in_name", "savings", "has_partner"]
    value: Any
    quote: str
    approximate: bool = False


class Extraction(BaseModel):
    facts: list[ExtractedFact]


SYSTEM = (
    "You extract facts from a UK welfare caseworker's notes. Only extract facts that are explicitly stated. "
    "Never guess: if a duration or amount is not stated, omit that field. For each fact give `quote`: an exact, "
    "verbatim substring of the note that states it, and set `approximate` true if the note says 'about', 'around' etc. "
    'Return JSON: {"facts": [{"field": ..., "value": ..., "quote": ..., "approximate": false}]}'
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _validate(text: str):
    def check(ex: Extraction) -> list[str]:
        bad = [f.quote for f in ex.facts if _norm(f.quote) not in _norm(text)]
        return [f"quote not found verbatim in note: {q!r}" for q in bad]
    return check


def extract_llm(text: str) -> tuple[list[ExtractedFact], dict]:
    fields = "\n".join(f"- {k}: {v}" for k, v in NOTE_FIELDS.items())
    user = f"Fields you may extract:\n{fields}\n\nNote:\n\"\"\"\n{text}\n\"\"\""
    try:
        ex, meta = llm.chat_json(settings.extraction_model, SYSTEM, user, Extraction, validate=_validate(text), max_tokens=1500)
    except ValueError as e:
        # still invalid after repairs: keep only the facts whose quotes verify
        log.warning("extraction repair failed: %s", e)
        return [], {"method": "llm_extraction", "error": str(e)[:200]}
    return ex.facts, {"method": "llm_extraction", "model": meta.model, "cache_hit": meta.cache_hit,
                      "tokens": meta.prompt_tokens + meta.completion_tokens, "latency_s": meta.latency_s}


_RULES: list[tuple[str, str, Any]] = [
    (r"[^.]*\bneeds? help (?:getting|with)[^.]*\.", "needs_care_help", True),
    (r"[^.]*has needed help with[^.]*\.", "needs_care_help", True),
    (r"[^.]*help her wash and get dressed[^.]*\.", "needs_care_help", True),
    (r"[^.]*manages personal care independently[^.]*\.", "needs_care_help", False),
    (r"[^.]*both during the day and at night[^.]*\.", "care_day_and_night", True),
    (r"[^.]*help with washing, dressing and medication during the day[^.]*\.", "care_day_and_night", False),
    (r"[^.]*electricity (?:account|bill) is in (?:their own name)[^.]*\.", "electricity_bill_in_name", True),
    (r"[^.]*electricity (?:account|bill) is in (?:her son's name|the housing association's name)[^.]*\.", "electricity_bill_in_name", False),
    (r"[^.]*lives with partner[^.]*\.", "has_partner", True),
    (r"[^.]*partner \w+ moved in[^.]*\.", "has_partner", True),
    (r"[^.]*\blives alone\b[^.]*\.", "has_partner", False),
]


def extract_rules(text: str) -> tuple[list[ExtractedFact], dict]:
    out: list[ExtractedFact] = []
    flat = text.replace("\n", " ")
    for pat, fld, val in _RULES:
        m = re.search(pat, flat)
        if m and not any(f.field == fld for f in out):
            out.append(ExtractedFact(field=fld, value=val, quote=m.group(0).strip()))
    m = re.search(r"[^.]*for about (\d+) months[^.]*\.", flat)
    if m:
        out.append(ExtractedFact(field="care_need_months", value=int(m.group(1)), quote=m.group(0).strip(), approximate=True))
    m = re.search(r"[^.]*(?:about|around) £([\d,]+)[^.]*\.", flat)
    if m:
        out.append(ExtractedFact(field="savings", value=float(m.group(1).replace(",", "")), quote=m.group(0).strip(), approximate=True))
    return out, {"method": "rule_extraction"}


def extract(text: str) -> tuple[list[ExtractedFact], dict]:
    try:
        return extract_llm(text)
    except llm.LLMUnavailable as e:
        facts, meta = extract_rules(text)
        meta["fallback_reason"] = str(e)
        return facts, meta


def coerce(fld: str, v: Any) -> Optional[Any]:
    if fld in ("care_need_months", "savings"):
        try:
            return float(str(v).replace("£", "").replace(",", ""))
        except ValueError:
            return None
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and v.lower() in ("true", "yes"):
        return True
    if isinstance(v, str) and v.lower() in ("false", "no"):
        return False
    return None
