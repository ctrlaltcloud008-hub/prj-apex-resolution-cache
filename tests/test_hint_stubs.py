"""The hint stubs satisfy their ports and integrate into the cascade."""

from __future__ import annotations

import asyncio

from resolution_cache import models
from resolution_cache.cache import ResolutionCache
from resolution_cache.gcp import StubSemanticHints, StubStructuralHints


def _request() -> models.CacheLookupRequest:
    return models.CacheLookupRequest(
        investigation_id="inv-1",
        failure_fingerprint="fp-1",
        independent=True,
        alert_count=1,
    )


class MissingLevelOne:
    async def lookup(self, failure_fingerprint):
        return None


def test_stubs_return_empty_and_never_raise():
    assert asyncio.run(StubStructuralHints().lookup(_request())) == []
    semantic = StubSemanticHints(similarity_threshold=0.6, max_candidates=5)
    assert asyncio.run(semantic.lookup(_request())) == []
    assert semantic.similarity_threshold == 0.6
    assert semantic.max_candidates == 5


def test_cascade_with_stubs_yields_no_hits_but_completes():
    cache = ResolutionCache(
        level_one=MissingLevelOne(),
        structural=StubStructuralHints(),
        semantic=StubSemanticHints(),
    )
    result = asyncio.run(cache.lookup(_request()))
    assert result.exact_candidate is None
    assert result.hints == []
    assert result.hints_loaded is True
