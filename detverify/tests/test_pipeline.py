"""Integration + unit tests for the DetVerify pipeline.

Validates the Phase 3 exit criterion (spec §9):

    A clean bundle scores ≥ 80, an adversarial bundle scores ≤ 30
    with a clear stage failure.

The fixtures here build a real signed bundle via the Phase 2
``SimEngine`` and a real ``RootIDVerifier`` from Phase 1, so the
pipeline is exercised end-to-end.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

from core.models import SensorChannel
from core.sim_engine import SimConfig, SimEngine
from detverify.pipeline import DetVerifyPipeline
from detverify.score_emitter import (
    VERDICT_FAILURE_THRESHOLD,
    VERDICT_SUCCESS_THRESHOLD,
    compose_score,
)
from detverify.stages import (
    stage1_signature,
    stage2_temporal,
    stage3_crossmodal,
    stage4_replay,
    stage5_anomaly,
    stage6_kinematic,
)
from rootid.did import build_did_document
from rootid.registry import IdentityRegistry
from rootid.tee_simulator import TEESimulator
from rootid.verifier import RootIDVerifier

if TYPE_CHECKING:
    from core.models import PoPWBundle, StageResult


# ---------------------------------------------------------------------------
# Fixtures: real signed bundle via SimEngine
# ---------------------------------------------------------------------------


def _build_clean_bundle() -> tuple[PoPWBundle, RootIDVerifier]:
    """A clean signed bundle plus a verifier whose registry knows the robot."""
    cfg = SimConfig(
        robot_did="did:knx:testnet:phase3-robot-001",
        seed=11,
        num_steps=30,
        capture_every_n_steps=10,
        camera_width=32,
        camera_height=32,
    )
    tee = TEESimulator(robot_did=cfg.robot_did)
    registry = IdentityRegistry()
    registry.register(
        build_did_document(
            tee.robot_did,
            public_bytes=tee.public_bytes,
            auth_bytes=tee.public_bytes,
            capabilities=["camera", "imu", "torque"],
            created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        ),
    )
    # Wide windows so the bundle's base_timestamp_ns=0 default doesn't trip
    # the freshness check at Stage 1. 10**19 ns ≈ 317 years.
    rootid_verifier = RootIDVerifier(
        registry,
        max_clock_skew_ns=10**19,
        freshness_window_ns=10**19,
    )
    bundle = SimEngine(cfg, tee).run()
    return bundle, rootid_verifier


@pytest.fixture(scope="module")
def clean_bundle() -> tuple[PoPWBundle, RootIDVerifier]:
    return _build_clean_bundle()


# ---------------------------------------------------------------------------
# Score emitter — pure unit tests
# ---------------------------------------------------------------------------


class TestScoreEmitter:
    def _stage(
        self,
        name: str,
        *,
        passed: bool = True,
        severity: str = "info",
    ) -> StageResult:
        from core.models import StageResult

        return StageResult(name=name, passed=passed, detail="x", severity=severity)  # type: ignore[arg-type]

    def test_all_passed_yields_success(self) -> None:
        results = [
            self._stage(n)
            for n in ("signature", "temporal", "crossmodal", "replay", "anomaly", "kinematic")
        ]
        score = compose_score(results)
        assert score.final_pct == 100
        assert score.verdict == "success"

    def test_signature_fail_collapses_to_zero(self) -> None:
        # Only signature stage failed; emitter should ignore other axes.
        results = [self._stage("signature", passed=False, severity="fail")]
        score = compose_score(results)
        assert score.final_pct == 0
        assert score.verdict == "failure"
        assert all(
            getattr(score, axis) == 0
            for axis in (
                "accuracy",
                "speed",
                "safety",
                "optimal_track",
                "energy_efficiency",
                "trajectory_stability",
            )
        )

    def test_kinematic_fail_drops_score_below_failure_threshold(self) -> None:
        results = [
            self._stage("signature"),
            self._stage("temporal"),
            self._stage("crossmodal", passed=False, severity="fail"),
            self._stage("replay", passed=False, severity="fail"),
            self._stage("anomaly", passed=False, severity="warning"),
            self._stage("kinematic", passed=False, severity="fail"),
        ]
        score = compose_score(results)
        assert score.final_pct <= VERDICT_FAILURE_THRESHOLD, score
        assert score.verdict == "failure"

    def test_anomaly_warning_only_dings_safety(self) -> None:
        results = [
            self._stage(n) for n in ("signature", "temporal", "crossmodal", "replay", "kinematic")
        ]
        results.append(self._stage("anomaly", passed=False, severity="warning"))
        score = compose_score(results)
        assert score.safety < 100
        assert score.verdict == "success"  # final_pct still well above 80


# ---------------------------------------------------------------------------
# Per-stage tests on real-signed bundles (slow because they run the sim)
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestStagesOnCleanBundle:
    def test_stage1_signature_passes(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        bundle, verifier = clean_bundle
        r = stage1_signature.run(bundle, verifier=verifier)
        assert r.passed is True
        assert r.severity == "info"

    def test_stage2_temporal_passes(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        bundle, _ = clean_bundle
        r = stage2_temporal.run(bundle)
        assert r.passed is True

    def test_stage3_crossmodal_passes(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        bundle, _ = clean_bundle
        r = stage3_crossmodal.run(bundle)
        assert r.passed is True

    def test_stage4_replay_passes(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        bundle, _ = clean_bundle
        r = stage4_replay.run(bundle)
        assert r.passed is True

    def test_stage5_anomaly_passes(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        bundle, _ = clean_bundle
        r = stage5_anomaly.run(bundle)
        assert r.severity in ("info", "warning")
        # On a clean SimEngine bundle the IMU magnitudes sit near (g, 0)
        # so the seeded baseline IsolationForest should NOT flag them.
        assert r.passed is True

    def test_stage6_kinematic_passes(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        bundle, _ = clean_bundle
        r = stage6_kinematic.run(bundle)
        assert r.passed is True


@pytest.mark.slow
class TestStageFailures:
    def test_temporal_catches_decreasing_timestamps(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        bundle, _ = clean_bundle
        # Reverse the order of camera packets WITHOUT re-signing —
        # surfaces non-monotonic timestamps in the channel.
        cam_packets = [p for p in bundle.sensor_packets if p.channel == SensorChannel.CAMERA]
        rest = [p for p in bundle.sensor_packets if p.channel != SensorChannel.CAMERA]
        bad = bundle.model_copy(
            update={"sensor_packets": list(reversed(cam_packets)) + rest},
        )
        r = stage2_temporal.run(bad)
        assert r.passed is False
        assert "timestamp_ns" in r.detail

    def test_replay_catches_duplicate(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        bundle, _ = clean_bundle
        # Inject a duplicate of the first packet.
        first = bundle.sensor_packets[0]
        bad = bundle.model_copy(
            update={"sensor_packets": [first, *bundle.sensor_packets]},
        )
        r = stage4_replay.run(bad)
        assert r.passed is False
        assert "duplicate" in r.detail

    def test_kinematic_catches_torque_overshoot(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        # Build a fresh torque payload that violates the envelope.
        import base64

        from core import sensor_codec
        from core.models import SensorChannel as Ch

        bundle, _ = clean_bundle
        torque_packets = [p for p in bundle.sensor_packets if p.channel == Ch.TORQUE]
        assert torque_packets
        original = torque_packets[0]
        evil_payload = sensor_codec.encode_torque(tuple([10_000.0] * 7))
        evil = original.model_copy(
            update={"data_b64": base64.b64encode(evil_payload).decode("ascii")},
        )
        bad_packets = [evil if p is original else p for p in bundle.sensor_packets]
        bad = bundle.model_copy(update={"sensor_packets": bad_packets})
        r = stage6_kinematic.run(bad)
        assert r.passed is False
        assert "exceeds" in r.detail


# ---------------------------------------------------------------------------
# Pipeline + Phase 3 exit criterion
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestPipelineExitCriterion:
    def test_clean_bundle_scores_at_least_80(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        bundle, verifier = clean_bundle
        pipeline = DetVerifyPipeline(verifier)
        result = pipeline.verify(bundle)
        assert result.score.final_pct >= VERDICT_SUCCESS_THRESHOLD, result.score
        assert result.score.verdict == "success"
        assert result.deterministic_only is True

    def test_signature_attack_scores_at_most_30(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        bundle, verifier = clean_bundle
        # Tamper with a signature byte — Stage 1 must short-circuit.
        sig = bytearray(bytes.fromhex(bundle.sensor_packets[0].signature_hex))
        sig[0] ^= 0x80
        evil_packet = bundle.sensor_packets[0].model_copy(
            update={"signature_hex": bytes(sig).hex()},
        )
        evil_bundle = bundle.model_copy(
            update={"sensor_packets": [evil_packet, *bundle.sensor_packets[1:]]},
        )
        pipeline = DetVerifyPipeline(verifier)
        result = pipeline.verify(evil_bundle)
        assert result.score.final_pct <= VERDICT_FAILURE_THRESHOLD, result.score
        assert result.score.verdict == "failure"
        # Stage 1 short-circuits — only one stage in the result list.
        assert len(result.stage_results) == 1
        assert result.stage_results[0].name == "signature"
        assert result.stage_results[0].severity == "fail"

    def test_torque_attack_scores_at_most_30(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        import base64

        from core import sensor_codec

        bundle, verifier = clean_bundle
        torque_packets = [p for p in bundle.sensor_packets if p.channel == SensorChannel.TORQUE]
        original = torque_packets[0]
        evil_payload = sensor_codec.encode_torque(tuple([99_999.0] * 7))
        evil = original.model_copy(
            update={"data_b64": base64.b64encode(evil_payload).decode("ascii")},
        )
        # Replace the first torque packet with the evil one.
        bad_packets = [evil if p is original else p for p in bundle.sensor_packets]
        bad_bundle = bundle.model_copy(update={"sensor_packets": bad_packets})
        pipeline = DetVerifyPipeline(verifier)
        result = pipeline.verify(bad_bundle)
        # The torque payload tamper invalidates the packet's RootID
        # signature too (signed bytes change), so signature fails first.
        # Either way: score must be ≤ failure threshold.
        assert result.score.final_pct <= VERDICT_FAILURE_THRESHOLD, result.score
        assert result.score.verdict == "failure"


# ---------------------------------------------------------------------------
# llm_compare adapter
# ---------------------------------------------------------------------------


class TestLlmCompare:
    def test_disabled_returns_none(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        from detverify.llm_compare import compare_with_llm

        bundle, _ = clean_bundle
        assert compare_with_llm(bundle, enabled=False) is None

    def test_no_api_key_returns_none(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from detverify.llm_compare import compare_with_llm

        bundle, _ = clean_bundle
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert compare_with_llm(bundle, enabled=True) is None

    def test_with_api_key_raises_not_implemented(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from detverify.llm_compare import compare_with_llm

        bundle, _ = clean_bundle
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
        with pytest.raises(NotImplementedError):
            compare_with_llm(bundle, enabled=True)


# ---------------------------------------------------------------------------
# Determinism within process — same seed → same score
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestPipelineDeterminism:
    def test_same_clean_bundle_gives_same_score(
        self,
        clean_bundle: tuple[PoPWBundle, RootIDVerifier],
    ) -> None:
        bundle, verifier = clean_bundle
        pipeline = DetVerifyPipeline(verifier)
        a = pipeline.verify(bundle)
        b = pipeline.verify(bundle)
        assert a.score == b.score
        assert [s.severity for s in a.stage_results] == [s.severity for s in b.stage_results]
