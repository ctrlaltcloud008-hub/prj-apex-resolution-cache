"""The HTTP contract and auth for the Resolution Cache."""

from __future__ import annotations

from fastapi.testclient import TestClient

from resolution_cache import app as app_module
from resolution_cache import models
from resolution_cache.settings import Settings


def _candidate() -> models.ResolutionCandidate:
    return models.ResolutionCandidate(
        resolution_id="res-1",
        failure_fingerprint="fp-1",
        scope="INDEPENDENT",
        status="ACTIVE",
        intrinsically_safe=True,
        success_rate=1.0,
        applied_count=3,
        auto_applicable=True,
    )


class FakeService:
    async def lookup_level_one(self, failure_fingerprint):
        return _candidate()

    async def revalidate(self, resolution_id):
        return None

    async def lookup_structural_hints(self, request):
        return []

    async def lookup_semantic_hints(self, request):
        return []

    async def lookup(self, request):
        return models.CacheLookupResult(
            request=request, exact_candidate=_candidate(), hints_loaded=False
        )


def _client(service=None) -> TestClient:
    app_module.app.dependency_overrides[app_module.get_service] = (
        lambda: service or FakeService()
    )
    return TestClient(app_module.app)


def test_level_one_endpoint_returns_candidate():
    # Route and shape are the Orchestrator's ResolutionCacheHttpClient contract.
    try:
        response = _client().post(
            "/v1/resolutions/exact", json={"failure_fingerprint": "fp-1"}
        )
    finally:
        app_module.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["resolution_id"] == "res-1"


def test_hint_endpoints_wrap_candidates_for_the_orchestrator_client():
    request = {
        "investigation_id": "inv-1",
        "failure_fingerprint": "fp-1",
        "independent": True,
        "alert_count": 1,
    }
    try:
        client = _client()
        structural = client.post("/v1/resolutions/structural", json=request)
        semantic = client.post("/v1/resolutions/semantic", json=request)
    finally:
        app_module.app.dependency_overrides.clear()
    assert structural.status_code == 200
    assert structural.json() == {"candidates": []}
    assert semantic.json() == {"candidates": []}


def test_revalidate_endpoint_uses_contract_route():
    try:
        response = _client().post(
            "/v1/resolutions/revalidate", json={"resolution_id": "res-1"}
        )
    finally:
        app_module.app.dependency_overrides.clear()
    assert response.status_code == 200


def test_lookup_endpoint_returns_cascade_result():
    try:
        response = _client().post(
            "/v1/lookup",
            json={
                "investigation_id": "inv-1",
                "failure_fingerprint": "fp-1",
                "independent": True,
                "alert_count": 1,
            },
        )
    finally:
        app_module.app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["exact_candidate"]["resolution_id"] == "res-1"
    assert body["hints_loaded"] is False


def test_endpoints_reject_unauthenticated_when_auth_required():
    secured = Settings(
        environment="production",
        spanner_project_id="p",
        spanner_instance_id="i",
        spanner_database_id="d",
        redis_url="redis://x",
        push_audience="https://cache.example",
        push_service_account="sa@example.iam.gserviceaccount.com",
    )
    app_module.app.dependency_overrides[app_module.get_settings] = (
        lambda: secured
    )
    app_module.app.dependency_overrides[app_module.get_service] = FakeService
    try:
        response = TestClient(app_module.app).post(
            "/v1/resolutions/exact", json={"failure_fingerprint": "fp-1"}
        )
    finally:
        app_module.app.dependency_overrides.clear()
    assert response.status_code == 401


def _post_with_token(claims=None, error=None):
    from unittest import mock

    secured = Settings(
        environment="production",
        spanner_project_id="p",
        spanner_instance_id="i",
        spanner_database_id="d",
        redis_url="redis://x",
        push_audience="https://cache.example",
        push_service_account="orchestrator@example.iam.gserviceaccount.com",
    )
    app_module.app.dependency_overrides[app_module.get_settings] = (
        lambda: secured
    )
    app_module.app.dependency_overrides[app_module.get_service] = FakeService
    verifier = mock.Mock()
    if error is not None:
        verifier.side_effect = error
    else:
        verifier.return_value = claims
    try:
        with mock.patch(
            "google.oauth2.id_token.verify_oauth2_token", verifier
        ):
            response = TestClient(app_module.app).post(
                "/v1/resolutions/exact",
                json={"failure_fingerprint": "fp-1"},
                headers={"Authorization": "Bearer signed-token"},
            )
    finally:
        app_module.app.dependency_overrides.clear()
    return response


def test_valid_google_signed_token_is_accepted():
    response = _post_with_token(
        claims={
            "email": "orchestrator@example.iam.gserviceaccount.com",
            "email_verified": True,
        }
    )
    assert response.status_code == 200


def test_wrong_service_account_or_bad_token_is_rejected():
    wrong = _post_with_token(
        claims={
            "email": "intruder@example.iam.gserviceaccount.com",
            "email_verified": True,
        }
    )
    bad = _post_with_token(error=ValueError("bad signature"))
    assert wrong.status_code == 401
    assert bad.status_code == 401
