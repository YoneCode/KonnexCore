"""RootID HTTP endpoints — Layer A."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from api.deps import AppState, get_state
from core.models import DIDDocument, PolicyTrace, PoPWBundle, SensorChannel, SensorPacket
from rootid.did import build_did_document, make_did
from rootid.registry import IdentityRegistryError
from rootid.sensor_signer import SensorSigner
from rootid.tee_simulator import TEESimulator

router = APIRouter(prefix="/api/identity", tags=["identity"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateIdentityRequest(BaseModel):
    """Body for ``POST /api/identity/create``."""

    model_config = ConfigDict(extra="forbid")

    network: str = Field(default="testnet")
    capabilities: list[str] = Field(default_factory=lambda: ["camera", "imu", "torque"])


class SignBundlePacket(BaseModel):
    """One unsigned sensor reading for the sign-bundle endpoint."""

    model_config = ConfigDict(extra="forbid")

    channel: SensorChannel
    timestamp_ns: int = Field(..., ge=0)
    data_b64: str


class SignBundleRequest(BaseModel):
    """Body for ``POST /api/identity/sign-bundle``."""

    model_config = ConfigDict(extra="forbid")

    robot_did: str
    job_id: str
    task_prompt: str
    policy_trace: PolicyTrace
    packets: list[SignBundlePacket]


class VerifyPacketResponse(BaseModel):
    """Response for ``POST /api/identity/verify-packet``."""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    reason: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/create",
    response_model=DIDDocument,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new robot identity (server-held TEE)",
)
def create_identity(
    body: CreateIdentityRequest,
    state: Annotated[AppState, Depends(get_state)],
) -> DIDDocument:
    """Generate a fresh keypair, register the DID, return the document.

    Server-held TEE pool is a demo affordance — production deployments
    keep keys inside the robot's hardware secure element.
    """
    tee = TEESimulator(robot_did=make_did(body.network, b"\x00" * 32))
    # Replace synthetic DID with the deterministic one from the actual key.
    real_did = make_did(body.network, tee.public_bytes)
    real_tee = TEESimulator(robot_did=real_did)
    doc = build_did_document(
        real_tee.robot_did,
        public_bytes=real_tee.public_bytes,
        auth_bytes=real_tee.public_bytes,
        capabilities=body.capabilities,
        created_at=datetime.now(tz=timezone.utc),
    )
    try:
        state.registry.register(doc)
    except IdentityRegistryError as exc:
        raise HTTPException(  # noqa: B904 — context preserved in detail
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "did-already-registered", "message": str(exc)},
        )
    state.tee_pool[real_tee.robot_did] = real_tee
    return doc


@router.get(
    "/{did:path}",
    response_model=DIDDocument,
    summary="Resolve a registered DID",
)
def resolve_identity(
    did: str,
    state: Annotated[AppState, Depends(get_state)],
) -> DIDDocument:
    """Look up the DID document. Returns 404 if not registered."""
    try:
        return state.registry.resolve(did)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "unknown-did", "did": did},
        ) from exc


@router.post(
    "/sign-bundle",
    response_model=PoPWBundle,
    summary="Sign a set of sensor packets via the server-held TEE",
)
def sign_bundle(
    body: SignBundleRequest,
    state: Annotated[AppState, Depends(get_state)],
) -> PoPWBundle:
    """Sign the supplied packets and assemble a complete ``PoPWBundle``."""
    tee = state.tee_pool.get(body.robot_did)
    if tee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "unknown-tee",
                "did": body.robot_did,
                "hint": "create the identity via POST /api/identity/create first",
            },
        )
    signer = SensorSigner(tee)
    signed_packets: list[SensorPacket] = []
    for pkt in body.packets:
        try:
            data = base64.b64decode(pkt.data_b64, validate=True)
        except (ValueError, TypeError, binascii.Error) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "bad-base64", "message": str(exc)},
            ) from exc
        signed_packets.append(
            signer.sign_packet(body.job_id, pkt.channel, pkt.timestamp_ns, data),
        )
    return signer.build_bundle(
        job_id=body.job_id,
        task_prompt=body.task_prompt,
        policy_trace=body.policy_trace,
        packets=signed_packets,
        submitted_at=datetime.now(tz=timezone.utc),
    )


@router.post(
    "/verify-packet",
    response_model=VerifyPacketResponse,
    summary="Verify one signed sensor packet against the registry",
)
def verify_packet(
    packet: SensorPacket,
    state: Annotated[AppState, Depends(get_state)],
) -> VerifyPacketResponse:
    """Run the rootid verifier against a single packet."""
    from rootid.verifier import RootIDVerifier

    verifier = RootIDVerifier(
        state.registry,
        max_clock_skew_ns=10**19,
        freshness_window_ns=10**19,
    )
    result = verifier.verify_packet(packet)
    return VerifyPacketResponse(valid=result.valid, reason=result.reason)
