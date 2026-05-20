"""SensorSigner — assembles signed PoPWBundles from a TEE-backed signer.

The signer is a thin coordinator. All private-key-touching work happens
inside ``TEESimulator``; this module only handles bundle assembly,
Merkle root computation, and the cross-packet invariants the verifier
relies on (single robot per bundle, single job per bundle, non-empty).

The Merkle leaves are the canonical pre-hash bytes from
``core.crypto.canonical_sensor_bytes`` — the same bytes the TEE
hashed before signing. This makes the bundle's Merkle root a
verifier-side commitment that does not depend on the (mutable)
base64 encoding of the raw payload.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from core import crypto
from core.models import PoPWBundle

if TYPE_CHECKING:
    from datetime import datetime

    from core.models import PolicyTrace, SensorChannel, SensorPacket
    from rootid.tee_simulator import TEESimulator


class SensorSignerError(RuntimeError):
    """Bundle-assembly invariant violation.

    Distinct from ``ValueError`` so callers can branch on
    "signer says this bundle is malformed" vs "Pydantic says these
    fields are individually invalid".
    """


class SensorSigner:
    """Signs ``SensorPacket``s and assembles ``PoPWBundle``s."""

    def __init__(self, tee: TEESimulator) -> None:
        self._tee = tee

    @property
    def robot_did(self) -> str:
        """The DID this signer is bound to (delegates to the TEE)."""
        return self._tee.robot_did

    def sign_packet(
        self,
        job_id: str,
        channel: SensorChannel,
        timestamp_ns: int,
        data: bytes,
    ) -> SensorPacket:
        """Delegate to the TEE; returns a fully-signed ``SensorPacket``."""
        return self._tee.sign_sensor_packet(
            job_id=job_id,
            channel=channel,
            timestamp_ns=timestamp_ns,
            data=data,
        )

    def build_bundle(
        self,
        *,
        job_id: str,
        task_prompt: str,
        policy_trace: PolicyTrace,
        packets: list[SensorPacket],
        submitted_at: datetime,
    ) -> PoPWBundle:
        """Compose a ``PoPWBundle`` over already-signed packets.

        Raises:
            SensorSignerError: If ``packets`` is empty, or if any
                packet's ``robot_did`` differs from this signer's, or
                if any packet's ``job_id`` differs from the bundle's.
        """
        if not packets:
            msg = "cannot build a bundle from an empty packet list"
            raise SensorSignerError(msg)

        signer_did = self._tee.robot_did
        for idx, packet in enumerate(packets):
            if packet.robot_did != signer_did:
                msg = (
                    f"packet[{idx}] has robot_did={packet.robot_did!r} "
                    f"but signer is {signer_did!r}"
                )
                raise SensorSignerError(msg)
            if packet.job_id != job_id:
                msg = f"packet[{idx}] has job_id={packet.job_id!r} " f"but bundle is {job_id!r}"
                raise SensorSignerError(msg)

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
        merkle_root_hex = crypto.merkle_root(leaves).hex()

        return PoPWBundle(
            job_id=job_id,
            robot_did=signer_did,
            task_prompt=task_prompt,
            policy_trace=policy_trace,
            sensor_packets=list(packets),
            bundle_merkle_root=merkle_root_hex,
            submitted_at=submitted_at,
        )
