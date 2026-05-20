# Idea #3 — RootID: Hardware-Rooted Identity & Attestation Layer for Konnex

> **One-line pitch (140 chars):** RootID is the off-chain attestation pipeline that anchors Konnex's RobotIdentity contract to TEE-signed sensor telemetry.

---

## The Gap (Verified, Not Guessed)

Konnex's protocol has a smart contract called `RobotIdentity` and explicitly requires hardware-rooted attestation — but the off-chain signing pipeline that connects them is not in any published code.

### Source 1 — Their Smart Contract Registry
`https://docs.konnex.world/understand-konnex/protocol-architecture`

> **Registry & Smart Contracts**
> - **RobotIdentity** — hardware-secured keys and on-chain trust.
> - TaskRegistry — stablecoin escrow, deadlines, penalties, fee-split logic.
> - StakeVault — dual staking (KNX + stablecoins) for validators/executors.
> - BondMatrix — stablecoin bonds from third-party stakers.
> - PayoutRouter — atomic stablecoin releases after validation.
>
> Every packet's SHA-3 hash becomes its immutable JobID.

### Source 2 — Their PoPW Spec
`https://docs.konnex.world/understand-konnex/contracts-and-popw`

> **Hardware-rooted provenance (TEE / secure elements)**
>
> If the bits are fake, off-device verification does not help. The first line of defense is on the device: **trusted execution environments and secure elements sign telemetry and media at capture time**. Validators check signatures, freshness, and binding to the task so that synthetic or replayed streams fail verification.

### Source 3 — Mining Requirements
`https://docs.konnex.world/participate/mining`

> **Evidence** — Sensor bundles and traces that meet PoPW requirements (**including hardware attestation where applicable**).

**The gap:** They define `RobotIdentity` as a contract, mandate hardware-signed telemetry, and require it for PoPW — but the **off-chain pipeline that produces signed sensor packets and binds them to onchain identity does not exist as published code**.

This is not invented. It's the missing infrastructure layer between their smart contract registry and actual sensor capture.

---

## Why This Wins the Spark Grant

| Builder requirement | How RootID hits it |
|---|---|
| "Working prototype, not slideware" | TEE simulation + signed packet pipeline running on testnet |
| "Team with ML / robotics / distributed systems background" | Crypto + DID + secure element design — strong distributed systems signal |
| "Commitment to ship on Konnex" | Implements RobotIdentity spec directly |
| "Open-source contributions — strong plus" | First public Konnex attestation reference |

**RFP category match (exact text):** "Robot Identity and Memory"

This is the only listed RFP category whose name explicitly maps to identity. RootID nails it.

---

## What We Build

### Core: Three-Layer Attestation Pipeline

```
[Sensor Capture Layer] → [TEE Signing Layer] → [Onchain Anchor Layer]
        │                         │                        │
   Raw IMU/cam data         Ed25519 signature         RobotIdentity DID +
                            with timestamp +          ScoreRoot binding
                            JobID nonce
```

### Layer 1 — DID Method `did:knx:`

W3C-compliant decentralized identifier method for robots:

```
did:knx:<chain-id>:<robot-public-key-hash>
```

