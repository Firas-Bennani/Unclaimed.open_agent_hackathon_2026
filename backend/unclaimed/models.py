"""Core data types: facts with provenance, resolved facts, decisions."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel

SourceName = Literal["dwp", "housing", "council", "notes", "derived", "caseworker"]


class Fact(BaseModel):
    id: str
    field: str
    value: Any
    source: SourceName
    source_label: str
    record_id: str
    as_of: Optional[date] = None
    extraction_method: str  # sql | csv | rest_api | llm_extraction | rule_extraction | derivation | caseworker
    confidence: float = 1.0
    quote: Optional[str] = None
    note: Optional[str] = None
    status: Literal["active", "stale", "superseded"] = "active"


class ResolvedFact(BaseModel):
    field: str
    value: Any = None
    state: Literal["known", "missing", "conflict", "stale"]
    fact_ids: list[str] = []
    explanation: str = ""


class SourceHit(BaseModel):
    source: str
    label: str
    backend: str
    query: str
    records: int
    latency_ms: float
    ok: bool = True
    error: Optional[str] = None
    tokens: int = 0
    llm_latency_s: float = 0.0


class Decision(BaseModel):
    benefit: str
    benefit_name: str
    status: Literal["eligible", "not_eligible", "needs_info"]
    amount_weekly: Optional[float] = None
    amount_monthly: Optional[float] = None
    amount_one_off: Optional[float] = None
    amount_is_minimum: bool = False
    already_receiving: bool = False
    reason: str
    question: Optional[str] = None
    question_field: Optional[str] = None
    escalation_cause: Optional[str] = None
    rule_version: str
    clauses: list[dict] = []
    fact_ids: list[str] = []
    deterministic: dict = {}
    reasoning: dict = {}
    arbiter: dict = {}
