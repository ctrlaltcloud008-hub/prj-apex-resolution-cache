"""Resolution Cache domain types.

Mirrors the Orchestrator's ``ResolutionCacheClient`` vocabulary. Authoritative
resolution rows come from the Investigation Store; these are the typed
candidates and requests that cross the cache's boundary.
"""

from __future__ import annotations

import enum

import pydantic


class CacheLevel(enum.StrEnum):
    """Which level produced a result."""

    LEVEL_1 = "LEVEL_1"
    LEVEL_2 = "LEVEL_2"
    LEVEL_3 = "LEVEL_3"


class ResolutionCandidate(pydantic.BaseModel):
    """A resolution the cache offers — exact (L1) or a hint (L2/L3).

    ``auto_applicable`` is true only for an exact Level 1 candidate that passed
    authoritative revalidation and the direct-apply gates. Hints are never
    auto-applicable.
    """

    resolution_id: str
    failure_fingerprint: str | None = None
    scope: str
    status: str
    intrinsically_safe: bool
    success_rate: float
    applied_count: int
    auto_applicable: bool = False
    level: CacheLevel = CacheLevel.LEVEL_1


class CacheLookupRequest(pydantic.BaseModel):
    """Stable inputs used to query the cache for one Investigation."""

    investigation_id: str
    failure_fingerprint: str
    independent: bool
    alert_count: int


class CacheLookupResult(pydantic.BaseModel):
    """The authoritatively-validated exact candidate and attributed hints."""

    request: CacheLookupRequest
    exact_candidate: ResolutionCandidate | None = None
    hints: list[ResolutionCandidate] = pydantic.Field(default_factory=list)
    hints_loaded: bool = False
