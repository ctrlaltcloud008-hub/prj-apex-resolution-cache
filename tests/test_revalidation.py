"""Pure revalidation gate: which authoritative resolutions may auto-apply."""

from __future__ import annotations

from investigation_store import models as store_models

from resolution_cache import revalidation


def _resolution(
    *,
    scope=store_models.ResolutionScope.INDEPENDENT,
    status=store_models.ResolutionStatus.ACTIVE,
    success_count=3,
    failure_count=0,
    auto_applicable=True,
) -> store_models.ResolutionRow:
    return store_models.ResolutionRow(
        resolution_id="res-1",
        source_investigation_id="inv-1",
        scope=scope,
        alert_fingerprints=["fp-1"],
        root_cause="x",
        remediation_steps=[{"action": "restart_deployment"}],
        auto_applicable=auto_applicable,
        success_count=success_count,
        failure_count=failure_count,
        consecutive_failures=0,
        success_rate=(
            success_count / (success_count + failure_count)
            if success_count + failure_count
            else 0.0
        ),
        status=status,
        projection_version=4,
    )


def test_eligible_independent_is_auto_applicable():
    assert revalidation.is_auto_applicable(_resolution()) is True


def test_correlated_is_never_auto_applicable():
    assert (
        revalidation.is_auto_applicable(
            _resolution(scope=store_models.ResolutionScope.CORRELATED)
        )
        is False
    )


def test_below_attempt_threshold_is_not_auto_applicable():
    assert (
        revalidation.is_auto_applicable(_resolution(success_count=1)) is False
    )


def test_below_rate_threshold_is_not_auto_applicable():
    # 8/10 = 0.80 < 0.85
    assert (
        revalidation.is_auto_applicable(
            _resolution(success_count=8, failure_count=2)
        )
        is False
    )


def test_unsafe_action_is_not_auto_applicable():
    assert (
        revalidation.is_auto_applicable(_resolution(auto_applicable=False))
        is False
    )


def test_non_active_status_is_not_auto_applicable():
    assert (
        revalidation.is_auto_applicable(
            _resolution(status=store_models.ResolutionStatus.DEGRADED)
        )
        is False
    )


def test_candidate_carries_authoritative_fields():
    candidate = revalidation.to_candidate(_resolution(), fingerprint="fp-1")
    assert candidate.resolution_id == "res-1"
    assert candidate.auto_applicable is True
    assert candidate.failure_fingerprint == "fp-1"
    assert candidate.scope == "INDEPENDENT"
