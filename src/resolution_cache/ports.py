"""Boundary protocols for the Resolution Cache."""

from __future__ import annotations

import typing

from resolution_cache import models


class AuthoritativeResolutions(typing.Protocol):
    """Loads and revalidates resolutions from authoritative Spanner storage."""

    async def revalidate(
        self, resolution_id: str
    ) -> models.ResolutionCandidate | None: ...


class Level1Index(typing.Protocol):
    """Reads the exact projected candidate for a Failure Fingerprint."""

    async def get(self, failure_fingerprint: str) -> str | None: ...


class StructuralHints(typing.Protocol):
    """Level 2 structural (Neo4j) hint source."""

    async def lookup(
        self, request: models.CacheLookupRequest
    ) -> list[models.ResolutionCandidate]: ...


class SemanticHints(typing.Protocol):
    """Level 3 semantic (Vector Search) hint source."""

    async def lookup(
        self, request: models.CacheLookupRequest
    ) -> list[models.ResolutionCandidate]: ...
