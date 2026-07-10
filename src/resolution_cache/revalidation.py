"""Authoritative revalidation gate (pure).

Alert identity finds a candidate; authority proves it. A Level 1 projection is a
fast pre-filter only — auto-applicability is decided here from the authoritative
Spanner resolution, reusing the store's health ladder plus the direct-apply
scope/status gates (design 14).
"""

from __future__ import annotations

from investigation_store import health
from investigation_store import models as store_models

from resolution_cache import models


def is_auto_applicable(resolution: store_models.ResolutionRow) -> bool:
    """Whether the Orchestrator may skip diagnosis and apply this directly."""
    return (
        resolution.scope is store_models.ResolutionScope.INDEPENDENT
        and health.auto_apply_eligible(
            resolution.status,
            resolution.success_count,
            resolution.failure_count,
            resolution.auto_applicable,
        )
    )


def to_candidate(
    resolution: store_models.ResolutionRow,
    *,
    fingerprint: str | None = None,
    level: models.CacheLevel = models.CacheLevel.LEVEL_1,
    auto_applicable: bool | None = None,
) -> models.ResolutionCandidate:
    """Builds a typed candidate from an authoritative resolution row."""
    if auto_applicable is None:
        auto_applicable = (
            level is models.CacheLevel.LEVEL_1
            and is_auto_applicable(resolution)
        )
    return models.ResolutionCandidate(
        resolution_id=resolution.resolution_id,
        failure_fingerprint=fingerprint,
        scope=resolution.scope.value,
        status=resolution.status.value,
        intrinsically_safe=resolution.auto_applicable,
        success_rate=resolution.success_rate,
        applied_count=resolution.success_count + resolution.failure_count,
        auto_applicable=auto_applicable,
        level=level,
    )
