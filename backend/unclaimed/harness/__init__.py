"""Data Harness: federated fact gathering over heterogeneous sources."""
from __future__ import annotations

from typing import Protocol

from ..config import settings
from ..models import Fact, SourceHit


class DataHarness(Protocol):
    name: str
    status: str

    def gather(self, household: dict) -> tuple[list[Fact], list[SourceHit]]: ...


def get_harness() -> DataHarness:
    from .local import LocalFederatedHarness

    h = LocalFederatedHarness()
    if settings.data_backend == "zetaris":
        # No verified Zetaris API access yet (see NEEDS_FIRAS.md): stay on the local federation, say so.
        h.status = "local federation (Zetaris requested but not configured)"
    return h
