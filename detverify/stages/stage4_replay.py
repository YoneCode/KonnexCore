"""DetVerify Stage 4 — Replay / freshness.

The TEE simulator already enforces monotonic ``(job_id, channel)``
nonces at signing time, and the Phase 1 RootIDVerifier enforces
monotonicity within bundle scope. This stage adds a second line of
defense by detecting any duplicate ``(channel, nonce)`` tuple in the
bundle's packet list — the cheapest possible replay-injection check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models import StageResult

if TYPE_CHECKING:
    from core.models import PoPWBundle

STAGE_NAME = "replay"


def run(bundle: PoPWBundle) -> StageResult:
    """Run Stage 4."""
    seen: set[tuple[str, int]] = set()
    duplicates: list[str] = []
    for idx, packet in enumerate(bundle.sensor_packets):
        key = (packet.channel.value, packet.nonce)
        if key in seen:
            duplicates.append(
                f"packet[{idx}] duplicate (channel={packet.channel.value}, nonce={packet.nonce})",
            )
        else:
            seen.add(key)

    if duplicates:
        return StageResult(
            name=STAGE_NAME,
            passed=False,
            detail="; ".join(duplicates),
            severity="fail",
        )
    return StageResult(
        name=STAGE_NAME,
        passed=True,
        detail=f"no duplicate (channel, nonce) across {len(bundle.sensor_packets)} packets",
        severity="info",
    )
