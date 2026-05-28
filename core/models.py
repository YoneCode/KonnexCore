"""Pydantic schemas shared across all KonnexCore layers.

These types are the single contract between ``rootid``, ``detverify``,
``honeynet``, and ``api``. Per spec Section 5 ("Rules for using these
models") every API endpoint, every test, and every inter-module call
exchanges instances of these classes — never raw dicts.

Konnex compatibility is anchored at ``ScoreVector``, which mirrors the
AI Verifier schema documented at
https://docs.konnex.world/supported-ai-models/verifier exactly.
Extensions to that schema live only in ``DetVerifyResult.stage_results``.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Regex for the ``did:knx:`` method per spec Section 5.
_DID_PATTERN = r"^did:knx:[a-zA-Z0-9_:.-]+$"


# ============================================================
# IDENTITY (Layer A — RootID)
# ============================================================


class DIDDocument(BaseModel):
    """W3C-compliant DID Document for a robot identity.

    The ``id`` field follows the ``did:knx:`` method (spec Section 5).
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        pattern=_DID_PATTERN,
        description="DID identifier per the did:knx: method.",
    )
    public_key_hex: str = Field(
        ...,
        description="Hex-encoded Ed25519 public key (32 bytes).",
    )
    auth_key_hex: str = Field(
        ...,
        description="Hex-encoded Ed25519 authentication key (32 bytes).",
    )
    capabilities: list[str] = Field(
        ...,
        description="Sensor capabilities, e.g. ['camera', 'imu', 'lidar'].",
    )
    created_at: datetime = Field(
        ...,
        description="UTC creation timestamp of the DID document.",
    )


class SensorChannel(str, Enum):
    """Enumerates the sensor channels supported by RootID."""

    CAMERA = "camera"
    IMU = "imu"
    LIDAR = "lidar"
    GPS = "gps"
    TORQUE = "torque"
    THERMAL = "thermal"


class SensorPacket(BaseModel):
    """A single sensor reading, signed at capture time by the robot's TEE."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(
        ...,
        description="SHA-3 hash issued by TaskRegistry; binds the packet to a job.",
    )
    robot_did: str = Field(
        ...,
        pattern=_DID_PATTERN,
        description="DID of the originating robot.",
    )
    channel: SensorChannel = Field(..., description="Sensor channel kind.")
    timestamp_ns: int = Field(
        ...,
        ge=0,
        description="Capture timestamp in nanoseconds; must be monotonic per channel.",
    )
    nonce: int = Field(
        ...,
        ge=0,
        description="Monotonic counter per (job_id, channel); enforced by the TEE.",
    )
    data_b64: str = Field(..., description="Base64-encoded raw sensor payload.")
    signature_hex: str = Field(
        ...,
        description="Hex-encoded 64-byte Ed25519 signature over canonical bytes.",
    )


# ============================================================
# BUNDLE (Layer A → Layer B)
# ============================================================


class PolicyTrace(BaseModel):
    """The action sequence the robot's policy produced during a job."""

    model_config = ConfigDict(extra="forbid")

    actions: list[dict[str, object]] = Field(
        ...,
        description="Ordered list of action dicts emitted by the policy.",
    )
    seed: int = Field(..., description="Deterministic-replay seed.")
    policy_hash: str = Field(
        ...,
        description="Hex-encoded SHA-3-256 of the policy WASM.",
    )


class PoPWBundle(BaseModel):
    """The Proof-of-Physical-Work artefact validated by DetVerify."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(..., description="JobID issued by TaskRegistry.")
    robot_did: str = Field(
        ...,
        pattern=_DID_PATTERN,
        description="DID of the robot that produced the bundle.",
    )
    task_prompt: str = Field(..., description="Original natural-language task prompt.")
    policy_trace: PolicyTrace = Field(..., description="Action trace from policy.")
    sensor_packets: list[SensorPacket] = Field(
        ...,
        description="All signed sensor packets captured during execution.",
    )
    bundle_merkle_root: str = Field(
        ...,
        description="Hex-encoded SHA-3-256 Merkle root over sensor_packets.",
    )
    submitted_at: datetime = Field(
        ...,
        description="UTC submission timestamp at the validator.",
    )


# ============================================================
# SCORING (Layer B output, Konnex-compatible schema)
# ============================================================


Verdict = Literal["success", "failure", "inconclusive"]


class ScoreVector(BaseModel):
    """Konnex AI Verifier output schema, exactly.

    Source: https://docs.konnex.world/supported-ai-models/verifier
    Any divergence is a bug.
    """

    model_config = ConfigDict(extra="forbid")

    accuracy: int = Field(..., ge=0, le=100)
    speed: int = Field(..., ge=0, le=100)
    safety: int = Field(..., ge=0, le=100)
    optimal_track: int = Field(..., ge=0, le=100)
    energy_efficiency: int = Field(..., ge=0, le=100)
    trajectory_stability: int = Field(..., ge=0, le=100)
    final_pct: int = Field(..., ge=0, le=100)
    verdict: Verdict
    reasoning: str


class StageResult(BaseModel):
    """Result of a single DetVerify pipeline stage."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Stage identifier, e.g. 'signature'.")
    passed: bool = Field(..., description="Whether this stage's checks passed.")
    detail: str = Field(..., description="Human-readable explanation.")
    severity: Literal["info", "warning", "fail"] = Field(default="info")


