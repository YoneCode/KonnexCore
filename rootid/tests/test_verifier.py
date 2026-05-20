"""Tests for ``rootid/verifier.py``.

The verifier surfaces a precise ``reason`` string for each failure
class (per the ``systematic-debugging`` skill — generic
"verification failed" makes upstream debugging hopeless).

Failure classes pinned by tests below:
    unknown-robot-did, bad-signature-length, signature-does-not-verify,
    job-id-mismatch, timestamp-out-of-window, nonce-not-monotonic,
    merkle-root-mismatch, bundle-empty, bundle-mixed-robots,
    bundle-mixed-jobs (extension — same rationale as mixed robots).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from core.models import PolicyTrace, PoPWBundle, SensorChannel
from rootid.did import build_did_document, make_did
from rootid.registry import IdentityRegistry
from rootid.sensor_signer import SensorSigner
from rootid.tee_simulator import TEESimulator
from rootid.verifier import RootIDVerifier, VerificationResult

# Fixed clock for deterministic freshness tests. 2026-05-20 12:00:00 UTC in ns.
_NOW_NS = 1_779_710_400_000_000_000


# ---------------------------------------------------------------------------
# Test scaffolding
# ---------------------------------------------------------------------------


def _build_honest_bundle(
    job_id: str = "job-1",
    *,
    n_packets: int = 2,
    base_ts: int = _NOW_NS - 1_000_000_000,
) -> tuple[IdentityRegistry, SensorSigner, PoPWBundle]:
    """Build a registry, signer, and an honest bundle in one shot."""
    tee = TEESimulator(robot_did="did:knx:testnet:robot-aaaa")
    signer = SensorSigner(tee)

    registry = IdentityRegistry()
    did_str = make_did("testnet", tee.public_bytes)
    # Re-register the simulator's DID under its own true public key. We
    # use the DID the simulator reports rather than the freshly derived
    # one because the simulator was constructed with an explicit DID
    # (this mirrors production: chain authority is the DID; the
    # simulator just signs).
    doc = build_did_document(
        tee.robot_did,
        public_bytes=tee.public_bytes,
        auth_bytes=tee.public_bytes,  # phase 1: same key for both roles
        capabilities=["camera", "imu"],
        created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )
    registry.register(doc)
    # And register the make_did-derived form too, in case future tests
    # rely on it. (The simulator's DID is the authoritative one.)
    if did_str != tee.robot_did:
        registry.register(
            build_did_document(
                did_str,
                public_bytes=tee.public_bytes,
                auth_bytes=tee.public_bytes,
                capabilities=[],
                created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )
        )

    packets = [
        signer.sign_packet(job_id, SensorChannel.CAMERA, base_ts + 1_000_000 * (i + 1), b"frame")
        for i in range(n_packets)
    ]
    bundle = signer.build_bundle(
        job_id=job_id,
        task_prompt="pick apple",
        policy_trace=PolicyTrace(
            actions=[{"step": 0}],
            seed=42,
            policy_hash="dd" * 32,
        ),
        packets=packets,
        submitted_at=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
    )
    return registry, signer, bundle


def _verifier(registry: IdentityRegistry) -> RootIDVerifier:
    # Wide freshness window so the default test bundle doesn't trip it.
    return RootIDVerifier(
        registry,
        max_clock_skew_ns=5_000_000_000,
        freshness_window_ns=60_000_000_000,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_honest_bundle_verifies(self) -> None:
        registry, _, bundle = _build_honest_bundle()
        v = _verifier(registry)
        result = v.verify_bundle(bundle, now_ns=_NOW_NS)
        assert result == VerificationResult(valid=True, reason="ok"), result

    def test_honest_packet_verifies(self) -> None:
        registry, _, bundle = _build_honest_bundle()
        v = _verifier(registry)
        result = v.verify_packet(bundle.sensor_packets[0], now_ns=_NOW_NS)
        assert result.valid is True
        assert result.reason == "ok"

    def test_honest_packet_with_expected_job_id(self) -> None:
        registry, _, bundle = _build_honest_bundle(job_id="my-job")
        v = _verifier(registry)
        result = v.verify_packet(
            bundle.sensor_packets[0],
            expected_job_id="my-job",
            now_ns=_NOW_NS,
        )
        assert result.valid is True


# ---------------------------------------------------------------------------
# Failure-class taxonomy — one test per class
# ---------------------------------------------------------------------------


class TestFailureClasses:
    def test_unknown_robot_did(self) -> None:
        registry, _, bundle = _build_honest_bundle()
        v = _verifier(registry)
        # Replace robot_did with a never-registered one. Apply to both
        # the bundle and its (single) packet to keep mixed-robot logic
        # from firing first.
        ghost_did = "did:knx:testnet:ghost-1234"
        packet = bundle.sensor_packets[0].model_copy(update={"robot_did": ghost_did})
        # First packet's robot_did is ghost — verifier should fail at
        # public-key resolution, not bundle-mixed-robots.
        result = v.verify_packet(packet, now_ns=_NOW_NS)
        assert result.valid is False
        assert result.reason == "unknown-robot-did", result

        # Bundle-level: same outcome on the first packet.
        # Replace ALL packets so mixed-robot doesn't fire.
        all_ghost = bundle.model_copy(
            update={
                "robot_did": ghost_did,
                "sensor_packets": [
                    p.model_copy(update={"robot_did": ghost_did}) for p in bundle.sensor_packets
                ],
            },
        )
        result = v.verify_bundle(all_ghost, now_ns=_NOW_NS)
        assert result.valid is False
        assert result.reason == "unknown-robot-did"

    def test_bad_signature_length(self) -> None:
        registry, _, bundle = _build_honest_bundle()
        v = _verifier(registry)
        packet = bundle.sensor_packets[0]
        bad = packet.model_copy(update={"signature_hex": "ab" * 32})  # 32 != 64 bytes
        result = v.verify_packet(bad, now_ns=_NOW_NS)
        assert result.valid is False
        assert result.reason == "bad-signature-length", result

    def test_bad_signature_non_hex(self) -> None:
        registry, _, bundle = _build_honest_bundle()
        v = _verifier(registry)
        packet = bundle.sensor_packets[0]
        # signature_hex is a Pydantic ``str`` field with no hex constraint;
        # the verifier must catch the ValueError from bytes.fromhex.
        bad = packet.model_copy(update={"signature_hex": "zz" * 64})
        result = v.verify_packet(bad, now_ns=_NOW_NS)
        assert result.valid is False
        assert result.reason == "bad-signature-length", result

    def test_signature_does_not_verify(self) -> None:
        registry, _, bundle = _build_honest_bundle()
        v = _verifier(registry)
        packet = bundle.sensor_packets[0]
        # Flip a bit in the signature
        sig_bytes = bytearray(bytes.fromhex(packet.signature_hex))
        sig_bytes[0] ^= 0x80
        bad = packet.model_copy(update={"signature_hex": bytes(sig_bytes).hex()})
        result = v.verify_packet(bad, now_ns=_NOW_NS)
        assert result.valid is False
        assert result.reason == "signature-does-not-verify", result

    def test_job_id_mismatch(self) -> None:
        registry, _, bundle = _build_honest_bundle(job_id="job-A")
        v = _verifier(registry)
        result = v.verify_packet(
            bundle.sensor_packets[0],
            expected_job_id="job-B",
            now_ns=_NOW_NS,
        )
        assert result.valid is False
        assert result.reason == "job-id-mismatch", result

    def test_timestamp_too_old(self) -> None:
        registry, _, bundle = _build_honest_bundle()
        v = _verifier(registry)
        # Fast-forward verifier clock past the freshness window.
        future = _NOW_NS + 120_000_000_000  # 120s ahead
        result = v.verify_packet(bundle.sensor_packets[0], now_ns=future)
        assert result.valid is False
        assert result.reason == "timestamp-out-of-window", result

    def test_timestamp_too_far_in_future(self) -> None:
        registry, _, bundle = _build_honest_bundle()
        v = _verifier(registry)
        # Rewind verifier clock so the packet is "from the future".
        past = _NOW_NS - 120_000_000_000  # 120s behind
        result = v.verify_packet(bundle.sensor_packets[0], now_ns=past)
        assert result.valid is False
        assert result.reason == "timestamp-out-of-window", result

    def test_bundle_empty(self) -> None:
        registry, _, bundle = _build_honest_bundle()
        v = _verifier(registry)
        empty = bundle.model_copy(update={"sensor_packets": []})
        result = v.verify_bundle(empty, now_ns=_NOW_NS)
        assert result.valid is False
        assert result.reason == "bundle-empty", result

    def test_bundle_mixed_robots(self) -> None:
        registry, _, bundle_a = _build_honest_bundle(job_id="job-1")
        # Build a foreign signer + packet, and register the foreign DID
        # too so the verifier doesn't fail at unknown-robot-did first.
        foreign_tee = TEESimulator(robot_did="did:knx:testnet:other-bbbb")
        foreign_signer = SensorSigner(foreign_tee)
        foreign_doc = build_did_document(
            foreign_tee.robot_did,
            public_bytes=foreign_tee.public_bytes,
            auth_bytes=foreign_tee.public_bytes,
            capabilities=[],
            created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        registry.register(foreign_doc)

        foreign_packet = foreign_signer.sign_packet(
            "job-1", SensorChannel.CAMERA, _NOW_NS - 100, b"x"
        )
        mixed = bundle_a.model_copy(
            update={
                "sensor_packets": [bundle_a.sensor_packets[0], foreign_packet],
            },
        )
        v = _verifier(registry)
        result = v.verify_bundle(mixed, now_ns=_NOW_NS)
        assert result.valid is False
        assert result.reason == "bundle-mixed-robots", result

    def test_bundle_mixed_jobs(self) -> None:
        registry, signer, bundle_a = _build_honest_bundle(job_id="job-1")
        # Sign a packet against a different job.
        foreign_packet = signer.sign_packet("job-OTHER", SensorChannel.CAMERA, _NOW_NS - 100, b"x")
        mixed = bundle_a.model_copy(
            update={
                "sensor_packets": [bundle_a.sensor_packets[0], foreign_packet],
            },
        )
        v = _verifier(registry)
        result = v.verify_bundle(mixed, now_ns=_NOW_NS)
        assert result.valid is False
        assert result.reason == "bundle-mixed-jobs", result

    def test_merkle_root_mismatch(self) -> None:
        registry, _, bundle = _build_honest_bundle()
        v = _verifier(registry)
        # Tamper with the bundle's claimed Merkle root only.
        bad_root = "ee" * 32
        # Compute the actual root via _build first then assert different.
        assert bundle.bundle_merkle_root != bad_root
        bad = bundle.model_copy(update={"bundle_merkle_root": bad_root})
        result = v.verify_bundle(bad, now_ns=_NOW_NS)
        assert result.valid is False
        assert result.reason == "merkle-root-mismatch", result

    def test_nonce_not_monotonic(self) -> None:
        registry, signer, _ = _build_honest_bundle(job_id="job-N")
        # Build a bundle whose two packets have decreasing nonces by
        # signing them in reverse order.
        v = _verifier(registry)
        p0 = signer.sign_packet("job-N", SensorChannel.CAMERA, _NOW_NS - 200, b"a")
        p1 = signer.sign_packet("job-N", SensorChannel.CAMERA, _NOW_NS - 100, b"b")
        # In normal order p0.nonce < p1.nonce. Reverse them.
        out_of_order = signer.build_bundle(
            job_id="job-N",
            task_prompt="x",
            policy_trace=PolicyTrace(
                actions=[{"step": 0}],
                seed=1,
                policy_hash="dd" * 32,
            ),
            packets=[p1, p0],
            submitted_at=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
        )
        result = v.verify_bundle(out_of_order, now_ns=_NOW_NS)
        assert result.valid is False
        assert result.reason == "nonce-not-monotonic", result


# ---------------------------------------------------------------------------
# Property tests — every single bit-flip in any signature → reject
# ---------------------------------------------------------------------------


class TestSignatureCorruption:
    @given(byte=st.integers(min_value=0, max_value=63), bit=st.integers(min_value=0, max_value=7))
    @hsettings(max_examples=30, deadline=None)
    def test_any_signature_bit_flip_rejected(self, byte: int, bit: int) -> None:
        registry, _, bundle = _build_honest_bundle()
        v = _verifier(registry)
        packet = bundle.sensor_packets[0]
        sig = bytearray(bytes.fromhex(packet.signature_hex))
        sig[byte] ^= 1 << bit
        bad = packet.model_copy(update={"signature_hex": bytes(sig).hex()})
        result = v.verify_packet(bad, now_ns=_NOW_NS)
        assert result.valid is False
        assert result.reason == "signature-does-not-verify"


# ---------------------------------------------------------------------------
# VerificationResult dataclass shape
# ---------------------------------------------------------------------------


class TestVerificationResult:
    def test_is_frozen_dataclass(self) -> None:
        r = VerificationResult(valid=True, reason="ok")
        with pytest.raises((AttributeError, Exception)):
            r.valid = False  # type: ignore[misc]

    def test_replace_works(self) -> None:
        r = VerificationResult(valid=True, reason="ok")
        r2 = replace(r, valid=False, reason="x")
        assert r2 == VerificationResult(valid=False, reason="x")


class TestConstructorGuards:
    def test_negative_skew_rejected(self) -> None:
        registry = IdentityRegistry()
        with pytest.raises(ValueError, match="non-negative"):
            RootIDVerifier(registry, max_clock_skew_ns=-1)

    def test_negative_freshness_rejected(self) -> None:
        registry = IdentityRegistry()
        with pytest.raises(ValueError, match="non-negative"):
            RootIDVerifier(registry, freshness_window_ns=-1)

    def test_now_ns_defaults_to_wall_clock(self) -> None:
        # Smoke-check the ``now_ns is None`` branch by passing a packet
        # with a real-now-relative timestamp and not supplying now_ns.
        registry, _, bundle = _build_honest_bundle(
            base_ts=_NOW_NS - 1_000_000_000,
        )
        # Use a wide-open verifier so the wall-clock-vs-fixture skew
        # doesn't cause spurious freshness failures.
        v = RootIDVerifier(
            registry,
            max_clock_skew_ns=10**18,
            freshness_window_ns=10**18,
        )
        result = v.verify_packet(bundle.sensor_packets[0])
        assert result.valid is True
