"""Level 1 exact lookup: Redis pre-filter + authoritative revalidation."""

from __future__ import annotations

import asyncio
import json

from resolution_cache import models
from resolution_cache.level_one import Level1Lookup


class FakeIndex:
    def __init__(self, value: str | None = None, *, error: bool = False):
        self._value = value
        self._error = error

    async def get(self, failure_fingerprint: str) -> str | None:
        if self._error:
            raise RuntimeError("redis down")
        return self._value


class FakeAuth:
    def __init__(self, candidate: models.ResolutionCandidate | None):
        self._candidate = candidate
        self.revalidated: list[str] = []

    async def revalidate(self, resolution_id: str):
        self.revalidated.append(resolution_id)
        return self._candidate


def _projection(resolution_id="res-1") -> str:
    return json.dumps(
        {
            "resolution_id": resolution_id,
            "scope": "INDEPENDENT",
            "status": "ACTIVE",
            "auto_applicable": True,
            "success_rate": 1.0,
            "applied_count": 3,
            "projection_version": 4,
        },
        separators=(",", ":"),
    )


def _candidate(auto=True) -> models.ResolutionCandidate:
    return models.ResolutionCandidate(
        resolution_id="res-1",
        scope="INDEPENDENT",
        status="ACTIVE",
        intrinsically_safe=True,
        success_rate=1.0,
        applied_count=3,
        auto_applicable=auto,
    )


def test_eligible_projection_revalidates_and_returns_candidate():
    auth = FakeAuth(_candidate(auto=True))
    lookup = Level1Lookup(FakeIndex(_projection()), auth)

    candidate = asyncio.run(lookup.lookup("fp-1"))

    assert candidate is not None
    assert candidate.resolution_id == "res-1"
    assert candidate.failure_fingerprint == "fp-1"
    assert candidate.auto_applicable is True
    assert auth.revalidated == ["res-1"]


def test_stale_projection_failing_revalidation_returns_none():
    # Redis says eligible, but authority disagrees -> not an exact candidate.
    lookup = Level1Lookup(
        FakeIndex(_projection()), FakeAuth(_candidate(auto=False))
    )
    assert asyncio.run(lookup.lookup("fp-1")) is None


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)


def test_redis_index_reads_the_pipeline_projection_format():
    from resolution_cache.gcp import RedisLevel1Index

    redis = FakeRedis()
    # Exactly the key/value the Feedback Pipeline's projection writer writes.
    redis.store["resolution:alert:fp-1"] = _projection("res-1")
    index = RedisLevel1Index(redis)

    lookup = Level1Lookup(index, FakeAuth(_candidate(auto=True)))
    candidate = asyncio.run(lookup.lookup("fp-1"))
    assert candidate is not None
    assert candidate.resolution_id == "res-1"


def test_projection_with_missing_authoritative_record_returns_none():
    lookup = Level1Lookup(FakeIndex(_projection()), FakeAuth(None))
    assert asyncio.run(lookup.lookup("fp-1")) is None


def test_redis_miss_returns_none():
    lookup = Level1Lookup(FakeIndex(None), FakeAuth(_candidate()))
    assert asyncio.run(lookup.lookup("fp-1")) is None


def test_redis_error_degrades_to_none():
    lookup = Level1Lookup(FakeIndex(error=True), FakeAuth(_candidate()))
    assert asyncio.run(lookup.lookup("fp-1")) is None
