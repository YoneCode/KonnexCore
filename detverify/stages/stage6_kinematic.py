"""DetVerify Stage 6 — Kinematic envelope.

For every torque packet in the bundle, asserts:

* the joint count matches the configured kinematic spec,
* every per-joint torque is within the spec's per-joint envelope.

Default spec models a Kuka iiwa 7-DOF arm with conservative torque
limits derived from the manufacturer's published continuous torques.
Phase 8 replaces the inline defaults with subnet-published kinematic
specs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.models import SensorChannel, StageResult
from detverify._common import decode_torque_packets, packets_for_channel

if TYPE_CHECKING:
    from core.models import PoPWBundle

STAGE_NAME = "kinematic"

#: Per-joint torque limit (N·m) for the default Kuka iiwa 7-DOF spec.
#: A loose value covering the manufacturer's continuous + transient
#: bounds; full envelope per joint lands in Phase 8.
_DEFAULT_TORQUE_LIMIT: float = 320.0
_DEFAULT_NUM_JOINTS: int = 7


@dataclass(frozen=True)
class KinematicSpec:
    """Per-robot kinematic envelope used by Stage 6."""

    num_joints: int = _DEFAULT_NUM_JOINTS
    per_joint_torque_limit: float = _DEFAULT_TORQUE_LIMIT
    #: Optional finer-grained limits, indexed by joint index. If
    #: provided, override ``per_joint_torque_limit`` for those joints.
    per_joint_overrides: tuple[float, ...] = field(default_factory=tuple)

    def limit_for_joint(self, joint_index: int) -> float:
        if joint_index < len(self.per_joint_overrides):
            return self.per_joint_overrides[joint_index]
        return self.per_joint_torque_limit


DEFAULT_SPEC = KinematicSpec()


def run(bundle: PoPWBundle, *, spec: KinematicSpec | None = None) -> StageResult:
    """Run Stage 6."""
    kinematic_spec = spec if spec is not None else DEFAULT_SPEC

    torque_packets = packets_for_channel(bundle, SensorChannel.TORQUE)
    if not torque_packets:
        return StageResult(
            name=STAGE_NAME,
            passed=True,
            detail="no torque packets to check",
            severity="info",
        )

    try:
        torque_streams = decode_torque_packets(torque_packets)
    except ValueError as exc:
        return StageResult(
            name=STAGE_NAME,
            passed=False,
            detail=f"torque decode failed: {exc}",
            severity="fail",
        )

    violations: list[str] = []
    for packet_idx, torques in enumerate(torque_streams):
        if len(torques) != kinematic_spec.num_joints:
            violations.append(
                f"torque[{packet_idx}] joint count={len(torques)} "
                f"!= spec.num_joints={kinematic_spec.num_joints}",
            )
            continue
        for joint_idx, tau in enumerate(torques):
            limit = kinematic_spec.limit_for_joint(joint_idx)
            if abs(tau) > limit:
                violations.append(
                    f"torque[{packet_idx}].joint[{joint_idx}]={tau:.3f} "
                    f"exceeds |limit|={limit}",
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
            f"{len(torque_streams)} torque packets within "
            f"{kinematic_spec.num_joints}-joint envelope"
        ),
        severity="info",
    )
