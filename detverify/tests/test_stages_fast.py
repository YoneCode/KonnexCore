"""Fast unit tests for DetVerify stages — fill the uncovered branches.

These build minimal Pydantic ``PoPWBundle``/``SensorPacket`` instances
inline (no PyBullet, no SimEngine) so they run in milliseconds and
cover failure branches the integration tests don't reach.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone

from core import sensor_codec
from core.models import (
    PolicyTrace,
    PoPWBundle,
    SensorChannel,
    SensorPacket,
    StageResult,
)
from detverify.score_emitter import compose_score
from detverify.stages import (
    stage2_temporal,
    stage3_crossmodal,
    stage5_anomaly,
    stage6_kinematic,
)
from detverify.stages.stage6_kinematic import KinematicSpec

ROBOT_DID = "did:knx:testnet:fast-tests"


def _packet(
    *,
    channel: SensorChannel,
    nonce: int,
    ts: int,
    data: bytes = b"",
) -> SensorPacket:
    return SensorPacket(
        job_id="j-1",
        robot_did=ROBOT_DID,
        channel=channel,
        timestamp_ns=ts,
        nonce=nonce,
        data_b64=base64.b64encode(data).decode("ascii"),
        signature_hex="cc" * 64,
    )


def _bundle(packets: list[SensorPacket]) -> PoPWBundle:
    return PoPWBundle(
        job_id="j-1",
        robot_did=ROBOT_DID,
        task_prompt="x",
        policy_trace=PolicyTrace(actions=[{"i": 0}], seed=0, policy_hash="dd" * 32),
        sensor_packets=packets,
        bundle_merkle_root="ee" * 32,
        submitted_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Stage 2 — gap bounds
# ---------------------------------------------------------------------------


class TestTemporalGaps:
    def test_gap_too_small_fails(self) -> None:
        packets = [
            _packet(channel=SensorChannel.IMU, nonce=0, ts=1_000_000_000),
            _packet(channel=SensorChannel.IMU, nonce=1, ts=1_000_000_500),  # 500 ns gap
        ]
        result = stage2_temporal.run(_bundle(packets))
        assert result.passed is False
        assert "below" in result.detail

    def test_gap_too_large_fails(self) -> None:
        packets = [
            _packet(channel=SensorChannel.IMU, nonce=0, ts=1),
            _packet(
                channel=SensorChannel.IMU,
                nonce=1,
                ts=1 + stage2_temporal.MAX_GAP_NS + 1,
            ),
        ]
        result = stage2_temporal.run(_bundle(packets))
        assert result.passed is False
        assert "above" in result.detail


# ---------------------------------------------------------------------------
# Stage 3 — physical-plausibility branches
# ---------------------------------------------------------------------------


class TestCrossmodalBranches:
    def test_imu_decode_error_fails(self) -> None:
        # Bad magic in the IMU payload.
        bad = _packet(channel=SensorChannel.IMU, nonce=0, ts=1, data=b"NOT_AN_IMU")
        result = stage3_crossmodal.run(_bundle([bad]))
        assert result.passed is False
        assert "imu decode" in result.detail

    def test_torque_decode_error_fails(self) -> None:
        bad = _packet(channel=SensorChannel.TORQUE, nonce=0, ts=1, data=b"NOPE")
        result = stage3_crossmodal.run(_bundle([bad]))
        assert result.passed is False
        assert "torque decode" in result.detail

    def test_camera_decode_error_fails(self) -> None:
        bad = _packet(channel=SensorChannel.CAMERA, nonce=0, ts=1, data=b"NOT_PNG")
        result = stage3_crossmodal.run(_bundle([bad]))
        assert result.passed is False
        assert "camera" in result.detail

    def test_imu_accel_magnitude_overshoot_fails(self) -> None:
        # 100 m/s² along x — well above MAX_ACCEL_M_S2 = 50.
        payload = sensor_codec.encode_imu(accel=(100.0, 0.0, 0.0), gyro=(0.0, 0.0, 0.0))
        packet = _packet(channel=SensorChannel.IMU, nonce=0, ts=1, data=payload)
        result = stage3_crossmodal.run(_bundle([packet]))
        assert result.passed is False
        assert "|accel|" in result.detail

    def test_imu_gyro_magnitude_overshoot_fails(self) -> None:
        payload = sensor_codec.encode_imu(accel=(0.0, 0.0, 9.81), gyro=(100.0, 0.0, 0.0))
        packet = _packet(channel=SensorChannel.IMU, nonce=0, ts=1, data=payload)
        result = stage3_crossmodal.run(_bundle([packet]))
        assert result.passed is False
        assert "|gyro|" in result.detail

    def test_torque_joint_count_mismatch_fails(self) -> None:
        p1 = _packet(
            channel=SensorChannel.TORQUE,
            nonce=0,
            ts=1,
            data=sensor_codec.encode_torque((0.0,) * 7),
        )
        p2 = _packet(
            channel=SensorChannel.TORQUE,
            nonce=1,
            ts=2_000_000,
            data=sensor_codec.encode_torque((0.0,) * 5),
        )
        result = stage3_crossmodal.run(_bundle([p1, p2]))
        assert result.passed is False
        assert "joint count" in result.detail

    def test_camera_shape_mismatch_fails(self) -> None:
        import numpy as np

        small = sensor_codec.encode_camera_frame(np.zeros((4, 4, 3), dtype=np.uint8))
        big = sensor_codec.encode_camera_frame(np.zeros((4, 8, 3), dtype=np.uint8))
        p1 = _packet(channel=SensorChannel.CAMERA, nonce=0, ts=1, data=small)
        p2 = _packet(channel=SensorChannel.CAMERA, nonce=1, ts=2_000_000, data=big)
        result = stage3_crossmodal.run(_bundle([p1, p2]))
        assert result.passed is False
        assert "shape" in result.detail


# ---------------------------------------------------------------------------
# Stage 5 — empty + decode-error branches
# ---------------------------------------------------------------------------


class TestAnomalyBranches:
    def test_empty_imu_passes_with_info(self) -> None:
        # No IMU packets at all — stage returns info, passed=True.
        result = stage5_anomaly.run(_bundle([]))
        assert result.passed is True
        assert result.severity == "info"
        assert "no imu" in result.detail

    def test_decode_error_warns(self) -> None:
        bad = _packet(channel=SensorChannel.IMU, nonce=0, ts=1, data=b"BAD_IMU_PAYLOAD")
        result = stage5_anomaly.run(_bundle([bad]))
        assert result.passed is False
        assert result.severity == "warning"
        assert "decode" in result.detail


# ---------------------------------------------------------------------------
# Stage 6 — empty + decode-error + joint-count + per-joint-override
# ---------------------------------------------------------------------------


class TestKinematicBranches:
    def test_empty_torque_passes(self) -> None:
        result = stage6_kinematic.run(_bundle([]))
        assert result.passed is True
        assert "no torque" in result.detail

    def test_decode_error_fails(self) -> None:
        bad = _packet(channel=SensorChannel.TORQUE, nonce=0, ts=1, data=b"NOPE")
        result = stage6_kinematic.run(_bundle([bad]))
        assert result.passed is False
        assert "decode" in result.detail

    def test_joint_count_mismatch_fails(self) -> None:
        # Default spec expects 7 joints; supply 5.
        packet = _packet(
            channel=SensorChannel.TORQUE,
            nonce=0,
            ts=1,
            data=sensor_codec.encode_torque((0.0,) * 5),
        )
        result = stage6_kinematic.run(_bundle([packet]))
        assert result.passed is False
        assert "joint count" in result.detail

    def test_per_joint_override_used(self) -> None:
        # Custom spec: joint 0 has limit 10 N·m; everything else 320.
        spec = KinematicSpec(
            num_joints=7,
            per_joint_torque_limit=320.0,
            per_joint_overrides=(10.0,),
        )
        # Joint 0 = 50 N·m exceeds the 10 N·m override.
        packet = _packet(
            channel=SensorChannel.TORQUE,
            nonce=0,
            ts=1,
            data=sensor_codec.encode_torque((50.0,) + (0.0,) * 6),
        )
        result = stage6_kinematic.run(_bundle([packet]), spec=spec)
        assert result.passed is False
        assert "joint[0]" in result.detail


# ---------------------------------------------------------------------------
# Score emitter — empty stage list
# ---------------------------------------------------------------------------


class TestScoreEmitterEdge:
    def test_empty_results_yields_perfect_score(self) -> None:
        # No stages reported → no penalties → all 100s.
        score = compose_score([])
        assert score.final_pct == 100
        assert score.verdict == "success"
        assert score.reasoning == "all deterministic stages passed"

    def test_unknown_stage_name_ignored(self) -> None:
        # A stage outside the closed taxonomy doesn't crash compose_score.
        results = [
            StageResult(name="future-stage", passed=True, detail="x", severity="info"),
        ]
        score = compose_score(results)
        assert score.final_pct == 100
