"""Internal helpers shared by DetVerify stages.

Each stage in ``detverify/stages/`` receives the raw ``PoPWBundle`` and
either decodes packets itself or pulls from these helpers. The helpers
are intentionally thin — they live here only because two or more
stages share the same access pattern.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from core import sensor_codec

if TYPE_CHECKING:
    from collections.abc import Iterable

    from core.models import PoPWBundle, SensorChannel, SensorPacket


def packets_for_channel(
    bundle: PoPWBundle,
    channel: SensorChannel,
) -> list[SensorPacket]:
    """Return the packets in ``bundle`` for ``channel`` in arrival order."""
    return [p for p in bundle.sensor_packets if p.channel == channel]


def decode_imu_packets(
    packets: Iterable[SensorPacket],
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Decode a sequence of IMU packets into ``[(accel, gyro), ...]``."""
    return [sensor_codec.decode_imu(base64.b64decode(p.data_b64)) for p in packets]


def decode_torque_packets(
    packets: Iterable[SensorPacket],
) -> list[tuple[float, ...]]:
    """Decode a sequence of torque packets into ``[(τ_0, τ_1, ...), ...]``."""
    return [sensor_codec.decode_torque(base64.b64decode(p.data_b64)) for p in packets]
