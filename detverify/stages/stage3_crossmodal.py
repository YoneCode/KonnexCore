"""DetVerify Stage 3 — Cross-modal physical plausibility.

The Konnex spec calls for IMU↔GPS and LiDAR↔camera consistency. The
Phase 2 sim engine produces camera + IMU + torque streams (no GPS or
LiDAR), so this stage focuses on what's available:

* IMU acceleration magnitudes must be physically plausible for a
  desk-scale roboarm: ``|accel| ≤ MAX_ACCEL_M_S2``.
* IMU angular-velocity magnitudes must satisfy ``|gyro| ≤ MAX_GYRO_RAD_S``.
* All camera frames in the bundle must share an identical (H, W, C)
  shape — sudden shape changes signal a frame-skip or splice attack.
* All torque vectors in the bundle must share an identical joint count
  (no robot suddenly grows or loses an arm).

A future Phase (Launch tier) will replace these with the EKF-driven
sensor fusion stub in :mod:`detverify.fusion`.
"""

from __future__ import annotations

import base64
import math
from typing import TYPE_CHECKING

from core import sensor_codec
from core.models import SensorChannel, StageResult
from detverify._common import (
    decode_imu_packets,
    decode_torque_packets,
    packets_for_channel,
)

if TYPE_CHECKING:
    from core.models import PoPWBundle

STAGE_NAME = "crossmodal"

#: Linear acceleration ceiling for a desk-scale roboarm, in m/s².
#: Loose enough to admit free-fall (9.81) but tight enough to flag
#: spoofed IMU streams that claim implausible spike events.
MAX_ACCEL_M_S2: float = 50.0

#: Angular velocity ceiling, in rad/s. Roughly 9 rev/s — well above
#: anything a Kuka iiwa can do, well below sensor saturation.
MAX_GYRO_RAD_S: float = 60.0


def _vec_norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def run(bundle: PoPWBundle) -> StageResult:  # noqa: PLR0912, C901
    """Run Stage 3 — comprehensive plausibility check across channels."""
    violations: list[str] = []

    # --- IMU plausibility ---
    imu_packets = packets_for_channel(bundle, SensorChannel.IMU)
    try:
        imu_decoded = decode_imu_packets(imu_packets)
    except ValueError as exc:
        return StageResult(
            name=STAGE_NAME,
            passed=False,
            detail=f"imu decode failed: {exc}",
            severity="fail",
        )
    for idx, (accel, gyro) in enumerate(imu_decoded):
        a_mag = _vec_norm(accel)
        g_mag = _vec_norm(gyro)
        if a_mag > MAX_ACCEL_M_S2:
            violations.append(f"imu[{idx}] |accel|={a_mag:.3f} > {MAX_ACCEL_M_S2}")
        if g_mag > MAX_GYRO_RAD_S:
            violations.append(f"imu[{idx}] |gyro|={g_mag:.3f} > {MAX_GYRO_RAD_S}")

    # --- Torque consistency: same joint count across the bundle ---
    torque_packets = packets_for_channel(bundle, SensorChannel.TORQUE)
    try:
        torque_decoded = decode_torque_packets(torque_packets)
    except ValueError as exc:
        return StageResult(
            name=STAGE_NAME,
            passed=False,
            detail=f"torque decode failed: {exc}",
            severity="fail",
        )
    if torque_decoded:
        expected_n = len(torque_decoded[0])
        for idx, torques in enumerate(torque_decoded[1:], start=1):
            if len(torques) != expected_n:
                violations.append(
                    f"torque[{idx}] joint count={len(torques)} differs from expected={expected_n}",
                )

    # --- Camera consistency: same (H, W, C) across the bundle ---
    cam_packets = packets_for_channel(bundle, SensorChannel.CAMERA)
    cam_shape: tuple[int, ...] | None = None
    for idx, packet in enumerate(cam_packets):
        try:
            frame = sensor_codec.decode_camera_frame(base64.b64decode(packet.data_b64))
        except ValueError as exc:
            return StageResult(
                name=STAGE_NAME,
                passed=False,
                detail=f"camera[{idx}] decode failed: {exc}",
                severity="fail",
            )
        shape = frame.shape
        if cam_shape is None:
            cam_shape = shape
        elif shape != cam_shape:
            violations.append(
                f"camera[{idx}] shape={shape} differs from first={cam_shape}",
            )

    if violations:
        return StageResult(
            name=STAGE_NAME,
            passed=False,
            detail="; ".join(violations),
            severity="fail",
        )
    return StageResult(
        name=STAGE_NAME,
        passed=True,
        detail=(
            f"imu={len(imu_decoded)} torque={len(torque_decoded)} camera={len(cam_packets)}; "
            "all magnitudes within physical envelope"
        ),
        severity="info",
    )
