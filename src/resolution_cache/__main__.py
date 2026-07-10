"""Composition root: wire real adapters from settings and serve.

Importing this module has no side effects; ``bootstrap`` performs the wiring so
tests can import ``resolution_cache.app`` without touching GCP.
"""

from __future__ import annotations

from resolution_cache import app as app_module
from resolution_cache.cache import ResolutionCache
from resolution_cache.gcp import (
    RedisLevel1Index,
    SpannerAuthoritativeResolutions,
    StubSemanticHints,
    StubStructuralHints,
)
from resolution_cache.level_one import Level1Lookup
from resolution_cache.service import CacheService
from resolution_cache.settings import Settings


def build_service(settings: Settings) -> CacheService:
    import redis.asyncio as redis
    from investigation_store import DatabaseConfig, build_database

    database = build_database(
        DatabaseConfig(
            project_id=settings.spanner_project_id or "",
            instance_id=settings.spanner_instance_id or "",
            database_id=settings.spanner_database_id or "",
        )
    )
    authoritative = SpannerAuthoritativeResolutions.from_database(database)
    index = RedisLevel1Index(redis.from_url(settings.redis_url))
    level_one = Level1Lookup(index, authoritative)
    structural = StubStructuralHints()
    semantic = StubSemanticHints()
    cache = ResolutionCache(
        level_one=level_one, structural=structural, semantic=semantic
    )
    return CacheService(
        authoritative=authoritative,
        level_one=level_one,
        structural=structural,
        semantic=semantic,
        cache=cache,
    )


def bootstrap() -> None:
    settings = Settings.from_env()
    app_module.configure(settings=settings, service=build_service(settings))


def main() -> None:
    import uvicorn

    bootstrap()
    uvicorn.run(app_module.app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
