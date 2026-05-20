"""DetVerify Stage 2 — Temporal consistency.

For each ``SensorChannel`` present in the bundle, asserts:

* ``timestamp_ns`` is strictly monotonically increasing across that
  channel's packets,
* the per-packet sample period is within a reasonable range (no packet
  is more than ``MAX_GAP_NS`` from the previous in the same channel,
  and no two consecutive packets are closer than ``MIN_GAP_NS``).

Failures here surface as ``severity="fail"`` so the pipeline
short-circuits — temporal corruption invalidates downstream
cross-modal and replay reasoning.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models import SensorChannel, StageResult
from detverify._common import packets_for_channel

if TYPE_CHECKING:
    from core.models import PoPWBundle

STAGE_NAME = "temporal"

#: Minimum acceptable gap between consecutive packets on the same channel.
#: 1 microsecond — anything tighter than this is essentially a duplicate
#: capture, which Stage 4 (replay) handles separately, but we surface
#: the timing anomaly here too.
MIN_GAP_NS: int = 1_000

#: Maximum acceptable gap between consecutive packets on the same
#: channel: 60 seconds. Real PoPW bundles are seconds-long; a gap >
#: this strongly suggests a missing-frame attack or clock glitch.
MAX_GAP_NS: int = 60_000_000_000

#: Need at least 2 packets per channel to evaluate gaps.
_MIN_PACKETS_FOR_GAP_CHECK: int = 2


def run(bundle: PoPWBundle) -> StageResult:
    """Run Stage 2."""
    violations: list[str] = []

    for channel in SensorChannel:
        packets = packets_for_channel(bundle, channel)
        if len(packets) < _MIN_PACKETS_FOR_GAP_CHECK:
            continue
        prev_ts = packets[0].timestamp_ns
        for idx, packet in enumerate(packets[1:], start=1):
            ts = packet.timestamp_ns
            if ts <= prev_ts:
                violations.append(
                    f"{channel.value}[{idx}] timestamp_ns={ts} not after prev={prev_ts}",
                )
                # Continue scanning so the message lists all problems.
            else:
                gap = ts - prev_ts
                if gap < MIN_GAP_NS:
                    violations.append(
                        f"{channel.value}[{idx}] gap={gap}ns below {MIN_GAP_NS}",
                    )
                elif gap > MAX_GAP_NS:
                    violations.append(
                        f"{channel.value}[{idx}] gap={gap}ns above {MAX_GAP_NS}",
                    )
            prev_ts = ts

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
        detail="all per-channel timestamps monotonic and within bounds",
        severity="info",
    )
