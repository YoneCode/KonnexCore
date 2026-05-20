"""Stateless verifier for ``SensorPacket`` and ``PoPWBundle`` instances.

The verifier is the consumer side of the canonical signing format
defined in ``core.crypto`` (``SENSOR_DOMAIN_V1``,
``canonical_sensor_digest``). It performs every check spec'd in
build-spec §6.2 plus the bundle-level invariants from the Phase 1
plan.

Design choices (per ``systematic-debugging`` skill)
---------------------------------------------------
Every failure path returns a ``VerificationResult`` with a precise,
machine-readable ``reason`` string drawn from the closed taxonomy
below. Generic "verification failed" is never returned. This keeps
upstream debugging tractable: a verifier rejection in production logs
maps 1:1 to a specific class of attack or misconfiguration.

Failure taxonomy (closed; new classes require a verifier version bump)::

    ok                          — packet/bundle accepted
    unknown-robot-did           — registry has no entry for the DID
    bad-signature-length        — signature_hex is not 64 bytes
    signature-does-not-verify   — Ed25519 verify failed
    job-id-mismatch             — packet.job_id != expected_job_id (or bundle.job_id)
    timestamp-out-of-window     — outside [now - freshness, now + skew]
    nonce-not-monotonic         — packets out of order within (job, channel)
    merkle-root-mismatch        — bundle.bundle_merkle_root != recomputed
    bundle-empty                — bundle has zero sensor_packets
    bundle-mixed-robots         — packets disagree on robot_did
    bundle-mixed-jobs           — packets disagree on job_id

The verifier is stateless — it owns no per-bundle history, so callers
that need cross-bundle freshness tracking layer their own state on
top.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core import crypto
from core.config import ED25519_SIGNATURE_BYTES

if TYPE_CHECKING:
    from core.models import PoPWBundle, SensorPacket
    from rootid.registry import IdentityRegistry

# Default freshness window: 60 s back, 5 s ahead. Generous enough for
# realistic robot clock drift; tight enough to catch replays.
_DEFAULT_FRESHNESS_NS: int = 60 * 1_000_000_000
_DEFAULT_SKEW_NS: int = 5 * 1_000_000_000


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Outcome of a verifier call.

    ``reason`` is always populated. On success it is the literal
    string ``"ok"``; on failure it is one of the taxonomy entries in
    the module docstring.
    """

    valid: bool
    reason: str


# Pre-baked successful result. Cheap micro-optimisation; also makes
# ``valid is True`` checks short-circuit cleanly.
_OK = VerificationResult(valid=True, reason="ok")


def _fail(reason: str) -> VerificationResult:
    return VerificationResult(valid=False, reason=reason)


class RootIDVerifier:
    """Verifier for RootID-signed sensor packets and bundles."""

    def __init__(
        self,
        registry: IdentityRegistry,
        *,
        max_clock_skew_ns: int = _DEFAULT_SKEW_NS,
        freshness_window_ns: int = _DEFAULT_FRESHNESS_NS,
    ) -> None:
        if max_clock_skew_ns < 0 or freshness_window_ns < 0:
            msg = "skew and freshness windows must be non-negative"
            raise ValueError(msg)
        self._registry = registry
        self._max_clock_skew_ns = max_clock_skew_ns
        self._freshness_window_ns = freshness_window_ns

    # ------------------------------------------------------------------
    # Packet-level
    # ------------------------------------------------------------------

    def verify_packet(  # noqa: PLR0911 — failure-reason taxonomy requires distinct exits
        self,
        packet: SensorPacket,
        *,
        expected_job_id: str | None = None,
        now_ns: int | None = None,
    ) -> VerificationResult:
        """Verify a single ``SensorPacket``.

        Args:
            packet: The packet to verify.
            expected_job_id: If supplied, ``packet.job_id`` must match
                or the result is ``job-id-mismatch``.
            now_ns: Override for the verifier's clock (test-only).
                Defaults to ``time.time_ns()``.

        Returns:
            A ``VerificationResult`` whose ``reason`` is one of the
            module-docstring taxonomy entries.
        """
        # 1. Public key resolution.
        try:
            public_bytes = self._registry.public_key_for(packet.robot_did)
        except KeyError:
            return _fail("unknown-robot-did")

        # 2. Signature length.
        try:
            signature = bytes.fromhex(packet.signature_hex)
        except ValueError:
            return _fail("bad-signature-length")
        if len(signature) != ED25519_SIGNATURE_BYTES:
            return _fail("bad-signature-length")

        # 3. JobID binding (optional).
        if expected_job_id is not None and packet.job_id != expected_job_id:
            return _fail("job-id-mismatch")

        # 4. Freshness.
        now = now_ns if now_ns is not None else time.time_ns()
        lower = now - self._freshness_window_ns
        upper = now + self._max_clock_skew_ns
        if packet.timestamp_ns < lower or packet.timestamp_ns > upper:
            return _fail("timestamp-out-of-window")

        # 5. Signature.
        digest = crypto.canonical_sensor_digest(
            job_id=packet.job_id,
            channel=packet.channel.value,
            timestamp_ns=packet.timestamp_ns,
            nonce=packet.nonce,
            data=base64.b64decode(packet.data_b64),
        )
        if not crypto.verify(public_bytes, digest, signature):
            return _fail("signature-does-not-verify")

        return _OK

    # ------------------------------------------------------------------
    # Bundle-level
    # ------------------------------------------------------------------

    def verify_bundle(  # noqa: PLR0911 — failure-reason taxonomy requires distinct exits
        self,
        bundle: PoPWBundle,
        *,
        now_ns: int | None = None,
    ) -> VerificationResult:
        """Verify a full ``PoPWBundle``.

        Performs all packet-level checks plus:
          * non-empty packet list,
          * single robot across all packets,
          * single job across all packets,
          * monotonic ``(channel, nonce)`` ordering,
          * bundle Merkle root matches recomputation.
        """
        packets = bundle.sensor_packets
        if not packets:
            return _fail("bundle-empty")

        bundle_robot = bundle.robot_did
        bundle_job = bundle.job_id

        # Cross-packet shape: single robot, single job, monotonic nonces
        # per channel. Run these BEFORE per-packet signature checks so
        # the verifier surfaces structural errors before crypto errors.
        last_nonce_per_channel: dict[str, int] = {}
        for packet in packets:
            if packet.robot_did != bundle_robot:
                return _fail("bundle-mixed-robots")
            if packet.job_id != bundle_job:
                return _fail("bundle-mixed-jobs")
            chan = packet.channel.value
            prev = last_nonce_per_channel.get(chan)
            if prev is not None and packet.nonce <= prev:
                return _fail("nonce-not-monotonic")
            last_nonce_per_channel[chan] = packet.nonce

        # Recompute the Merkle root over canonical pre-hashes and
        # compare. This catches the case where a packet was swapped
        # without rebuilding the bundle's commitment.
        leaves = [
            crypto.canonical_sensor_bytes(
                job_id=p.job_id,
                channel=p.channel.value,
                timestamp_ns=p.timestamp_ns,
                nonce=p.nonce,
                data=base64.b64decode(p.data_b64),
            )
            for p in packets
        ]
        if crypto.merkle_root(leaves).hex() != bundle.bundle_merkle_root:
            return _fail("merkle-root-mismatch")

        # Per-packet checks last.
        for packet in packets:
            res = self.verify_packet(
                packet,
                expected_job_id=bundle_job,
                now_ns=now_ns,
            )
            if not res.valid:
                return res

        return _OK
