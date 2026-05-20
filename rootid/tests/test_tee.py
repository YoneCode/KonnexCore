"""Tests for ``rootid/tee_simulator.py``.

These tests pin the security-critical invariants documented in the
Phase 1 plan and the spec (§6.2):

1.  Private key bytes never appear in any public attribute, ``repr``,
    ``str``, or return value.
2.  ``sign_sensor_packet`` issues nonces 0, 1, 2, ... per
    ``(job_id, channel)`` pair, strictly monotonic.
3.  Distinct ``(job_id, channel)`` pairs share no counter state.
4.  The returned packet's signature verifies against the simulator's
    public key over the canonical digest from ``core.crypto``.
5.  Negative ``timestamp_ns`` is rejected.
6.  Empty ``data`` is allowed (sensor heartbeats).
7.  ``attest()`` returns only public material plus a versioned scheme
    identifier — never the private key.
"""

from __future__ import annotations

import binascii

import pytest

from core import crypto
from core.config import ED25519_PUBLIC_BYTES, ED25519_SIGNATURE_BYTES
from core.models import SensorChannel
from rootid.tee_simulator import TEESimulator


@pytest.fixture
def tee() -> TEESimulator:
    return TEESimulator(robot_did="did:knx:testnet:abc1234567890abc")


# ---------------------------------------------------------------------------
# Invariant 1 — private key isolation
# ---------------------------------------------------------------------------


class TestKeyIsolation:
    def test_public_bytes_correct_length(self, tee: TEESimulator) -> None:
        assert len(tee.public_bytes) == ED25519_PUBLIC_BYTES

    def test_robot_did_exposed(self, tee: TEESimulator) -> None:
        assert tee.robot_did == "did:knx:testnet:abc1234567890abc"

    def test_repr_does_not_leak_private(self, tee: TEESimulator) -> None:
        # Capture private bytes via the leading-underscore back door —
        # then assert they do NOT appear in repr.
        priv_hex = tee._private_bytes.hex()
        assert priv_hex not in repr(tee)
        assert priv_hex not in str(tee)

    def test_repr_includes_public_material(self, tee: TEESimulator) -> None:
        assert tee.public_bytes.hex() in repr(tee) or tee.robot_did in repr(tee)

    def test_no_public_attribute_named_private(self, tee: TEESimulator) -> None:
        public_attrs = [a for a in dir(tee) if not a.startswith("_")]
        assert "private_bytes" not in public_attrs
        assert "private" not in public_attrs

    def test_two_simulators_have_distinct_keys(self) -> None:
        a = TEESimulator(robot_did="did:knx:testnet:robot-a")
        b = TEESimulator(robot_did="did:knx:testnet:robot-b")
        assert a.public_bytes != b.public_bytes
        assert a._private_bytes != b._private_bytes


# ---------------------------------------------------------------------------
# Invariants 2 & 3 — nonce monotonicity per (job_id, channel)
# ---------------------------------------------------------------------------


class TestNonceMonotonicity:
    def test_first_packet_for_pair_has_nonce_zero(self, tee: TEESimulator) -> None:
        p = tee.sign_sensor_packet(
            job_id="job-1",
            channel=SensorChannel.CAMERA,
            timestamp_ns=1,
            data=b"frame",
        )
        assert p.nonce == 0

    def test_subsequent_packets_increment(self, tee: TEESimulator) -> None:
        p0 = tee.sign_sensor_packet("job-1", SensorChannel.CAMERA, 1, b"a")
        p1 = tee.sign_sensor_packet("job-1", SensorChannel.CAMERA, 2, b"b")
        p2 = tee.sign_sensor_packet("job-1", SensorChannel.CAMERA, 3, b"c")
        assert (p0.nonce, p1.nonce, p2.nonce) == (0, 1, 2)

    def test_distinct_channels_independent_counters(self, tee: TEESimulator) -> None:
        p_cam = tee.sign_sensor_packet("job-1", SensorChannel.CAMERA, 1, b"a")
        p_imu = tee.sign_sensor_packet("job-1", SensorChannel.IMU, 1, b"b")
        # Both start at 0 because the counter is keyed on (job_id, channel).
        assert p_cam.nonce == 0
        assert p_imu.nonce == 0

    def test_distinct_jobs_independent_counters(self, tee: TEESimulator) -> None:
        p_a = tee.sign_sensor_packet("job-A", SensorChannel.CAMERA, 1, b"a")
        p_b = tee.sign_sensor_packet("job-B", SensorChannel.CAMERA, 1, b"b")
        assert p_a.nonce == 0
        assert p_b.nonce == 0


