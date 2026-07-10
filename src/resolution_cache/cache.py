"""The cascading Resolution Cache (design 14 lookup order).

For an INDEPENDENT single-alert Investigation, try Level 1 first and stop on an
eligible revalidated hit; otherwise gather Level 2 (structural) and Level 3
(semantic) hints concurrently under a bounded budget. A correlated or
multi-alert Investigation never receives a Level 1 auto-apply candidate in v1. A
slow or failing hint source contributes nothing rather than failing the lookup.
"""

from __future__ import annotations

import asyncio

from resolution_cache import models, ports


def should_attempt_level_one(request: models.CacheLookupRequest) -> bool:
    """Only an independent single-alert Investigation may auto-apply from L1."""
    return request.independent and request.alert_count == 1


class ResolutionCache:
    def __init__(
        self,
        *,
        level_one,
        structural: ports.StructuralHints,
        semantic: ports.SemanticHints,
        hint_budget_seconds: float = 0.5,
    ) -> None:
        self._level_one = level_one
        self._structural = structural
        self._semantic = semantic
        self._budget = hint_budget_seconds

    async def lookup(
        self, request: models.CacheLookupRequest
    ) -> models.CacheLookupResult:
        if should_attempt_level_one(request):
            exact = await self._level_one.lookup(request.failure_fingerprint)
            if exact is not None:
                return models.CacheLookupResult(
                    request=request,
                    exact_candidate=exact,
                    hints_loaded=False,
                )

        hints = await self._gather_hints(request)
        return models.CacheLookupResult(
            request=request, hints=hints, hints_loaded=True
        )

    async def _gather_hints(
        self, request: models.CacheLookupRequest
    ) -> list[models.ResolutionCandidate]:
        async def safe(source) -> list[models.ResolutionCandidate]:
            try:
                return await asyncio.wait_for(
                    source.lookup(request), self._budget
                )
            except Exception:
                return []

        structural, semantic = await asyncio.gather(
            safe(self._structural), safe(self._semantic)
        )
        return [*structural, *semantic]
