"""The cascading cache: Level 1 short-circuit, budgeted concurrent hints."""

from __future__ import annotations

import asyncio

from resolution_cache import models
from resolution_cache.cache import ResolutionCache, should_attempt_level_one


def _request(*, independent=True, alert_count=1) -> models.CacheLookupRequest:
    return models.CacheLookupRequest(
        investigation_id="inv-1",
        failure_fingerprint="fp-1",
        independent=independent,
        alert_count=alert_count,
    )


def _candidate(
    resolution_id="res-1", level=models.CacheLevel.LEVEL_1, auto=True
) -> models.ResolutionCandidate:
    return models.ResolutionCandidate(
        resolution_id=resolution_id,
        scope="INDEPENDENT",
        status="ACTIVE",
        intrinsically_safe=True,
        success_rate=1.0,
        applied_count=3,
        auto_applicable=auto,
        level=level,
    )


class FakeLevelOne:
    def __init__(self, candidate=None):
        self._candidate = candidate
        self.calls = 0

    async def lookup(self, failure_fingerprint):
        self.calls += 1
        return self._candidate


class FakeHints:
    def __init__(self, candidates=None, *, error=False, delay=0.0):
        self._candidates = candidates or []
        self._error = error
        self._delay = delay
        self.calls = 0

    async def lookup(self, request):
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error:
            raise RuntimeError("hint backend down")
        return self._candidates


def _cache(level_one, structural, semantic, budget=0.5):
    return ResolutionCache(
        level_one=level_one,
        structural=structural,
        semantic=semantic,
        hint_budget_seconds=budget,
    )


def test_planner_attempts_level_one_only_for_independent_single_alert():
    assert should_attempt_level_one(_request()) is True
    assert should_attempt_level_one(_request(independent=False)) is False
    assert should_attempt_level_one(_request(alert_count=3)) is False


def test_exact_hit_short_circuits_before_hints():
    level_one = FakeLevelOne(_candidate())
    structural = FakeHints([_candidate("s")])
    semantic = FakeHints([_candidate("v")])
    cache = _cache(level_one, structural, semantic)

    result = asyncio.run(cache.lookup(_request()))

    assert result.exact_candidate is not None
    assert result.exact_candidate.resolution_id == "res-1"
    assert result.hints == []
    assert result.hints_loaded is False
    assert structural.calls == 0 and semantic.calls == 0


def test_level_one_miss_gathers_hints_from_both_levels():
    structural = FakeHints([_candidate("s", level=models.CacheLevel.LEVEL_2)])
    semantic = FakeHints([_candidate("v", level=models.CacheLevel.LEVEL_3)])
    cache = _cache(FakeLevelOne(None), structural, semantic)

    result = asyncio.run(cache.lookup(_request()))

    assert result.exact_candidate is None
    assert result.hints_loaded is True
    assert {c.resolution_id for c in result.hints} == {"s", "v"}


def test_correlated_never_attempts_level_one():
    level_one = FakeLevelOne(_candidate())
    cache = _cache(level_one, FakeHints(), FakeHints())

    result = asyncio.run(cache.lookup(_request(independent=False)))

    assert level_one.calls == 0
    assert result.exact_candidate is None
    assert result.hints_loaded is True


def test_failing_hint_source_degrades_without_failing_lookup():
    structural = FakeHints(error=True)
    semantic = FakeHints([_candidate("v", level=models.CacheLevel.LEVEL_3)])
    cache = _cache(FakeLevelOne(None), structural, semantic)

    result = asyncio.run(cache.lookup(_request()))

    assert [c.resolution_id for c in result.hints] == ["v"]


def test_hint_source_exceeding_budget_contributes_nothing():
    slow = FakeHints([_candidate("s")], delay=0.2)
    fast = FakeHints([_candidate("v", level=models.CacheLevel.LEVEL_3)])
    cache = _cache(FakeLevelOne(None), slow, fast, budget=0.05)

    result = asyncio.run(cache.lookup(_request()))

    assert [c.resolution_id for c in result.hints] == ["v"]