# ---------------------------------------------------------------------------
# Invariant 4 — signature verifies against canonical digest
# ---------------------------------------------------------------------------


class TestSignatureVerifies:
    def test_signature_length(self, tee: TEESimulator) -> None:
        p = tee.sign_sensor_packet("job-1", SensorChannel.CAMERA, 1, b"x")
        sig = bytes.fromhex(p.signature_hex)
        assert len(sig) == ED25519_SIGNATURE_BYTES

    def test_signature_verifies_against_canonical_digest(self, tee: TEESimulator) -> None:
        data = b"frame-bytes"
        p = tee.sign_sensor_packet("job-1", SensorChannel.CAMERA, 100, data)
        sig = bytes.fromhex(p.signature_hex)
        digest = crypto.canonical_sensor_digest(
            job_id=p.job_id,
            channel=p.channel.value,
            timestamp_ns=p.timestamp_ns,
            nonce=p.nonce,
            data=data,
        )
        assert crypto.verify(tee.public_bytes, digest, sig)

    def test_signature_does_not_verify_with_tampered_data(self, tee: TEESimulator) -> None:
        p = tee.sign_sensor_packet("job-1", SensorChannel.CAMERA, 1, b"good")
        sig = bytes.fromhex(p.signature_hex)
        wrong_digest = crypto.canonical_sensor_digest(
            p.job_id, p.channel.value, p.timestamp_ns, p.nonce, b"BAD"
        )
        assert not crypto.verify(tee.public_bytes, wrong_digest, sig)

    def test_packet_robot_did_matches_simulator(self, tee: TEESimulator) -> None:
        p = tee.sign_sensor_packet("job-1", SensorChannel.CAMERA, 1, b"x")
        assert p.robot_did == tee.robot_did

    def test_packet_data_b64_round_trips(self, tee: TEESimulator) -> None:
        import base64

        original = b"\x00\x01\x02hello\xff"
        p = tee.sign_sensor_packet("job-1", SensorChannel.CAMERA, 1, original)
        assert base64.b64decode(p.data_b64) == original


# ---------------------------------------------------------------------------
# Invariants 5 & 6 — input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_negative_timestamp_rejected(self, tee: TEESimulator) -> None:
        with pytest.raises(ValueError, match="timestamp"):
            tee.sign_sensor_packet("j", SensorChannel.CAMERA, -1, b"x")

    def test_empty_data_allowed(self, tee: TEESimulator) -> None:
        p = tee.sign_sensor_packet("j", SensorChannel.CAMERA, 1, b"")
        sig = bytes.fromhex(p.signature_hex)
        digest = crypto.canonical_sensor_digest("j", SensorChannel.CAMERA.value, 1, 0, b"")
        assert crypto.verify(tee.public_bytes, digest, sig)

    def test_rejects_empty_robot_did_in_constructor(self) -> None:
        with pytest.raises(ValueError, match="robot_did"):
            TEESimulator(robot_did="")

    def test_rejects_malformed_robot_did_in_constructor(self) -> None:
        with pytest.raises(ValueError, match="did:knx:"):
            TEESimulator(robot_did="not-a-did")


# ---------------------------------------------------------------------------
# Invariant 7 — attestation returns only public material
# ---------------------------------------------------------------------------


class TestAttest:
    def test_attest_includes_public_fields(self, tee: TEESimulator) -> None:
        report = tee.attest()
        assert report["robot_did"] == tee.robot_did
        assert report["public_key_hex"] == tee.public_bytes.hex()
        assert report["scheme"] == "ed25519-sha3-256-v1"

    def test_attest_does_not_leak_private(self, tee: TEESimulator) -> None:
        priv_hex = tee._private_bytes.hex()
        report = tee.attest()
        for value in report.values():
            assert priv_hex not in value

    def test_attest_keys_are_only_public_set(self, tee: TEESimulator) -> None:
        report = tee.attest()
        assert set(report.keys()) == {"robot_did", "public_key_hex", "scheme"}


# ---------------------------------------------------------------------------
# Smoke check that the produced packet is itself spec-compliant
# ---------------------------------------------------------------------------


def test_packet_signature_hex_is_valid_hex(tee: TEESimulator) -> None:
    p = tee.sign_sensor_packet("job-1", SensorChannel.CAMERA, 1, b"x")
    # bytes.fromhex raises if the string isn't valid hex.
    try:
        bytes.fromhex(p.signature_hex)
    except binascii.Error as exc:
        pytest.fail(f"signature_hex is not valid hex: {exc}")
