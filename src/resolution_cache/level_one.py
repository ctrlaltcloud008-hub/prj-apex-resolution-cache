"""Level 1 exact lookup.

The Redis index is a fast pre-filter that names a candidate resolution for a
Failure Fingerprint; the returned candidate is the authoritative Spanner record,
and only an auto-applicable revalidated candidate is served. A Redis miss, an
undecodable value, a missing/ineligible authoritative record, or a Redis outage
all degrade to "no exact candidate" so diagnosis runs.
"""

from __future__ import annotations

import json

from resolution_cache import models, ports


class Level1Lookup:
    """Exact Level 1 lookup over the index and authoritative storage."""

    def __init__(
        self,
        index: ports.Level1Index,
        authoritative: ports.AuthoritativeResolutions,
    ) -> None:
        self._index = index
        self._authoritative = authoritative

    async def lookup(
        self, failure_fingerprint: str
    ) -> models.ResolutionCandidate | None:
        try:
            raw = await self._index.get(failure_fingerprint)
        except Exception:
            return None  # A cache outage never blocks the workflow.
        if raw is None:
            return None
        try:
            projected = json.loads(raw)
        except (ValueError, TypeError):
            return None
        resolution_id = projected.get("resolution_id")
        if not resolution_id:
            return None

        candidate = await self._authoritative.revalidate(resolution_id)
        if candidate is None or not candidate.auto_applicable:
            return None
        return candidate.model_copy(
            update={"failure_fingerprint": failure_fingerprint}
        )
