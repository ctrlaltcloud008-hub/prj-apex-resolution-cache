"""Facade implementing the Orchestrator's ResolutionCacheClient operations."""

from __future__ import annotations

from resolution_cache import models, ports
from resolution_cache.cache import ResolutionCache
from resolution_cache.level_one import Level1Lookup


class CacheService:
    """The five cache operations the Orchestrator's client expects."""

    def __init__(
        self,
        *,
        authoritative: ports.AuthoritativeResolutions,
        level_one: Level1Lookup,
        structural: ports.StructuralHints,
        semantic: ports.SemanticHints,
        cache: ResolutionCache,
    ) -> None:
        self._authoritative = authoritative
        self._level_one = level_one
        self._structural = structural
        self._semantic = semantic
        self._cache = cache

    async def lookup_level_one(
        self, failure_fingerprint: str
    ) -> models.ResolutionCandidate | None:
        return await self._level_one.lookup(failure_fingerprint)

    async def revalidate(
        self, resolution_id: str
    ) -> models.ResolutionCandidate | None:
        return await self._authoritative.revalidate(resolution_id)

    async def lookup_structural_hints(
        self, request: models.CacheLookupRequest
    ) -> list[models.ResolutionCandidate]:
        return await self._structural.lookup(request)

    async def lookup_semantic_hints(
        self, request: models.CacheLookupRequest
    ) -> list[models.ResolutionCandidate]:
        return await self._semantic.lookup(request)

    async def lookup(
        self, request: models.CacheLookupRequest
    ) -> models.CacheLookupResult:
        return await self._cache.lookup(request)
