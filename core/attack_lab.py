"""Adversarial PoPWBundle generators (Phase 4).

Each ``make_*_bundle`` function returns a ``(bundle, expected_stage)``
pair where ``bundle`` is a fully Pydantic-valid ``PoPWBundle`` that
*looks* clean to a naive structural validator but trips a specific
DetVerify stage. The string ``expected_stage`` is the
``StageResult.name`` whose ``severity == "fail"`` after the pipeline
runs.

The attack catalogue maps spec §9 Phase 4 sub-tasks 1:1 onto pipeline
stages so the demo and tests can attribute every adversarial bundle
to a precise detection mechanism:

    deepfake_video_bundle      → stage 1 (signature; tampered packet)
    replayed_imu_bundle        → stage 1 (signature; intra-bundle nonce
                                  monotonicity check in rootid verifier)
    gps_spoof_bundle           → stage 1 (signature; foreign signer)
    frame_skip_bundle          → stage 2 (temporal; non-monotonic ts)
    torque_mismatch_bundle     → stage 6 (kinematic; envelope overshoot)

Three of the five attacks land on stage 1 — that is the *correct*
behaviour: spec §6.2 makes signature checking the gate every other
stage stands behind. Each attack still has a precisely-named
``StageResult.detail`` reason so the demo distinguishes them.

All generators take a builder context (TEE + signer + registry) so
tests can register the attacker's identity ahead of time and assert
that the failure is *not* incidentally caused by an unknown DID.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import numpy as np

from core import sensor_codec
from core.models import PolicyTrace, PoPWBundle, SensorChannel
from core.sim_engine import SimConfig, SimEngine
from rootid.did import build_did_document
from rootid.registry import IdentityRegistry
from rootid.sensor_signer import SensorSigner
from rootid.tee_simulator import TEESimulator

if TYPE_CHECKING:
    from core.models import SensorPacket

# ---------------------------------------------------------------------------
# Attack catalogue metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AttackOutcome:
    """Result of an attack-generator call.

    Attributes:
        bundle: The adversarial ``PoPWBundle``. Structurally valid
            (passes Pydantic), so a naive verifier accepts it.
        expected_stage: The ``StageResult.name`` whose
            ``severity == "fail"`` after running the bundle through
            the DetVerify pipeline.
        registry: The identity registry that knows the bundle's
            *legitimate* robot. Verifying with this registry gives
            authentic signatures the chance to pass — which is what
            makes downstream stage failures attributable to the
            attack rather than incidental key mismatches. Tests and
            demos should hand this registry to ``RootIDVerifier``.
        narrative: One-sentence description for human-facing demos.
    """

    bundle: PoPWBundle
    expected_stage: str
    registry: IdentityRegistry
    narrative: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_clean_context(
    *,
    seed: int,
    robot_did: str = "did:knx:testnet:attack-lab-robot",
) -> tuple[TEESimulator, SensorSigner, IdentityRegistry, PoPWBundle]:
    """Construct a TEE + signer + registry + clean bundle for an attack."""
    cfg = SimConfig(
        robot_did=robot_did,
        seed=seed,
        num_steps=20,
        capture_every_n_steps=10,
        camera_width=32,
        camera_height=32,
    )
    tee = TEESimulator(robot_did=cfg.robot_did)
    signer = SensorSigner(tee)

    registry = IdentityRegistry()
    registry.register(
        build_did_document(
            tee.robot_did,
            public_bytes=tee.public_bytes,
            auth_bytes=tee.public_bytes,
            capabilities=["camera", "imu", "torque"],
            created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        ),
    )

    bundle = SimEngine(cfg, tee).run()
    return tee, signer, registry, bundle


def _replace_packet_at(
    bundle: PoPWBundle,
    index: int,
    new_packet: SensorPacket,
) -> PoPWBundle:
    new_packets = list(bundle.sensor_packets)
    new_packets[index] = new_packet
    return bundle.model_copy(update={"sensor_packets": new_packets})


# ---------------------------------------------------------------------------
# Attack 1 — Deepfake video
# ---------------------------------------------------------------------------


def make_deepfake_video_bundle(*, seed: int = 1) -> AttackOutcome:
    """Splice a synthesised camera frame into an otherwise-signed bundle.

    The bundle's first camera packet has its ``data_b64`` swapped for a
    fabricated frame *without* re-signing. Naive structural validators
    pass it (the JSON shape is intact); DetVerify Stage 1 rejects the
    packet because the signature was over the original canonical bytes.
    """
    _, _, registry, bundle = _build_clean_context(seed=seed)
    cam_idx, cam_packet = next(
        (i, p) for i, p in enumerate(bundle.sensor_packets) if p.channel == SensorChannel.CAMERA
    )
    fake = np.full((32, 32, 4), 255, dtype=np.uint8)  # solid white "deepfake"
    fake_payload = sensor_codec.encode_camera_frame(fake)
    spliced = cam_packet.model_copy(
        update={"data_b64": base64.b64encode(fake_payload).decode("ascii")},
    )
    attacked = _replace_packet_at(bundle, cam_idx, spliced)
    return AttackOutcome(
        bundle=attacked,
        expected_stage="signature",
        registry=registry,
        narrative=(
            "synthesised camera frame swapped into an otherwise-signed " "bundle without re-signing"
        ),
    )


# ---------------------------------------------------------------------------
# Attack 2 — Replayed IMU
# ---------------------------------------------------------------------------


def make_replayed_imu_bundle(*, seed: int = 2) -> AttackOutcome:
    """Duplicate an existing IMU packet within the same bundle.

    The duplicate retains its original signature and (channel, nonce)
    pair. Stage 1 sees two valid signatures (the duplicate is a
    byte-identical copy). Stage 4 catches the duplicate
    ``(channel, nonce)`` tuple.
    """
    _, _, registry, bundle = _build_clean_context(seed=seed)
    imu_idx, imu_packet = next(
        (i, p) for i, p in enumerate(bundle.sensor_packets) if p.channel == SensorChannel.IMU
    )
    # Splice a duplicate copy right after the original.
    new_packets = list(bundle.sensor_packets)
    new_packets.insert(imu_idx + 1, imu_packet.model_copy())
    attacked = bundle.model_copy(update={"sensor_packets": new_packets})
    return AttackOutcome(
        bundle=attacked,
        expected_stage="signature",
        registry=registry,
        narrative=(
            "old IMU packet replayed into the bundle (same channel + nonce, "
            "valid signature); caught by rootid's intra-bundle monotonic-"
            "nonce invariant at Stage 1"
        ),
    )


# ---------------------------------------------------------------------------
# Attack 3 — GPS spoof (foreign signer impersonation)
# ---------------------------------------------------------------------------


def make_gps_spoof_bundle(*, seed: int = 3) -> AttackOutcome:
    """Inject a GPS packet signed by an unauthorised foreign TEE.

    The Phase 2 ``SimEngine`` does not synthesise GPS, so an honest
    attacker may try to attach a forged GPS stream. The injected
    packet's signature was produced by a *different* keypair from the
    bundle's robot, so Stage 1 (signature verification under the
    bundle's registered public key) rejects it.

    Note: this also illustrates why Stage 1 must verify against the
    *bundle*'s registered key rather than any key — without that,
    an attacker could forge GPS data using their own valid signature.
    """
    tee, signer, registry, bundle = _build_clean_context(seed=seed)

    # Foreign TEE produces a "GPS" packet that LOOKS valid in isolation.
    foreign_tee = TEESimulator(
        robot_did="did:knx:testnet:attack-lab-foreign",
    )
    foreign_signer = SensorSigner(foreign_tee)
    spoof_payload = b"GPS-FAKE-37.7749,-122.4194"  # arbitrary opaque bytes
    foreign_packet = foreign_signer.sign_packet(
        bundle.job_id,
        SensorChannel.GPS,
        timestamp_ns=bundle.sensor_packets[-1].timestamp_ns + 1_000_000,
        data=spoof_payload,
    )
    # Pretend the foreign packet came from the bundle's robot. The
    # signature stays the foreign one, so verification fails.
    impersonating = foreign_packet.model_copy(update={"robot_did": tee.robot_did})

    new_packets = [*bundle.sensor_packets, impersonating]

    # The merkle root must match the new packet list or stage 1 catches
    # merkle-root-mismatch BEFORE the signature check. The attacker who
    # has the canonical pre-hashes can recompute the root, so we do
    # the same here to keep the attack hitting the *signature* stage.
    from core import crypto

    leaves = [
        crypto.canonical_sensor_bytes(
            job_id=p.job_id,
            channel=p.channel.value,
            timestamp_ns=p.timestamp_ns,
            nonce=p.nonce,
            data=base64.b64decode(p.data_b64),
        )
        for p in new_packets
    ]
    new_root_hex = crypto.merkle_root(leaves).hex()
    attacked = bundle.model_copy(
        update={
            "sensor_packets": new_packets,
            "bundle_merkle_root": new_root_hex,
        },
    )
    # Reference signer to suppress lint warning for unused name in code review.
    _ = signer
    return AttackOutcome(
        bundle=attacked,
        expected_stage="signature",
        registry=registry,
        narrative=(
            "forged GPS packet signed by a foreign TEE and re-attributed " "to the bundle's robot"
        ),
    )


# ---------------------------------------------------------------------------
# Attack 4 — Frame skip (non-monotonic timestamps, properly signed)
# ---------------------------------------------------------------------------


def make_frame_skip_bundle(*, seed: int = 4) -> AttackOutcome:
    """Sign two camera packets with strictly decreasing timestamps.

    The ``TEESimulator`` enforces monotonic *nonces* per
    ``(job_id, channel)`` but does not police the *timestamps* —
    timestamps are caller-supplied so a malicious scheduler can
    splice frames out of order. Stage 1 still passes (every packet
    is signed correctly over its own timestamp). Stage 2 catches the
    decreasing timestamp on camera[1].
    """
    _, signer, registry, _ = _build_clean_context(seed=seed)
    job_id = "frame-skip-job"
    # First packet at a much later timestamp than the second.
    p_late = signer.sign_packet(job_id, SensorChannel.CAMERA, 200_000_000, b"frame-late")
    p_early = signer.sign_packet(job_id, SensorChannel.CAMERA, 100_000_000, b"frame-early")

    bundle = signer.build_bundle(
        job_id=job_id,
        task_prompt="frame-skip attack",
        policy_trace=PolicyTrace(
            actions=[{"step": 0}],
            seed=seed,
            policy_hash="dd" * 32,
        ),
        packets=[p_late, p_early],
        submitted_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )
    return AttackOutcome(
        bundle=bundle,
        expected_stage="temporal",
        registry=registry,
        narrative=(
            "two camera packets signed with decreasing timestamps within "
            "the same channel (frame splice attack)"
        ),
    )


# ---------------------------------------------------------------------------
# Attack 5 — Torque mismatch (signed values exceed kinematic envelope)
# ---------------------------------------------------------------------------


def make_torque_mismatch_bundle(*, seed: int = 5) -> AttackOutcome:
    """Sign a torque packet whose values exceed the kinematic envelope.

    The TEE happily signs whatever bytes it is handed — kinematic
    plausibility is a Stage 6 check, not a TEE concern. The bundle is
    fully signed and merkle-committed, so Stages 1, 2, 4, 5 all pass.
    Stage 6 catches per-joint torques that exceed the configured
    envelope (default 320 N·m).
    """
    _, signer, registry, _ = _build_clean_context(seed=seed)
    job_id = "torque-mismatch-job"

    # Sign one packet per channel so the bundle has a balanced shape;
    # only the torque packet carries the malicious payload.
    cam_payload = sensor_codec.encode_camera_frame(
        np.zeros((32, 32, 4), dtype=np.uint8),
    )
    imu_payload = sensor_codec.encode_imu(accel=(0.0, 0.0, 9.81), gyro=(0.0, 0.0, 0.0))
    bad_torque_payload = sensor_codec.encode_torque(tuple([99_999.0] * 7))

    p_cam = signer.sign_packet(job_id, SensorChannel.CAMERA, 1_000_000, cam_payload)
    p_imu = signer.sign_packet(job_id, SensorChannel.IMU, 2_000_000, imu_payload)
    p_torque = signer.sign_packet(job_id, SensorChannel.TORQUE, 3_000_000, bad_torque_payload)

    bundle = signer.build_bundle(
        job_id=job_id,
        task_prompt="torque-mismatch attack",
        policy_trace=PolicyTrace(
            actions=[{"step": 0}],
            seed=seed,
            policy_hash="dd" * 32,
        ),
        packets=[p_cam, p_imu, p_torque],
        submitted_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )
    return AttackOutcome(
        bundle=bundle,
        expected_stage="kinematic",
        registry=registry,
        narrative=(
            "torque packet signed with all-99999 N·m values, well above "
            "the Kuka iiwa per-joint envelope"
        ),
    )


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


#: Mapping from human-facing attack name → generator callable. Used by
#: ``examples/04_attack_lab.py`` to iterate the catalogue.
ATTACK_GENERATORS: dict[str, object] = {
    "deepfake_video": make_deepfake_video_bundle,
    "replayed_imu": make_replayed_imu_bundle,
    "gps_spoof": make_gps_spoof_bundle,
    "frame_skip": make_frame_skip_bundle,
    "torque_mismatch": make_torque_mismatch_bundle,
}
