"""Production adapters for the Resolution Cache ports.

Authoritative revalidation loads the Spanner resolution via the Investigation
Store and decides auto-applicability with the revalidation gate — the projection
is never trusted as action content.
"""

from __future__ import annotations

from investigation_store.resolutions import ResolutionRepository

from resolution_cache import models, revalidation

_LEVEL1_KEY = "resolution:alert:{}"


class RedisLevel1Index:
    """Reads the exact projected candidate the Feedback Pipeline writes.

    Key ``resolution:alert:{fingerprint}``; value is the projected candidate
    JSON. Returns ``None`` on a miss so the caller degrades to no candidate.
    """

    def __init__(self, redis) -> None:
        self._redis = redis

    async def get(self, failure_fingerprint: str) -> str | None:
        raw = await self._redis.get(_LEVEL1_KEY.format(failure_fingerprint))
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else raw


class SpannerAuthoritativeResolutions:
    """Revalidates resolutions against authoritative Spanner storage."""

    def __init__(self, repository: ResolutionRepository) -> None:
        self._repository = repository

    @classmethod
    def from_database(cls, database) -> SpannerAuthoritativeResolutions:
        return cls(ResolutionRepository.from_database(database))

    async def revalidate(
        self, resolution_id: str
    ) -> models.ResolutionCandidate | None:
        row = await self._repository.get_resolution(resolution_id)
        if row is None:
            return None
        return revalidation.to_candidate(
            row, level=models.CacheLevel.LEVEL_1
        )


class StubStructuralHints:
    """Level 2 (Neo4j) structural hints — empty until the graph store lands."""

    async def lookup(
        self, request: models.CacheLookupRequest
    ) -> list[models.ResolutionCandidate]:
        return []


class StubSemanticHints:
    """Level 3 (Vector Search) semantic hints — empty until Vector lands.

    Carries the similarity threshold and max-candidate config so the real
    adapter is a drop-in behind the same port.
    """

    def __init__(
        self, *, similarity_threshold: float = 0.50, max_candidates: int = 3
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.max_candidates = max_candidates

    async def lookup(
        self, request: models.CacheLookupRequest
    ) -> list[models.ResolutionCandidate]:
        return []
