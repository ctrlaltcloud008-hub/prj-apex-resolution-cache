"""Shared fixtures. Integration tests need a Spanner emulator with the store's
canonical schema; they skip when SPANNER_EMULATOR_HOST is unset."""

from __future__ import annotations

import asyncio
import contextlib
import os
import pathlib
import uuid

import pytest
from google.cloud import spanner_v1
from investigation_store import migrations

_STORE_MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[2]
    / "prj-apex-incident-store"
    / "schema"
    / "migrations"
)
_PROJECT = "apex-cache-test"
_INSTANCE = "cache-test"


@pytest.fixture
def migrated_store_db():
    if not os.environ.get("SPANNER_EMULATOR_HOST"):
        pytest.skip("SPANNER_EMULATOR_HOST not set; skipping emulator test")

    created = []

    def _build():
        client = spanner_v1.Client(project=_PROJECT)
        instance = client.instance(
            _INSTANCE,
            configuration_name=(
                f"{client.project_name}/instanceConfigs/emulator-config"
            ),
            display_name="cache-test",
        )
        if not instance.exists():
            instance.create().result(120)
        database = instance.database(f"rc-{uuid.uuid4().hex[:12]}")
        database.create().result(120)
        asyncio.run(migrations.apply_pending(database, _STORE_MIGRATIONS))
        created.append(database)
        return database

    yield _build

    for database in created:
        with contextlib.suppress(Exception):
            database.drop()
