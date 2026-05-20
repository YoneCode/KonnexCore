# How to Build KonnexCore — The Complete Build Specification

> A unified dApp combining Idea #1 (DetVerify) + Idea #2 (Honeynet) + Idea #3 (RootID) into one production-quality validator infrastructure stack for the Konnex builder grant.
>
> This document is written so any developer or AI coding agent (Cascade, Cursor, Kiro, Claude Code, etc.) can ship the project from zero with no ambiguity and no mistakes.

---

## Table of Contents

1. [Project Identity & Strategic Positioning](#1-project-identity--strategic-positioning)
2. [Unified Architecture](#2-unified-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Tech Stack & Pinned Dependencies](#4-tech-stack--pinned-dependencies)
5. [Data Models — Exact Schemas](#5-data-models--exact-schemas)
6. [Core Modules — Implementation Spec](#6-core-modules--implementation-spec)
7. [HTTP API Contract](#7-http-api-contract)
8. [Frontend Spec](#8-frontend-spec)
9. [Build Order — Phase-by-Phase](#9-build-order--phase-by-phase)
10. [Testing Requirements](#10-testing-requirements)
11. [VPS Deployment](#11-vps-deployment)
12. [Demo Recording Plan](#12-demo-recording-plan)
13. [Builder Application Submission](#13-builder-application-submission)
14. [Quality Gates — No Slop Allowed](#14-quality-gates--no-slop-allowed)
15. [Konnex Documentation Map](#15-konnex-documentation-map)
16. [Common Mistakes to Avoid](#16-common-mistakes-to-avoid)

---

## 1. Project Identity & Strategic Positioning

### Project name
**KonnexCore** — the validator infrastructure stack Konnex specced but didn't ship.

### One-line pitch (140 chars max — fits the application form)
> KonnexCore: TEE-attested sensor capture + deterministic Layer-3 verifier + honeypot oracle. The validator stack Konnex specced.

### What we explicitly claim
- ✅ Implements `RobotIdentity` smart contract attestation pipeline (Idea #3)
- ✅ Implements deterministic Layer-3 of validator metascore (Idea #1)
- ✅ Implements Layer-2 honeypot oracle of validator metascore (Idea #2)
- ✅ Open-source under MIT
- ✅ Software simulation of TEE (clearly framed; production binds to ARM PSA / Apple Secure Enclave)

### What we do NOT claim
- ❌ Production-grade TEE on real hardware (that is Launch tier work)
- ❌ Mainnet integration (testnet only at Spark)
- ❌ Real robots tested (synthetic + recorded data only)
- ❌ Replaces their AI Verifier (we augment Layer 3; their LLM tier remains Layer 3a)

### RFP Categories Hit
1. **"Sensor fusion & PoPW validation"** — direct match (DetVerify)
2. **"Robot Identity and Memory"** — direct match (RootID)
3. **"Propose your own subnet"** — Honeynet as cross-subnet validator QA

### Grant Tier Targeting
- **Spark ($25K)** — primary target, MVP submission
- **Launch ($75K)** — natural progression after Spark milestones
- **Mainnet ($200K+)** — production hardening + KNX allocation

---

## 2. Unified Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              KONNEXCORE                                 │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                       LAYER A — RootID                          │   │
│  │  did:knx: resolver  │  TEE simulator  │  Sensor packet signer   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │ produces signed PoPW bundles            │
│                              ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      LAYER B — DetVerify                        │   │
│  │  6-stage deterministic verifier                                 │   │
│  │  1. Signature  2. Temporal  3. Cross-modal                      │   │
│  │  4. Replay     5. Anomaly   6. Kinematic                        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │ emits ScoreVector                       │
│                              ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      LAYER C — Honeynet                         │   │
│  │  Generator  │  Ground-truth oracle  │  Validator H(V_i) tracker │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Shared services:  schema · crypto · sim engine · attack lab · CLI     │
│                                                                         │
│  Public surface:   FastAPI (port 8000) · React UI (port 5173/80)       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Layer responsibilities

| Layer | Module | Responsibility | Output |
|-------|--------|----------------|--------|
| A | `rootid/` | Identity, signing, attestation | Signed sensor packets |
| B | `detverify/` | Deterministic scoring of bundles | ScoreVector (Konnex schema) |
| C | `honeynet/` | Honeypot generation + validator QA | H(V_i) per validator |
| Shared | `core/` | Models, crypto, sim, attack, CLI | Used by A, B, C |

### Data flow (canonical example)

```
1. Operator submits task via testnet quest UI → JobID assigned
2. Robot (simulated) reads task → executes in PyBullet
3. RootID signs each sensor frame at capture time
4. PoPW Bundle = signed sensors + policy trace + JobID
5. DetVerify runs 6 deterministic stages → ScoreVector
6. (Optional) GPT-4o reference verifier runs in parallel for comparison
7. Validator emits final score (deterministic + LLM agreement check)
8. Honeynet injects ~10% honeypot tasks → tracks per-validator H(V_i)
9. Onchain commitment posted (mock chain at Spark; real testnet at Launch)
```

---

## 3. Repository Structure

**Exact folder/file layout. Do not deviate.**

```
konnexcore/
├── README.md                          # Hero readme, links to demo URL
├── LICENSE                            # MIT
├── .gitignore                         # Standard Python + Node + venv
├── .env.example                       # Template for env vars
├── pyproject.toml                     # Python project config
├── requirements.txt                   # Pinned Python deps
├── docker-compose.yml                 # Optional: full stack in Docker
├── Makefile                           # `make dev`, `make test`, `make demo`
├── scripts/
│   ├── setup_vps.sh                   # Idempotent VPS bootstrap
│   ├── deploy.sh                      # Build + ship to VPS
│   └── demo.sh                        # Run end-to-end demo locally
│
├── core/                              # SHARED MODULES (used by all layers)
│   ├── __init__.py
│   ├── models.py                      # Pydantic schemas (sensors, bundles, scores)
│   ├── crypto.py                      # Ed25519, SHA-3, Merkle root
│   ├── konnex_schema.py               # Mirrors Konnex JSON schemas exactly
│   ├── sim_engine.py                  # PyBullet wrapper for deterministic replay
│   ├── attack_lab.py                  # Adversarial bundle generators
│   ├── cli.py                         # `konnexcore` CLI entry point
│   └── config.py                      # Settings, env vars
│
├── rootid/                            # LAYER A — Identity & attestation
│   ├── __init__.py
│   ├── did.py                         # did:knx: method implementation
│   ├── tee_simulator.py               # Software TEE with isolated key store
│   ├── sensor_signer.py               # Signs sensor packets at capture
│   ├── verifier.py                    # Verifies signatures, freshness, JobID binding
│   ├── registry.py                    # Mock RobotIdentity contract
│   └── tests/
│       ├── test_did.py
│       ├── test_tee.py
│       └── test_signer.py
│
├── detverify/                         # LAYER B — Deterministic verifier
│   ├── __init__.py
│   ├── pipeline.py                    # Orchestrates 6 stages
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── stage1_signature.py        # Verifies RootID signatures
│   │   ├── stage2_temporal.py         # Timestamp monotonicity, sample rates
│   │   ├── stage3_crossmodal.py       # IMU↔GPS, LiDAR↔camera consistency
│   │   ├── stage4_replay.py           # Nonce/freshness checks
│   │   ├── stage5_anomaly.py          # Isolation Forest on sensor distributions
│   │   └── stage6_kinematic.py        # Joint limits, torque envelope, energy
│   ├── fusion.py                      # Extended Kalman Filter (state estimation)
│   ├── llm_compare.py                 # Adapter to call their GPT-4o reference
│   ├── score_emitter.py               # Emits Konnex-schema ScoreVector
│   └── tests/
│       ├── test_pipeline.py
│       ├── test_stage1.py
│       ├── ...
│       └── test_score_emitter.py
│
├── honeynet/                          # LAYER C — Honeypot oracle
│   ├── __init__.py
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── roboarm_gen.py             # PyBullet kitchen scenes
│   │   ├── drone_gen.py               # PyBullet flight envs
│   │   └── slam_gen.py                # Synthetic point cloud + ground truth
│   ├── injector.py                    # Indistinguishability layer
│   ├── oracle.py                      # Compares validator scores vs ground truth
│   ├── metascore.py                   # Implements S(V_i) = α·C + β·H − γ·P
│   ├── validator_pool.py              # Simulated validator behaviors (honest, lazy, etc.)
│   └── tests/
│       ├── test_generators.py
│       ├── test_oracle.py
│       └── test_metascore.py
│
├── api/                               # FASTAPI HTTP LAYER
│   ├── __init__.py
│   ├── main.py                        # FastAPI app entry
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── identity.py                # /api/identity/* (RootID)
│   │   ├── verify.py                  # /api/verify/* (DetVerify)
│   │   ├── honeypot.py                # /api/honeypot/* (Honeynet)
│   │   ├── attack.py                  # /api/attack/* (test harness)
│   │   └── demo.py                    # /api/demo/* (preset demo flows)
│   ├── deps.py                        # FastAPI dependencies
│   └── middleware.py                  # CORS, logging, error handling
│
├── dashboard/                         # REACT FRONTEND
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/
│   │   └── favicon.svg
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   └── client.ts              # Typed fetch wrappers
│       ├── components/
│       │   ├── Header.tsx
│       │   ├── LayerCard.tsx
│       │   ├── BundleViewer.tsx
│       │   ├── StageTimeline.tsx
│       │   ├── ValidatorChart.tsx
│       │   └── AttackPanel.tsx
│       ├── pages/
│       │   ├── Home.tsx               # Landing
│       │   ├── DetVerifyDemo.tsx      # Layer B demo
│       │   ├── RootIDDemo.tsx         # Layer A demo
│       │   ├── HoneynetDemo.tsx       # Layer C demo
│       │   └── FullStackDemo.tsx      # Combined 60s demo
│       ├── hooks/
│       │   └── useApi.ts
│       └── styles/
│           └── globals.css
│
├── docs/
│   ├── ARCHITECTURE.md                # Deep architecture doc
│   ├── PROTOCOL.md                    # How we mirror Konnex protocol
│   ├── SECURITY.md                    # Threat model
│   ├── APPLICATION.md                 # Pre-filled application form text
│   └── images/
│       └── architecture.svg
│
└── examples/
    ├── 01_sign_sensor.py              # Smallest RootID example
    ├── 02_verify_bundle.py            # Smallest DetVerify example
    ├── 03_honeypot_demo.py            # Smallest Honeynet example
    └── 04_full_stack.py               # End-to-end run
```

**Why this structure:**
- Clear layer separation = easy code review
- Each layer is independently testable
- `core/` shared modules prevent duplication
- `examples/` directory is what reviewers will run first
- `docs/APPLICATION.md` makes form submission instant

---

## 4. Tech Stack & Pinned Dependencies

### Python (`requirements.txt`)

```
# Core framework
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.9.2
pydantic-settings==2.5.2

# Math / sim
numpy==1.26.4
scipy==1.13.1
scikit-learn==1.5.2
filterpy==1.4.5
pybullet==3.2.6

# Crypto
cryptography==43.0.1
pynacl==1.5.0

# CLI & UX
click==8.1.7
rich==13.8.1

# HTTP / data
httpx==0.27.2
orjson==3.10.7

# Testing
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-cov==5.0.0

# Optional: LLM comparison only
openai==1.51.0
opencv-python==4.10.0.84

# Dev
black==24.8.0
ruff==0.6.8
mypy==1.11.2
```

**Why pinned exact versions:** Reproducibility for grant reviewers. They run `pip install -r requirements.txt` and get bit-identical behavior.

### Node (`dashboard/package.json`)

```json
{
  "name": "konnexcore-dashboard",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "tsc && vite build",
    "preview": "vite preview --host 0.0.0.0"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2",
    "recharts": "^2.13.0",
    "lucide-react": "^0.451.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.2"
  },
  "devDependencies": {
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.2",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "typescript": "^5.6.2",
    "vite": "^5.4.8"
  }
}
```

---

## 5. Data Models — Exact Schemas

These models are the contract between layers. Every module imports from `core/models.py`.

### `core/models.py` — minimum required types

```python
from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


# ============================================================
# IDENTITY (Layer A — RootID)
# ============================================================

class DIDDocument(BaseModel):
    id: str = Field(..., pattern=r"^did:knx:[a-zA-Z0-9_:.-]+$")
    public_key_hex: str  # Ed25519 public key
    auth_key_hex: str
    capabilities: list[str]  # e.g. ["camera", "imu", "lidar"]
    created_at: datetime


class SensorChannel(str, Enum):
    CAMERA = "camera"
    IMU = "imu"
    LIDAR = "lidar"
    GPS = "gps"
    TORQUE = "torque"
    THERMAL = "thermal"


class SensorPacket(BaseModel):
    """A single sensor reading, signed at capture time."""
    job_id: str          # SHA-3 hash from TaskRegistry
    robot_did: str       # did:knx:...
    channel: SensorChannel
    timestamp_ns: int    # nanosecond precision, monotonic
    nonce: int           # monotonic per (job_id, channel)
    data_b64: str        # base64-encoded raw sensor data
    signature_hex: str   # Ed25519 signature over canonical bytes


# ============================================================
# BUNDLE (Layer A → Layer B)
# ============================================================

class PolicyTrace(BaseModel):
    """The action sequence the robot's policy produced."""
    actions: list[dict]
    seed: int            # for deterministic replay
    policy_hash: str     # SHA-3 of policy WASM


class PoPWBundle(BaseModel):
    """The artefact validated by DetVerify."""
    job_id: str
    robot_did: str
    task_prompt: str
    policy_trace: PolicyTrace
    sensor_packets: list[SensorPacket]
    bundle_merkle_root: str   # SHA-3 root over packets
    submitted_at: datetime


# ============================================================
# SCORING (Layer B output, Konnex-compatible schema)
# ============================================================

Verdict = Literal["success", "failure", "inconclusive"]


class ScoreVector(BaseModel):
    """Mirrors Konnex AI Verifier schema exactly.
    Source: https://docs.konnex.world/supported-ai-models/verifier"""
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
    name: str
    passed: bool
    detail: str
    severity: Literal["info", "warning", "fail"] = "info"


class DetVerifyResult(BaseModel):
    """KonnexCore extension to ScoreVector — keeps base compat."""
    score: ScoreVector
    stage_results: list[StageResult]
    deterministic_only: bool
    llm_comparison: ScoreVector | None = None
    layers_agree: bool | None = None  # vs LLM tier per metascore Layer 3


# ============================================================
# HONEYNET (Layer C)
# ============================================================

class Subnet(str, Enum):
    DRONE = "drone-navigation"
    ROBOARM = "roboarm-vla"
    SLAM = "slam-3d-map"


class HoneypotTask(BaseModel):
    """A task with hidden ground truth, indistinguishable from organic."""
    job_id: str
    subnet: Subnet
    prompt: str
    deadline_s: int
    reward_test_knx: float
    is_honeypot: Literal[True] = True   # only known to oracle
    ground_truth_score: ScoreVector     # secret answer key
    ground_truth_hash: str              # commitment posted onchain


class ValidatorVote(BaseModel):
    validator_did: str
    job_id: str
    score: ScoreVector
    submitted_at: datetime


class ValidatorMetascore(BaseModel):
    """Implements S(V_i) = α·C + β·H − γ·P.
    Source: https://docs.konnex.world/understand-konnex/validator-metascore"""
    validator_did: str
    consensus_term: float          # C(W_i, W̄), 0..1
    honeypot_accuracy: float       # H(V_i), 0..1
    penalty_score: float           # P_i, 0..1
    alpha: float = 0.5
    beta: float = 0.4
    gamma: float = 0.1
    metascore: float               # final S(V_i)
    sample_count: int              # for confidence
```

**Rules for using these models:**
- Every API endpoint accepts/returns these types
- Every test asserts schema validity
- Never use raw dicts in module boundaries — always Pydantic models
- `ScoreVector` is the ONLY Konnex-compatible output format; do not invent fields outside `DetVerifyResult.stage_results`

---

## 6. Core Modules — Implementation Spec

### 6.1 `core/crypto.py`

```python
"""Ed25519 signing, SHA-3 hashing, Merkle roots.
All crypto is deterministic and standards-compliant."""

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey
)
from cryptography.hazmat.primitives import serialization
import hashlib

def generate_keypair() -> tuple[bytes, bytes]:
    """Returns (private_bytes_32, public_bytes_32)."""
    ...

def sign(private_bytes: bytes, message: bytes) -> bytes:
    """Returns 64-byte signature."""
    ...

def verify(public_bytes: bytes, message: bytes, signature: bytes) -> bool:
    """True iff signature is valid."""
    ...

def sha3_256(data: bytes) -> bytes:
    """Konnex protocol uses SHA-3 (per their protocol arch doc)."""
    return hashlib.sha3_256(data).digest()

def merkle_root(leaves: list[bytes]) -> bytes:
    """Standard binary Merkle, SHA-3-256."""
    ...
```

**Implementation rules:**
- Use `cryptography` library, not custom crypto
- All hashes are SHA-3 (matches their protocol arch quote: "Every packet's SHA-3 hash becomes its immutable JobID")
- Merkle root must be deterministic and tested against known vectors

### 6.2 `rootid/tee_simulator.py`

```python
"""Software simulation of a TEE (ARM TrustZone / Secure Enclave style).
Production swap-in uses ARM PSA Crypto API or Apple Secure Enclave Framework."""

class TEESimulator:
    """Isolated key store. Private keys never leave .sign()."""

    def __init__(self, robot_did: str):
        self._private_bytes, self.public_bytes = generate_keypair()
        self._robot_did = robot_did
        self._monotonic_counter: dict[tuple[str, str], int] = {}

    def sign_sensor_packet(
        self,
        job_id: str,
        channel: SensorChannel,
        timestamp_ns: int,
        data: bytes,
    ) -> SensorPacket:
        """Atomic sign: increments nonce, signs canonical bytes, returns packet."""
        ...

    def attest(self) -> dict:
        """Returns attestation report (mocks ARM PSA attestation token)."""
        ...
```

**Implementation rules:**
- Private key is `_private_bytes` with leading underscore — never logged, never returned
- Nonce is monotonic per `(job_id, channel)` — enforced at signing time
- Canonical signing bytes: `sha3_256(job_id || channel || timestamp_ns || nonce || data)`
- Document in module docstring: "PRODUCTION: replace with hardware TEE bindings"

### 6.3 `detverify/pipeline.py`

```python
"""Six-stage deterministic verifier.
Orchestrates stages 1-6, emits ScoreVector compatible with Konnex AI Verifier schema."""

class DetVerifyPipeline:
    def __init__(
        self,
        identity_registry: IdentityRegistry,
        anomaly_model: AnomalyModel,
        kinematic_constraints: KinematicSpec,
    ):
        ...

    def verify(self, bundle: PoPWBundle) -> DetVerifyResult:
        results: list[StageResult] = []

        # Stage 1: Signature verification
        sig_result = self._stage1_signature(bundle)
        results.append(sig_result)
        if sig_result.severity == "fail":
            return self._fail(bundle, results, "signature failure")

        # Stages 2-6 each return StageResult
        results.append(self._stage2_temporal(bundle))
        results.append(self._stage3_crossmodal(bundle))
        results.append(self._stage4_replay(bundle))
        results.append(self._stage5_anomaly(bundle))
        results.append(self._stage6_kinematic(bundle))

        score = self._compose_score(results, bundle)
        return DetVerifyResult(
            score=score,
            stage_results=results,
            deterministic_only=True,
        )
```

**Stage implementation rules:**
- Each stage is a separate file in `detverify/stages/`
- Each stage returns a `StageResult`, never raises
- `severity="fail"` short-circuits the pipeline (except stage 1, which always short-circuits)
- All stages must be deterministic — same input → same output, every time
- No network calls in any stage

### 6.4 `honeynet/oracle.py`

```python
"""Compares validator votes against honeypot ground truth.
Updates per-validator H(V_i) accuracy and the full S(V_i) metascore."""

class HoneynetOracle:
    def __init__(self, alpha: float = 0.5, beta: float = 0.4, gamma: float = 0.1):
        self._honeypots: dict[str, HoneypotTask] = {}
        self._votes: dict[str, list[ValidatorVote]] = {}
        # ...

    def register_honeypot(self, task: HoneypotTask) -> None: ...

    def submit_vote(self, vote: ValidatorVote) -> None: ...

    def compute_metascore(self, validator_did: str) -> ValidatorMetascore:
        """Implements S(V_i) = α·C + β·H − γ·P."""
        ...
```

**Implementation rules:**
- Score-vector comparison uses cosine similarity per the metascore design
- Severity tiers for divergence are governance-tunable (config in `core/config.py`)
- Validator simulator (`honeynet/validator_pool.py`) must include 5 archetypes:
  - `HonestValidator` — runs full DetVerify
  - `LazyValidator` — copies median of others
  - `StakePumpValidator` — always votes "success" with high score
  - `CollusionPair` — two validators with identical votes
  - `RandomValidator` — uniform random scores

---

## 7. HTTP API Contract

**Base URL:** `http://37.120.175.12:8000` (dev) or `https://yourdomain.xyz` (prod)

**Auto-generated docs:** `/docs` (FastAPI Swagger UI)

### Endpoints

```
GET    /api/health                          → {"status": "ok", "version": "0.1.0"}

# RootID (Layer A)
POST   /api/identity/create                 → DIDDocument
GET    /api/identity/{did}                  → DIDDocument
POST   /api/identity/sign-bundle            → PoPWBundle (with signed packets)
POST   /api/identity/verify-packet          → {"valid": bool, "reason": str}

# DetVerify (Layer B)
POST   /api/verify                          → DetVerifyResult
POST   /api/verify/with-llm-compare         → DetVerifyResult (includes LLM tier)

# Honeynet (Layer C)
POST   /api/honeypot/generate               → HoneypotTask
POST   /api/honeypot/submit-vote            → {"recorded": True}
GET    /api/honeypot/metascore/{validator}  → ValidatorMetascore
GET    /api/honeypot/leaderboard            → list[ValidatorMetascore]

# Attack Lab (test harness for demo)
POST   /api/attack/generate/{type}          → PoPWBundle (adversarial)
                                              type ∈ {deepfake, replay, gps_spoof,
                                                      frame_skip, torque_mismatch}

# Demo (preset flows)
POST   /api/demo/full-stack                 → DemoRunResult (all 3 layers)
GET    /api/demo/scenarios                  → list[DemoScenario]
```

**Contract rules:**
- All requests/responses are JSON validated by Pydantic
- Errors return `{"error": str, "detail": dict, "stage": str}` with appropriate HTTP code
- CORS allows the dashboard origin
- Logging at INFO level for all requests, DEBUG for stage internals

---

## 8. Frontend Spec

### Pages

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | `Home.tsx` | Hero, 3 layer cards, "Try Live Demo" CTA |
| `/demo` | `FullStackDemo.tsx` | The 60-second demo (combined flow) |
| `/detverify` | `DetVerifyDemo.tsx` | Layer B alone — adversarial vs GPT-4o |
| `/rootid` | `RootIDDemo.tsx` | Layer A alone — signed vs synthetic |
| `/honeynet` | `HoneynetDemo.tsx` | Layer C alone — validator metascore chart |
| `/docs` | external link | Links to `/docs` API + GitHub |

### Design system

- **Font:** Inter (free Google Fonts) or system stack
- **Colors:** dark mode by default; primary `#5b8cff`, success `#2dd4bf`, danger `#ef4444`
- **Style:** Tailwind utility classes; no custom CSS files except `globals.css`
- **Components:** keep flat — no `shadcn/ui` to avoid version drift; just well-styled native HTML
- **Charts:** `recharts` (declarative, lightweight)
- **Icons:** `lucide-react`

### `FullStackDemo.tsx` — the killer demo (spec)

Three-section vertical layout:

1. **Section 1 — RootID** (top)
   - Two robot cards side-by-side
   - "Robot A (RootID-attested)" — green checkmarks per signed packet
   - "Robot B (Synthetic adversary)" — red X marks
   - Click "Submit both bundles to validator"

2. **Section 2 — DetVerify** (middle)
   - Six stage indicators (signature, temporal, cross-modal, replay, anomaly, kinematic)
   - Robot A passes all stages (green)
   - Robot B fails at stage 1 (signature) — pipeline stops
   - Side panel: GPT-4o reference verdict ("success" — fooled by Robot B)
   - Caption: "Layer 3 deterministic check catches what GPT-4o misses"

3. **Section 3 — Honeynet** (bottom)
   - Live chart with 5 validator lines over time
   - 100 organic + 10 honeypot tasks streamed over 30 seconds
   - Honest validator's metascore stays high
   - Lazy/colluding/random validators visibly drop
   - Final leaderboard appears at the end

**Total demo runtime:** 60 seconds. User just clicks "Run Demo" once.

---

## 9. Build Order — Phase-by-Phase

**Build in this exact order. Do not skip ahead. Each phase is shippable on its own.**

### Phase 0 — Foundation (do this first, no exceptions)

1. Init Git repo, create folders per Section 3
2. Write `core/models.py` with all Pydantic schemas from Section 5
3. Write `core/crypto.py` with Ed25519 + SHA-3 + Merkle
4. Write tests for `core/crypto.py` first (test vectors)
5. CI: GitHub Actions running `pytest` + `ruff` + `mypy`

**Done when:** `pytest core/` is green.

### Phase 1 — RootID (Layer A)

1. `rootid/did.py` — DID document creation, parsing
2. `rootid/tee_simulator.py` — TEESimulator class
3. `rootid/sensor_signer.py` — uses TEE to produce SensorPacket
4. `rootid/verifier.py` — checks signature, freshness, JobID binding
5. `rootid/registry.py` — mock RobotIdentity registry
6. Tests for each
7. `examples/01_sign_sensor.py` — runnable hello-world

**Done when:** `examples/01_sign_sensor.py` runs and a manual curl to `/api/identity/sign-bundle` returns a signed bundle.

### Phase 2 — Core Sim Engine

1. `core/sim_engine.py` — PyBullet wrapper for deterministic kitchen scene
2. Implement one scenario: roboarm picks apple from pan
3. Generate synthetic sensor streams (camera, IMU, torque)
4. Sign sensor packets via RootID
5. Output complete `PoPWBundle`

**Done when:** `python -m core.sim_engine` produces `bundle.json` ready for verification.

### Phase 3 — DetVerify (Layer B)

1. `detverify/stages/stage1_signature.py` (uses RootID verifier)
2. `detverify/stages/stage2_temporal.py`
3. `detverify/stages/stage3_crossmodal.py` (with EKF in `detverify/fusion.py`)
4. `detverify/stages/stage4_replay.py`
5. `detverify/stages/stage5_anomaly.py` (Isolation Forest, fit on synthetic baseline)
6. `detverify/stages/stage6_kinematic.py`
7. `detverify/pipeline.py` orchestrator
8. `detverify/score_emitter.py` — emits Konnex-schema ScoreVector
9. `detverify/llm_compare.py` — optional GPT-4o comparison
10. Tests per stage + integration test
11. `examples/02_verify_bundle.py`

**Done when:** A clean bundle scores ≥80, an adversarial bundle scores ≤30 with clear stage failure.

### Phase 4 — Attack Lab

1. `core/attack_lab.py` with 5 generators:
   - `make_deepfake_video_bundle()`
   - `make_replayed_imu_bundle()`
   - `make_gps_spoof_bundle()`
   - `make_frame_skip_bundle()`
   - `make_torque_mismatch_bundle()`
2. Each returns a `PoPWBundle` that fools naive verifiers
3. Test that DetVerify catches each one

**Done when:** All 5 attacks pass GPT-4o reference but fail DetVerify with specific stage names.

### Phase 5 — Honeynet (Layer C)

1. `honeynet/generators/roboarm_gen.py` (start with this only)
2. `honeynet/injector.py` — indistinguishability layer
3. `honeynet/oracle.py` — comparison engine
4. `honeynet/validator_pool.py` — 5 archetypes
5. `honeynet/metascore.py` — S(V_i) formula
6. Add drone + SLAM generators
7. `examples/03_honeypot_demo.py`

**Done when:** Running 100 organic + 10 honeypot tasks separates honest from lazy validators by ≥0.3 metascore points.

### Phase 6 — FastAPI Backend

1. `api/main.py` — FastAPI app, CORS, OpenAPI tags
2. Routes per Section 7
3. Middleware (logging, error handler)
4. `uvicorn api.main:app --host 0.0.0.0 --port 8000`
5. Hit `/docs` and confirm all endpoints

**Done when:** All endpoints documented, all return correct Pydantic shapes.

### Phase 7 — Dashboard (React + Vite + Tailwind)

1. `pnpm create vite@latest dashboard --template react-ts`
2. Install deps from Section 4
3. Configure Tailwind
4. `src/api/client.ts` — typed wrappers around backend
5. Build `Home.tsx` first
6. Build `DetVerifyDemo.tsx` (single layer, simplest)
7. Build `RootIDDemo.tsx`
8. Build `HoneynetDemo.tsx`
9. Build `FullStackDemo.tsx` last (combines all three)

**Done when:** All demos run end-to-end with no console errors and look polished.

### Phase 8 — VPS Deployment

1. `scripts/setup_vps.sh` (idempotent)
2. Build dashboard: `pnpm build` → `dashboard/dist/`
3. Configure Nginx to serve `dist/` on port 80, reverse proxy `/api/*` to `localhost:8000`
4. Run backend with `systemd` service (auto-restart)
5. Optional: Cloudflare Tunnel or Let's Encrypt SSL

**Done when:** `https://yourdomain.xyz` shows working demo from any browser.

### Phase 9 — Polish & Submission

1. Record 60-second demo video (Section 12)
2. Fill `docs/APPLICATION.md` (Section 13)
3. Push final commits to public GitHub
4. Submit application form at `https://subnets.testnet.konnex.world/builders`

---

## 10. Testing Requirements

### Coverage targets
- Overall: ≥85%
- `core/crypto.py`: 100% (security-critical)
- `rootid/`: 95%
- `detverify/stages/`: 95%
- `honeynet/oracle.py`: 95%

### Test types

| Type | Where | What |
|------|-------|------|
| Unit | `*/tests/test_*.py` | Each function, edge cases |
| Property | `tests/property/` | Hypothesis-based for crypto round-trips |
| Integration | `tests/integration/` | Full pipeline end-to-end |
| Adversarial | `tests/adversarial/` | All 5 attack types must fail DetVerify |
| Schema | `tests/schema/` | API responses validate against Pydantic models |

### Test commands

```bash
make test              # all tests
make test-fast         # skip slow integration tests
make test-coverage     # with HTML coverage report
make lint              # ruff + mypy
make format            # black + ruff --fix
```

### CI requirements (`.github/workflows/ci.yml`)

- Runs on every push + PR
- Matrix: Python 3.10, 3.11, 3.12 (we develop on 3.11)
- Steps: install → lint → typecheck → test → coverage
- Fails build on any error

---

## 11. VPS Deployment

### One-shot setup (`scripts/setup_vps.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

# System packages
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-dev \
    build-essential pkg-config nginx ufw curl git

# Firewall
sudo ufw allow OpenSSH 80/tcp 443/tcp 8000/tcp 5173/tcp
sudo ufw --force enable

# Project setup
mkdir -p ~/konnexcore && cd ~/konnexcore
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Build dashboard
cd dashboard
pnpm install
pnpm build
cd ..

# Nginx config
sudo cp scripts/nginx.conf /etc/nginx/sites-available/konnexcore
sudo ln -sf /etc/nginx/sites-available/konnexcore /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Systemd service
sudo cp scripts/konnexcore.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now konnexcore
```

### `scripts/nginx.conf`

```nginx
server {
    listen 80;
    server_name 37.120.175.12;  # or your domain

    location / {
        root /home/kiro3/konnexcore/dashboard/dist;
        try_files $uri /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
    }
}
```

### `scripts/konnexcore.service`

```ini
[Unit]
Description=KonnexCore FastAPI backend
After=network.target

[Service]
Type=simple
User=kiro3
WorkingDirectory=/home/kiro3/konnexcore
Environment="PATH=/home/kiro3/konnexcore/venv/bin:/usr/bin"
ExecStart=/home/kiro3/konnexcore/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### Health check
```bash
curl http://127.0.0.1:8000/api/health
# Expected: {"status":"ok","version":"0.1.0"}
```

---

## 12. Demo Recording Plan

### Tools
- **OBS Studio** (free, cross-platform)
- 1080p, 30 fps, MP4 output
- Browser zoom 110% for readability

### Script (60 seconds total)

```
[00:00–00:05]  Title card
   "KonnexCore — the validator stack Konnex specced."

[00:05–00:15]  Problem
   Show docs page: https://docs.konnex.world/supported-ai-models/verifier
   Highlight the GPT-4o reference code.
   Voice: "Konnex's reference verifier is GPT-4o on 6 frames. We built the missing layers."

[00:15–00:25]  Layer A — RootID
   Open /rootid demo page.
   Click "Sign bundle". Show signature appearing on each sensor packet.
   Voice: "Each sensor packet is signed at capture by a TEE-simulated key."

[00:25–00:40]  Layer B — DetVerify
   Open /detverify demo page.
   Click "Generate adversarial bundle".
   GPT-4o passes it (left panel: green ✓).
   DetVerify catches it (right panel: stage 1 fails red ✗).
   Voice: "Same bundle. Their LLM verifier passes. Our deterministic Layer 3 catches it."

[00:40–00:55]  Layer C — Honeynet
   Open /honeynet demo page.
   Click "Run honeypot oracle".
   Watch 5 validators' metascore over 15 seconds.
   Honest validator stays at top; lazy/colluding fall.
   Voice: "Honeypots inject reference tasks. Bad validators reveal themselves."

[00:55–01:00]  Close
   "KonnexCore. Open-source. github.com/your-handle/konnexcore."
```

### Hosting the video
- Upload to YouTube as **unlisted**
- Drop URL into application form `Demo link` field

---

## 13. Builder Application Submission

### Pre-fill `docs/APPLICATION.md` with this content

```markdown
## Project / team name
KonnexCore

## Your name
[Your real name]

## Role
Founder / Tech lead

## Work email
[Your email]

## Twitter / X
@yourhandle

## GitHub / portfolio
https://github.com/yourhandle/konnexcore

## One-line pitch
KonnexCore: TEE-attested sensor capture + deterministic Layer-3 verifier + honeypot oracle. The validator stack Konnex specced.

## What subnet are you building and why Konnex?
KonnexCore is the validator infrastructure stack Konnex's docs spec but doesn't yet ship as public reference code:

1. RootID (Layer A) — implements the off-chain attestation pipeline that anchors the RobotIdentity contract to TEE-signed sensor telemetry. Software-simulated TEE today; production binds to ARM PSA Crypto API.

2. DetVerify (Layer B) — implements Layer 3 of the validator metascore (deterministic tier). Six closed-form checks that catch adversarial bundles which fool the GPT-4o reference verifier.

3. Honeynet (Layer C) — implements Layer 2 of the validator metascore (honeypot generation). Indistinguishable reference tasks that compute H(V_i) per validator and surface lazy/colluding behavior.

Why Konnex: the 15M strategic round, doxxed robotics-industry founders (Ollwerther, Declet, Van Oostrum), and a public spec that explicitly leaves these layers to the builder ecosystem make this the right project to ship reference code for. Konnex needs deterministic verification primitives that don't depend on per-call LLM costs, and honeypot infrastructure to score the validators that score miners.

## Subnet category
Sensor fusion & PoPW validation
(also touches: Robot Identity and Memory; cross-cutting validator infrastructure)

## Stage
Working demo

## Demo link
https://[your-domain].xyz
(Backup video: https://youtu.be/[unlisted-id])

## Team size & key members
Solo founder: [your name]. [1-2 sentences on background.]

## Optional: grant ask & funding history
Grant ask: Spark ($25,000) — milestones tied to:
- Public GitHub repo with MIT license (delivered at submission)
- Live demo URL with full 3-layer flow (delivered at submission)
- Integration with Konnex SDK once their public repo is available
- Documentation on protocol-architecture mapping (delivered at submission)
- Funding history: none.
```

### Submission checklist
- [ ] GitHub repo public, MIT license, README with demo URL
- [ ] Live demo URL works (test from incognito browser, not your dev session)
- [ ] Demo video uploaded (unlisted YouTube)
- [ ] All 3 layers function end-to-end
- [ ] CI passing on `main` branch
- [ ] No secrets / API keys in repo
- [ ] `docs/APPLICATION.md` finalized

---

## 14. Quality Gates — No Slop Allowed

**Every PR must pass these checks before merge:**

### Code quality gates
- [ ] `ruff check .` passes (0 errors)
- [ ] `mypy --strict` on `core/`, `rootid/`, `detverify/`, `honeynet/`
- [ ] `pytest` ≥85% coverage
- [ ] No `TODO` / `FIXME` / `XXX` comments in code merged to `main`
- [ ] No `print()` statements (use `logging`)
- [ ] No commented-out code

### Functional gates
- [ ] Every public function has a docstring
- [ ] Every Pydantic model has field descriptions
- [ ] Every API endpoint has a tag and summary in OpenAPI
- [ ] All 5 adversarial bundles fail DetVerify with named stage
- [ ] All 5 validator archetypes produce distinguishable metascores

### UI gates
- [ ] No console errors in any demo flow
- [ ] Mobile-responsive (test at 375px width)
- [ ] All buttons have loading states
- [ ] Errors show user-friendly messages, not raw stack traces
- [ ] No Lighthouse score under 90 on Performance/Accessibility

### Documentation gates
- [ ] README has working "Run locally in 60 seconds" section
- [ ] Architecture diagram in `docs/ARCHITECTURE.md`
- [ ] Each module has a top-level docstring explaining its role
- [ ] Examples in `examples/` actually run with current code

---

## 15. Konnex Documentation Map

**Every claim about Konnex in this spec is grounded in one of these URLs. If you find yourself making a claim not on this list, stop and verify.**

### Primary specs (must-read before building)
- Builder program & RFP: https://subnets.testnet.konnex.world/builders
- Design overview: https://docs.konnex.world/understand-konnex/design-overview
- Protocol architecture: https://docs.konnex.world/understand-konnex/protocol-architecture
- Proof-of-Physical-Work, TEE, contracts: https://docs.konnex.world/understand-konnex/contracts-and-popw
- Validator metascore (design): https://docs.konnex.world/understand-konnex/validator-metascore
- AI ecosystem: https://docs.konnex.world/understand-konnex/ai-ecosystem
- Roadmap: https://docs.konnex.world/understand-konnex/roadmap

### SDK references (mirror their interfaces)
- SDK overview: https://docs.konnex.world/sdk/sdk
- CLI: https://docs.konnex.world/sdk/cli
- Python SDK: https://docs.konnex.world/sdk/python
- HTTP API: https://docs.konnex.world/sdk/http
- Connecting Robots: https://docs.konnex.world/sdk/robots
- Validators SDK: https://docs.konnex.world/sdk/validators

### Subnets & workload classes
- Subnets overview: https://docs.konnex.world/subnets-workload-classes/subnets
- Drone navigation: https://docs.konnex.world/subnets-workload-classes/drone-navigation
- Roboarm VLA: https://docs.konnex.world/subnets-workload-classes/roboarm-vla
- SLAM 3D map: https://docs.konnex.world/subnets-workload-classes/slam-3d-map

### Supported AI models
- AI overview: https://docs.konnex.world/supported-ai-models/ai
- AI Verifier (the reference we extend): https://docs.konnex.world/supported-ai-models/verifier
- AI Fetch Interface: https://docs.konnex.world/supported-ai-models/fetch_interface

### Participate
- Mining: https://docs.konnex.world/participate/mining
- Validating: https://docs.konnex.world/participate/validating
- Wallet: https://docs.konnex.world/participate/wallet

### Testnet surface
- Quest: https://subnets.testnet.konnex.world/quest
- Faucet: (linked from quest)
- Explorer: https://subnets.testnet.konnex.world/explorer

### External (legitimacy & due diligence)
- SiliconANGLE — $15M raise: https://siliconangle.com/2026/01/15/konnex-nabs-15m-decentralize-autonomous-robotic-labor/
- The Robot Report — team: https://www.therobotreport.com/konnex-raises-funding-advance-robotics-as-a-service-offering/
- The Defiant: https://thedefiant.io/news/markets/konnexs-15m-funding-towards-autonomous-robotics-will-boost-the-25-trillion-physical-labor-economy
- Twitter/X: https://x.com/konnex_world

### Standards we follow
- W3C DID Core: https://www.w3.org/TR/did-core/
- Ed25519 RFC 8032: https://datatracker.ietf.org/doc/html/rfc8032
- ARM PSA Crypto API: https://arm-software.github.io/psa-api/crypto/

### Known broken (do not link to these in our app/docs)
- ❌ https://github.com/konnex-network — 404
- ❌ https://github.com/konnex-world/konnex — 404
- ❌ https://konnex.world/whitepaper — 404 at time of research

---

## 16. Common Mistakes to Avoid

**Read this before writing any code.**

### Architecture mistakes
- ❌ Putting all logic in one file. → ✅ Strict layer separation per Section 3.
- ❌ Coupling layers (e.g. DetVerify imports Honeynet internals). → ✅ Layers communicate only via `core/models.py` types.
- ❌ Hand-rolling crypto. → ✅ Use `cryptography` library exclusively.
- ❌ Inventing fields in `ScoreVector`. → ✅ Match Konnex AI Verifier schema exactly; extensions go in `DetVerifyResult.stage_results`.

### Crypto mistakes
- ❌ Using SHA-256 instead of SHA-3. → ✅ Konnex spec says SHA-3; we follow that.
- ❌ Reusing nonces across `(job_id, channel)`. → ✅ Monotonic counter per pair, enforced in TEE simulator.
- ❌ Returning private keys from any function. → ✅ Private keys never leave `TEESimulator._sign()`.
- ❌ Logging signed bytes or signatures in INFO/DEBUG. → ✅ Crypto logged at TRACE level only.

### API mistakes
- ❌ Returning raw dicts from endpoints. → ✅ Always Pydantic response models.
- ❌ CORS open to `*`. → ✅ Allow only the dashboard origin in prod.
- ❌ No rate limiting. → ✅ Add `slowapi` for `/api/verify/*` endpoints.
- ❌ Returning stack traces in 500 responses. → ✅ Generic message + log internally.

### Frontend mistakes
- ❌ Calling backend from `useEffect` without abort controllers. → ✅ Always abort on unmount.
- ❌ No loading states. → ✅ Skeleton/spinner for every async action.
- ❌ Hard-coded backend URL. → ✅ Read from `import.meta.env.VITE_API_URL`.
- ❌ Storing sensitive data in localStorage. → ✅ No secrets in frontend at all.

### Application form mistakes
- ❌ Pitch over 140 chars. → ✅ Count carefully; the form enforces it.
- ❌ Demo link broken when reviewers visit. → ✅ Test from incognito; set up uptime ping.
- ❌ GitHub repo private. → ✅ Public, MIT license, with clear README.
- ❌ Claiming features that aren't implemented. → ✅ Only claim what runs in the demo video.

### Demo recording mistakes
- ❌ Demo runs differently than what's in video. → ✅ Re-record after final code changes.
- ❌ Demo requires user to know context. → ✅ Voiceover or captions explain everything.
- ❌ 5+ minute video. → ✅ 60 seconds, hard cap.
- ❌ Background noise / unclear audio. → ✅ Use a decent mic, edit silence out.

### Konnex-specific mistakes
- ❌ Linking to broken GitHub URLs in our docs. → ✅ Use only verified URLs from Section 15.
- ❌ Quoting FDV / token price in the application. → ✅ Speculative; do not include.
- ❌ Saying "we replace Konnex's verifier". → ✅ "We add Layer 3 deterministic tier alongside their LLM tier" — collaborative framing.
- ❌ Pretending we have hardware TEE. → ✅ Always frame as "software-simulated TEE; production binds to ARM PSA / Apple Secure Enclave".

---

## End of Spec

If you've read to here, the build is well-defined. Start at **Phase 0 — Foundation** in Section 9 and execute sequentially. Every later phase depends on earlier ones being shipped clean.

Quality > speed. No slop. Match the spec or update the spec — never let code drift undocumented.

**Ship it.**