class DetVerifyResult(BaseModel):
    """KonnexCore extension to ``ScoreVector``; preserves Konnex compatibility."""

    model_config = ConfigDict(extra="forbid")

    score: ScoreVector = Field(..., description="Konnex-compatible score vector.")
    stage_results: list[StageResult] = Field(
        ...,
        description="Per-stage outcomes from the deterministic pipeline.",
    )
    deterministic_only: bool = Field(
        ...,
        description="True if no LLM tier was consulted.",
    )
    llm_comparison: ScoreVector | None = Field(
        default=None,
        description="Optional GPT-4o reference score.",
    )
    layers_agree: bool | None = Field(
        default=None,
        description="True iff deterministic verdict matches LLM verdict per metascore Layer 3.",
    )


# ============================================================
# HONEYNET (Layer C)
# ============================================================


class Subnet(str, Enum):
    """Konnex subnet workload classes."""

    DRONE = "drone-navigation"
    ROBOARM = "roboarm-vla"
    SLAM = "slam-3d-map"


class HoneypotTask(BaseModel):
    """A task with hidden ground truth, indistinguishable from organic ones."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(..., description="JobID — same shape as organic tasks.")
    subnet: Subnet = Field(..., description="Target subnet.")
    prompt: str = Field(..., description="Task prompt presented to validators.")
    deadline_s: int = Field(..., ge=0, description="Validation deadline in seconds.")
    reward_test_knx: float = Field(
        ...,
        ge=0.0,
        description="Test-KNX reward to mimic organic incentives.",
    )
    is_honeypot: Literal[True] = Field(
        default=True,
        description="Always True; only the oracle sees this field.",
    )
    ground_truth_score: ScoreVector = Field(
        ...,
        description="Secret answer key used for validator scoring.",
    )
    ground_truth_hash: str = Field(
        ...,
        description="Hex-encoded commitment of ground_truth_score.",
    )


class ValidatorVote(BaseModel):
    """A single validator's score for a job."""

    model_config = ConfigDict(extra="forbid")

    validator_did: str = Field(
        ...,
        pattern=_DID_PATTERN,
        description="DID of the voting validator.",
    )
    job_id: str = Field(..., description="JobID being voted on.")
    score: ScoreVector = Field(..., description="Validator's score vector.")
    submitted_at: datetime = Field(..., description="UTC vote submission timestamp.")


class ValidatorMetascore(BaseModel):
    """Validator metascore S(V_i) = α·C + β·H − γ·P.

    Source: https://docs.konnex.world/understand-konnex/validator-metascore
    """

    model_config = ConfigDict(extra="forbid")

    validator_did: str = Field(
        ...,
        pattern=_DID_PATTERN,
        description="DID of the validator being scored.",
    )
    consensus_term: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="C(W_i, W̄): consensus alignment with network.",
    )
    honeypot_accuracy: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="H(V_i): accuracy on injected honeypots.",
    )
    penalty_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="P_i: operational penalty score.",
    )
    alpha: float = Field(default=0.5, ge=0.0, description="Consensus weight.")
    beta: float = Field(default=0.4, ge=0.0, description="Honeypot weight.")
    gamma: float = Field(default=0.1, ge=0.0, description="Penalty weight.")
    metascore: float = Field(..., description="Final S(V_i) value.")
    sample_count: int = Field(
        ...,
        ge=0,
        description="Number of votes contributing to this metascore.",
    )
