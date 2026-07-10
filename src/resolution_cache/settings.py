"""Runtime configuration for the Resolution Cache."""

from __future__ import annotations

import dataclasses
import os


@dataclasses.dataclass(frozen=True)
class Settings:
    environment: str
    spanner_project_id: str | None
    spanner_instance_id: str | None
    spanner_database_id: str | None
    redis_url: str | None
    push_audience: str | None
    push_service_account: str | None

    @property
    def use_gcp(self) -> bool:
        return self.environment.lower() not in {"local", "test"}

    @property
    def auth_required(self) -> bool:
        return self.use_gcp

    @classmethod
    def from_env(cls) -> Settings:
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        settings = cls(
            environment=os.getenv("ENV", "production"),
            spanner_project_id=os.getenv("SPANNER_PROJECT_ID", project),
            spanner_instance_id=os.getenv("SPANNER_INSTANCE_ID"),
            spanner_database_id=os.getenv("SPANNER_DATABASE_ID"),
            redis_url=os.getenv("REDIS_URL"),
            push_audience=os.getenv("PUSH_AUDIENCE"),
            push_service_account=os.getenv("PUSH_SERVICE_ACCOUNT"),
        )
        if settings.use_gcp:
            required = {
                "SPANNER_PROJECT_ID": settings.spanner_project_id,
                "SPANNER_INSTANCE_ID": settings.spanner_instance_id,
                "SPANNER_DATABASE_ID": settings.spanner_database_id,
                "REDIS_URL": settings.redis_url,
                "PUSH_AUDIENCE": settings.push_audience,
                "PUSH_SERVICE_ACCOUNT": settings.push_service_account,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise RuntimeError(
                    "missing required production settings: "
                    + ", ".join(missing)
                )
        return settings