DID Document includes:
- Hardware key (Ed25519 public key from simulated TEE)
- Authentication keys (separate signing key for higher-level commands)
- Service endpoints (where to fetch the robot's policy bundle)
- Capability claims (sensor types, certifications, manufacturer)

DID resolver implementation that reads from `RobotIdentity` registry contract (or our local mock for the demo).

### Layer 2 — Simulated TEE Signing

We simulate ARM TrustZone / Apple Secure Enclave behavior in software:

- **Hardware key generation:** Ed25519 keypair generated inside isolated process; private key never exits the "secure boundary"
- **Sensor packet signing:** Every sensor frame signed at capture time with `(timestamp, JobID, nonce, sensor_data_hash)`
- **Freshness binding:** Each signature includes the JobID issued by `TaskRegistry` and a monotonic counter
- **Replay protection:** Validators reject signatures with stale timestamps or repeated nonces

Production version replaces our software simulation with actual ARM PSA Crypto API or Apple Secure Enclave Framework — same interfaces.

### Layer 3 — Onchain Anchor

Each completed job emits an onchain commitment:
- `JobID` (from TaskRegistry)
- Robot DID
- Sensor bundle Merkle root
- Validator ScoreRoot (per Konnex spec)

Contract interface mirrors their existing `RobotIdentity` + `TaskRegistry` shape from the protocol arch doc.

### Killer Demo: Spoof Resistance

Web dashboard showing two robots completing the same drone navigation task:

- **Robot A (RootID-attested):**
  - Each sensor packet signed at capture
  - Validator chain shows: signature valid → JobID match → freshness OK → bundle accepted
  - PoPW record fully provenance-anchored

- **Robot B (Synthetic adversary):**
  - Sensor packets generated post-hoc to look successful
  - Validator chain shows: signature missing/invalid → REJECTED at signature stage
  - Even if Robot B's video looks identical, the bundle fails attestation

User can also click "Simulate replay attack" — replay an old bundle from Robot A. Validator catches it via nonce/timestamp freshness.

---

## Tech Stack (All Open-Source, All Free)

| Component | Library | Purpose |
|---|---|---|
| Crypto primitives | `cryptography` (Ed25519) | TEE simulation |
| DID library | `did:knx:` custom + `did-method-key` reference | Identity resolution |
| Hash/Merkle | `hashlib` (SHA-3 per their spec) + custom Merkle | Sensor bundle anchoring |
| Backend | `fastapi` + `uvicorn` | HTTP API |
| Mock chain | In-memory contract simulator | RobotIdentity registry without needing testnet integration |
| Real testnet binding | `substrate-interface` Python lib | When integrating with their actual chain |
| Dashboard | React + Vite + Tailwind | Live attestation flow visualization |

---

## Konnex Documentation References (All Verified Working)

### Core spec we implement
- **Protocol architecture (RobotIdentity contract):** https://docs.konnex.world/understand-konnex/protocol-architecture
- **Proof-of-Physical-Work, TEE, contracts:** https://docs.konnex.world/understand-konnex/contracts-and-popw
- **Mining (hardware attestation requirement):** https://docs.konnex.world/participate/mining
- **Validator metascore (signature checks in Layer 3):** https://docs.konnex.world/understand-konnex/validator-metascore

### Integration points
- **Connecting Robots SDK** — sensor recording, bundle creation: https://docs.konnex.world/sdk/robots
- **Validators SDK:** https://docs.konnex.world/sdk/validators
- **Validating overview:** https://docs.konnex.world/participate/validating
- **AI Verifier (consumes our attested bundles):** https://docs.konnex.world/supported-ai-models/verifier

### Subnets (where attestation matters)
- **Subnets overview:** https://docs.konnex.world/subnets-workload-classes/subnets
- **Drone navigation:** https://docs.konnex.world/subnets-workload-classes/drone-navigation
- **Roboarm VLA:** https://docs.konnex.world/subnets-workload-classes/roboarm-vla
- **SLAM 3D map:** https://docs.konnex.world/subnets-workload-classes/slam-3d-map

### Protocol & roadmap
- **Design overview:** https://docs.konnex.world/understand-konnex/design-overview
- **Roadmap (mainnet contracts):** https://docs.konnex.world/understand-konnex/roadmap
- **AI ecosystem:** https://docs.konnex.world/understand-konnex/ai-ecosystem

### Builder program
- **Apply page:** https://subnets.testnet.konnex.world/builders
- **Testnet explorer:** https://subnets.testnet.konnex.world/explorer

### Their funding (legitimacy)
- **SiliconANGLE:** https://siliconangle.com/2026/01/15/konnex-nabs-15m-decentralize-autonomous-robotic-labor/
- **The Robot Report:** https://www.therobotreport.com/konnex-raises-funding-advance-robotics-as-a-service-offering/

### External standards we follow
- **W3C DID Core spec:** https://www.w3.org/TR/did-core/
- **DID method spec template:** https://www.w3.org/TR/did-spec-registries/
- **Ed25519 RFC:** https://datatracker.ietf.org/doc/html/rfc8032
- **ARM PSA Crypto API (real-world TEE target):** https://arm-software.github.io/psa-api/crypto/
- **OpenSSL Ed25519 docs:** https://www.openssl.org/docs/man3.0/man7/Ed25519.html

---

## Reality Check (Not Slop)

**Same GitHub 404 finding as Ideas 1 & 2:**
- `https://github.com/konnex-network` — 404
- `https://github.com/konnex-world/konnex` — 404

We build standalone, drop our public repo URL into the application form.

**Additional honest caveat for this idea:**
- Real TEE integration (ARM TrustZone, Apple Secure Enclave, Intel SGX) requires platform-specific work that no demo can finish in 2–3 weeks
- We **simulate** TEE behavior in software with the exact same crypto primitives and interfaces
- The application clearly states "TEE-simulated" — production hardening is roadmap material, not Spark-grant scope
- This is honest framing, not a weakness — Konnex's own docs treat TEE integration as Phase 1 mainnet work

---

## Comparison vs. Ideas #1 & #2

| Factor | #1 DetVerify | #2 Honeynet | #3 RootID |
|---|---|---|---|
| **Demo visual impact** | High | Medium | Medium-high |
| **RFP category fit** | Direct match | "Propose your own" | Direct match |
| **Code novelty** | High | Very high | Medium-high |
| **Crypto/distributed systems credibility signal** | Medium | Medium | **Highest** |
| **Solo-buildable in 2–3 weeks** | Yes | Yes | Yes (with software TEE simulation) |
| **Demo is "obvious" to non-technical reviewers** | Yes | Requires explanation | Yes (signed vs unsigned) |
| **Recurring mainnet revenue** | Per-validation fees | Per-honeypot fees | Per-attestation fees |
| **Risk of being out-of-scope for "Identity & Memory" RFP** | N/A | N/A | Low — we hit "Identity" perfectly, "Memory" partially |

---

## Optional Extension: Persistent Robot Memory

The RFP category is "Robot Identity **and Memory**". To fully cover both halves we add:

- **Memory store:** IPFS-anchored event log per robot (task history, attestation chain, reputation events)
- **Verifiable memory queries:** "Has this robot completed >10 successful drone deliveries?" returns Merkle proof
- **Cross-robot handoff:** Robot A passes mission state to Robot B with attestation chain intact

Cost: +1 week of build. Worth it for full RFP coverage.

---

## What We Do NOT Need

| Item | Why we skip it |
|---|---|
| Real TEE hardware | Software simulation with identical crypto interfaces — production swap-in is roadmap |
| Real robot hardware | Synthetic sensor streams demonstrate the attestation flow |
| Onchain testnet integration v1 | Mock contract simulator; real chain integration is Launch tier work |
| OpenAI API | Not used — pure crypto + protocol code |
| Their actual SDK | Mirror their schema from docs |

---

## Effort & Timeline

| Phase | Time | Output |
|---|---|---|
| **Week 1** | DID method, TEE simulator, sensor packet signing | Robot can sign and verify packets locally |
| **Week 2** | Mock RobotIdentity contract, JobID binding, freshness/nonce protection | End-to-end attested PoPW flow |
| **Week 3** | React dashboard, spoof-resistance demo, replay attack demo | Public demo URL on VPS |
| **Week 4 (buffer + memory extension)** | IPFS event log, cross-robot handoff, application polish | Submit |

**Total:** ~80–120 hours base, +30 hours for memory extension. ~3 weeks at full-time pace.

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Grant rejection | Medium-high | DID + TEE attestation code is reusable for any IoT/DePIN project |
| Reviewers expect real TEE not simulation | Low-medium | Frame clearly as "production-bound TEE interfaces" with software simulation; show ARM PSA mapping |
| Their existing internal team builds same thing | Low | They've published the spec for months without shipping; design ≠ implementation |
| W3C DID compliance not required by Konnex | Low | DID is industry standard; non-compliance would be a step backward |
| "Memory" half of RFP underdelivered | Medium without extension | Include IPFS memory extension for full RFP coverage |

---

## How This Becomes Mainnet ($200K+)

1. **Spark ($25K):** TEE-simulated attestation pipeline + DID method + spoof-resistance demo
2. **Launch ($75K):** Real testnet integration with their `RobotIdentity` contract, demo with multiple simulated robots, IPFS memory layer
3. **Mainnet ($200K+):** Production hardening — actual ARM PSA / Apple Secure Enclave bindings, governance-controlled DID resolver, ongoing attestation fees per packet

Like Idea #2, RootID has structural recurring revenue: every signed sensor packet pays a small fee to the attestation infrastructure.

---

## Final Honest Take

RootID is the **most credible distributed-systems / security signal** of the three. Pick this if:

- Your background skews toward crypto, security, or systems engineering rather than ML/robotics
- You want to hit a **listed RFP category by name** ("Robot Identity and Memory")
- You're willing to clearly frame software TEE simulation vs production TEE as roadmap

**Pick #1 (DetVerify) instead if** you want the most visually striking demo and the strongest "ML-meets-security" hybrid story.

**Pick #2 (Honeynet) instead if** you want the deepest protocol-design signal and the most novel build.

All three are real, all three are buildable solo on the VPS, all three target real gaps documented in Konnex's own published specs.
