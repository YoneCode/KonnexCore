"""Tests for ``core/attack_lab.py``.

For each attack generator, assert:

1. The produced ``PoPWBundle`` is structurally valid (Pydantic
   round-trip succeeds — naive validators accept it).
2. Running it through ``DetVerifyPipeline`` against the *legitimate*
   registry the generator built (so authentic signatures verify and
   the failure is genuinely attributable to the attack) produces a
   ``DetVerifyResult`` whose ``stage_results`` ends with the
   expected stage name and ``severity == "fail"``.
3. The Phase 4 exit criterion: each attack pushes
   ``final_pct <= VERDICT_FAILURE_THRESHOLD``.
"""

from __future__ import annotations

import pytest

from core.attack_lab import (
    ATTACK_GENERATORS,
    AttackOutcome,
    make_deepfake_video_bundle,
    make_frame_skip_bundle,
    make_gps_spoof_bundle,
    make_replayed_imu_bundle,
    make_torque_mismatch_bundle,
)
from core.models import PoPWBundle
from detverify.pipeline import DetVerifyPipeline
from detverify.score_emitter import VERDICT_FAILURE_THRESHOLD
from rootid.verifier import RootIDVerifier


def _verifier_for(outcome: AttackOutcome) -> RootIDVerifier:
    """Build a verifier from the outcome's legitimate registry."""
    return RootIDVerifier(
        outcome.registry,
        max_clock_skew_ns=10**19,
        freshness_window_ns=10**19,
    )


# ---------------------------------------------------------------------------
# Generic catalogue smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestCatalogue:
    def test_catalogue_has_five_entries(self) -> None:
        assert len(ATTACK_GENERATORS) == 5
        assert set(ATTACK_GENERATORS.keys()) == {
            "deepfake_video",
            "replayed_imu",
            "gps_spoof",
            "frame_skip",
            "torque_mismatch",
        }

    def test_each_outcome_round_trips_through_pydantic(self) -> None:
        for name, generator in ATTACK_GENERATORS.items():
            outcome = generator()  # type: ignore[operator]
            assert isinstance(outcome, AttackOutcome), name
            # Bundle is valid JSON per the Pydantic schema — naive
            # structural validators accept the bundle.
            again = PoPWBundle.model_validate_json(outcome.bundle.model_dump_json())
            assert again == outcome.bundle


# ---------------------------------------------------------------------------
# Per-attack assertions
# ---------------------------------------------------------------------------


def _run_attack(outcome: AttackOutcome) -> tuple[str, int]:
    """Run the bundle through DetVerify and return (last_stage, final_pct)."""
    verifier = _verifier_for(outcome)
    pipeline = DetVerifyPipeline(verifier)
    result = pipeline.verify(outcome.bundle)
    last = result.stage_results[-1]
    assert (
        last.severity == "fail"
    ), f"expected last stage severity 'fail', got {last.severity!s}: {last!r}"
    return last.name, result.score.final_pct


@pytest.mark.slow
class TestPerAttack:
    def test_deepfake_video_caught_at_signature(self) -> None:
        outcome = make_deepfake_video_bundle()
        assert outcome.expected_stage == "signature"
        stage, final_pct = _run_attack(outcome)
        assert stage == "signature"
        assert final_pct <= VERDICT_FAILURE_THRESHOLD

    def test_replayed_imu_caught_at_signature(self) -> None:
        outcome = make_replayed_imu_bundle()
        assert outcome.expected_stage == "signature"
        stage, final_pct = _run_attack(outcome)
        assert stage == "signature"
        assert final_pct <= VERDICT_FAILURE_THRESHOLD

    def test_gps_spoof_caught_at_signature(self) -> None:
        outcome = make_gps_spoof_bundle()
        assert outcome.expected_stage == "signature"
        stage, final_pct = _run_attack(outcome)
        assert stage == "signature"
        assert final_pct <= VERDICT_FAILURE_THRESHOLD

    def test_frame_skip_caught_at_temporal(self) -> None:
        outcome = make_frame_skip_bundle()
        assert outcome.expected_stage == "temporal"
        stage, final_pct = _run_attack(outcome)
        assert stage == "temporal"
        assert final_pct <= VERDICT_FAILURE_THRESHOLD

    def test_torque_mismatch_caught_at_kinematic(self) -> None:
        outcome = make_torque_mismatch_bundle()
        assert outcome.expected_stage == "kinematic"
        stage, final_pct = _run_attack(outcome)
        assert stage == "kinematic"
        assert final_pct <= VERDICT_FAILURE_THRESHOLD


# ---------------------------------------------------------------------------
# Phase 4 exit criterion: every attack catches at its declared stage AND
# scores below failure threshold.
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestPhase4ExitCriterion:
    def test_all_five_attacks_caught_at_distinct_stages(self) -> None:
        observed_stages: dict[str, str] = {}
        for name, generator in ATTACK_GENERATORS.items():
            outcome: AttackOutcome = generator()  # type: ignore[operator]
            stage, final_pct = _run_attack(outcome)
            assert (
                stage == outcome.expected_stage
            ), f"{name}: expected stage {outcome.expected_stage}, got {stage}"
            assert final_pct <= VERDICT_FAILURE_THRESHOLD, (
                f"{name}: final_pct={final_pct} above threshold " f"{VERDICT_FAILURE_THRESHOLD}"
            )
            observed_stages[name] = stage
        # The five attacks span at least three distinct stages
        # (signature catches deepfake/replayed/gps_spoof; temporal
        # catches frame_skip; kinematic catches torque_mismatch).
        assert len(set(observed_stages.values())) >= 3
