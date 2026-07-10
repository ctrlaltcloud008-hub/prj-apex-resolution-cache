"""HTTP surface implementing the Orchestrator's ResolutionCacheClient contract.

Internal endpoints require an OIDC bearer token when running against GCP. Each
operation delegates to the CacheService; all degrade to empty/none rather than
failing so a cache problem never blocks an Investigation.
"""

from __future__ import annotations

from typing import Annotated

import fastapi

from resolution_cache import models
from resolution_cache.service import CacheService
from resolution_cache.settings import Settings

app = fastapi.FastAPI(title="prj-apex-resolution-cache")

_service: CacheService | None = None
_settings: Settings | None = None


def configure(*, settings: Settings, service: CacheService) -> None:
    global _settings, _service
    _settings = settings
    _service = service


def get_service() -> CacheService:
    if _service is None:
        raise fastapi.HTTPException(
            status_code=503, detail="service not configured"
        )
    return _service


def get_settings() -> Settings:
    if _settings is None:
        return Settings(
            environment="local",
            spanner_project_id=None,
            spanner_instance_id=None,
            spanner_database_id=None,
            redis_url=None,
            push_audience=None,
            push_service_account=None,
        )
    return _settings


def require_auth(
    request: fastapi.Request,
    settings: Annotated[Settings, fastapi.Depends(get_settings)],
) -> None:
    if not settings.auth_required:
        return
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise fastapi.HTTPException(
            status_code=401,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_oidc_token(
        token, settings.push_audience, settings.push_service_account
    ):
        raise fastapi.HTTPException(status_code=401, detail="invalid token")


def verify_oidc_token(
    token: str,
    audience: str | None,
    expected_service_account: str | None = None,
) -> bool:
    """Verifies a Google-signed service-account OIDC token.

    Signature check against Google's public keys plus audience and
    caller-identity claims; no auth server. Defense-in-depth behind Cloud
    Run IAM.
    """
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token

        claims = google.oauth2.id_token.verify_oauth2_token(
            token,
            google.auth.transport.requests.Request(),
            audience=audience,
        )
    except Exception:
        return False
    if expected_service_account is not None:
        if claims.get("email") != expected_service_account:
            return False
        if not claims.get("email_verified", False):
            return False
    return True


ServiceDep = Annotated[CacheService, fastapi.Depends(get_service)]
_auth = [fastapi.Depends(require_auth)]


# Routes and shapes below are the Orchestrator's ResolutionCacheHttpClient
# contract: exact/revalidate return one candidate (or null); hint routes wrap
# their results as {"candidates": [...]}.


@app.post("/v1/resolutions/exact", dependencies=_auth)
async def level_one(
    body: dict, service: ServiceDep
) -> models.ResolutionCandidate | None:
    return await service.lookup_level_one(body["failure_fingerprint"])


@app.post("/v1/resolutions/revalidate", dependencies=_auth)
async def revalidate(
    body: dict, service: ServiceDep
) -> models.ResolutionCandidate | None:
    return await service.revalidate(body["resolution_id"])


@app.post("/v1/resolutions/structural", dependencies=_auth)
async def structural_hints(
    request: models.CacheLookupRequest, service: ServiceDep
) -> dict[str, list[models.ResolutionCandidate]]:
    return {"candidates": await service.lookup_structural_hints(request)}


@app.post("/v1/resolutions/semantic", dependencies=_auth)
async def semantic_hints(
    request: models.CacheLookupRequest, service: ServiceDep
) -> dict[str, list[models.ResolutionCandidate]]:
    return {"candidates": await service.lookup_semantic_hints(request)}


@app.post("/v1/lookup", dependencies=_auth)
async def lookup(
    request: models.CacheLookupRequest, service: ServiceDep
) -> models.CacheLookupResult:
    return await service.lookup(request)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
