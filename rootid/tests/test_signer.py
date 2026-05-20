"""Tests for ``rootid/sensor_signer.py``."""

from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest

from core import crypto
from core.models import PolicyTrace, PoPWBundle, SensorChannel
from rootid.sensor_signer import SensorSigner, SensorSignerError
from rootid.tee_simulator import TEESimulator

ROBOT_DID = "did:knx:testnet:robot-aaaaaaaa"


@pytest.fixture
def signer() -> SensorSigner:
    return SensorSigner(TEESimulator(robot_did=ROBOT_DID))


def _trace() -> PolicyTrace:
    return PolicyTrace(
        actions=[{"type": "move", "dx": 1}],
        seed=42,
        policy_hash="dd" * 32,
    )


def _now() -> datetime:
    return datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)


class TestSignPacket:
    def test_robot_did_propagates(self, signer: SensorSigner) -> None:
        assert signer.robot_did == ROBOT_DID

    def test_sign_packet_returns_signed_packet(self, signer: SensorSigner) -> None:
        p = signer.sign_packet("job-1", SensorChannel.CAMERA, 1, b"frame")
        assert p.robot_did == ROBOT_DID
        assert p.nonce == 0


class TestBuildBundle:
    def test_build_bundle_round_trips(self, signer: SensorSigner) -> None:
        packets = [
            signer.sign_packet("job-1", SensorChannel.CAMERA, 1, b"a"),
            signer.sign_packet("job-1", SensorChannel.IMU, 2, b"b"),
        ]
        bundle = signer.build_bundle(
            job_id="job-1",
            task_prompt="pick apple",
            policy_trace=_trace(),
            packets=packets,
            submitted_at=_now(),
        )
        # Round-trip via JSON to confirm schema validity end-to-end.
        again = PoPWBundle.model_validate_json(bundle.model_dump_json())
        assert again == bundle

    def test_merkle_root_changes_when_packets_reorder(self, signer: SensorSigner) -> None:
        p_a = signer.sign_packet("job-1", SensorChannel.CAMERA, 1, b"a")
        p_b = signer.sign_packet("job-1", SensorChannel.IMU, 2, b"b")
        bundle_ab = signer.build_bundle(
            job_id="job-1",
            task_prompt="x",
            policy_trace=_trace(),
            packets=[p_a, p_b],
            submitted_at=_now(),
        )
        bundle_ba = signer.build_bundle(
            job_id="job-1",
            task_prompt="x",
            policy_trace=_trace(),
            packets=[p_b, p_a],
            submitted_at=_now(),
        )
        assert bundle_ab.bundle_merkle_root != bundle_ba.bundle_merkle_root

    def test_merkle_root_reproducible_from_packet_data(self, signer: SensorSigner) -> None:
        p = signer.sign_packet("job-1", SensorChannel.CAMERA, 1, b"hello")
        bundle = signer.build_bundle(
            job_id="job-1",
            task_prompt="x",
            policy_trace=_trace(),
            packets=[p],
            submitted_at=_now(),
        )
        # Verifier-side reconstruction:
        leaves = [
            crypto.canonical_sensor_bytes(
                p.job_id,
                p.channel.value,
                p.timestamp_ns,
                p.nonce,
                base64.b64decode(p.data_b64),
            )
        ]
        expected = crypto.merkle_root(leaves).hex()
        assert bundle.bundle_merkle_root == expected

    def test_rejects_empty_packet_list(self, signer: SensorSigner) -> None:
        with pytest.raises(SensorSignerError, match="empty"):
            signer.build_bundle(
                job_id="job-1",
                task_prompt="x",
                policy_trace=_trace(),
                packets=[],
                submitted_at=_now(),
            )

    def test_rejects_packet_from_different_robot(self, signer: SensorSigner) -> None:
        # A packet not produced by this signer's TEE.
        other_signer = SensorSigner(TEESimulator(robot_did="did:knx:testnet:other-robot"))
        foreign = other_signer.sign_packet("job-1", SensorChannel.CAMERA, 1, b"x")
        with pytest.raises(SensorSignerError, match="robot_did"):
            signer.build_bundle(
                job_id="job-1",
                task_prompt="x",
                policy_trace=_trace(),
                packets=[foreign],
                submitted_at=_now(),
            )

    def test_rejects_packet_from_different_job(self, signer: SensorSigner) -> None:
        # Mixing a packet from job-2 into a job-1 bundle is malformed.
        p_other_job = signer.sign_packet("job-2", SensorChannel.CAMERA, 1, b"x")
        with pytest.raises(SensorSignerError, match="job_id"):
            signer.build_bundle(
                job_id="job-1",
                task_prompt="x",
                policy_trace=_trace(),
                packets=[p_other_job],
                submitted_at=_now(),
            )
