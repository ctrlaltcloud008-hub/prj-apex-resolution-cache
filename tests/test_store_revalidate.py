"""Emulator integration for authoritative revalidation via the Store."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from investigation_store import models as store_models
from investigation_store.resolutions import ResolutionRepository

from resolution_cache.gcp import SpannerAuthoritativeResolutions


def _now() -> datetime:
    return datetime(2026, 7, 5, 10, 0, tzinfo=UTC)


def _seed(
    database,
    *,
    resolution_id,
    scope=store_models.ResolutionScope.INDEPENDENT,
    auto_applicable=True,
    successes=3,
) -> None:
    repo = ResolutionRepository.from_database(database)
    asyncio.run(
        repo.create_resolution(
            resolution_id=resolution_id,
            source_investigation_id="inv-1",
            scope=scope,
            alert_fingerprints=["fp-1"],
            root_cause="worker OOM",
            remediation_steps=[{"action": "restart_deployment"}],
            auto_applicable=auto_applicable,
            now=_now(),
        )
    )
    # create_resolution starts at one success; add more to cross the threshold.
    for _ in range(successes - 1):
        asyncio.run(
            repo.apply_outcome(
                resolution_id, store_models.AttemptOutcome.SUCCESS, _now()
            )
        )


def test_eligible_resolution_revalidates_as_auto_applicable(migrated_store_db):
    database = migrated_store_db()
    _seed(database, resolution_id="res-ok", successes=3)
    auth = SpannerAuthoritativeResolutions.from_database(database)

    candidate = asyncio.run(auth.revalidate("res-ok"))
    assert candidate is not None
    assert candidate.auto_applicable is True


def test_below_threshold_revalidates_not_auto_applicable(migrated_store_db):
    database = migrated_store_db()
    _seed(database, resolution_id="res-new", successes=1)  # one success
    auth = SpannerAuthoritativeResolutions.from_database(database)

    candidate = asyncio.run(auth.revalidate("res-new"))
    assert candidate is not None
    assert candidate.auto_applicable is False


def test_correlated_revalidates_not_auto_applicable(migrated_store_db):
    database = migrated_store_db()
    _seed(
        database,
        resolution_id="res-corr",
        scope=store_models.ResolutionScope.CORRELATED,
        successes=3,
    )
    auth = SpannerAuthoritativeResolutions.from_database(database)

    candidate = asyncio.run(auth.revalidate("res-corr"))
    assert candidate is not None
    assert candidate.auto_applicable is False


def test_missing_resolution_returns_none(migrated_store_db):
    database = migrated_store_db()
    auth = SpannerAuthoritativeResolutions.from_database(database)
    assert asyncio.run(auth.revalidate("nope")) is None
