# Idea #2 — Honeynet: Honeypot Generation Service for Konnex Validators

> **One-line pitch (140 chars):** Honeynet generates deterministic reference tasks Konnex specced for validator metascore — catches lazy & colluding validators in the act.

---

## The Gap (Verified, Not Guessed)

Konnex's validator metascore design has **three layers**. Layer 2 is honeypots.

Source: `https://docs.konnex.world/understand-konnex/validator-metascore`

> **Layer 2 — Honeypots (deterministic reference tasks)**
>
> Robotics workloads have a structural advantage: simulators (e.g. ManiSkill, Isaac Sim, subnet-specific benches) can produce deterministic ground-truth metrics.
>
> The network (or a governed oracle module) **injects honeypots into the task mix** — runs whose correct grades are known before validators vote. Validators do not know which jobs are honeypots.
>
> If a validator's AI stack awards high scores to an objectively failed reference (e.g. dropped object marked as success), the protocol applies a hard penalty, up to slashing on severity tiers defined by governance.

The metascore formula explicitly includes honeypot accuracy:

> **S(V_i) = α·C(W_i, W̄) + β·H(V_i) − γ·P_i**
>
> - `C(W_i, W̄)` — Consensus alignment with network
> - `H(V_i)` — **Honeypot accuracy** ← *requires honeypot infrastructure to exist*
> - `P_i` — Operational penalties

**Status: page is titled "Validator metascore (design)".** The `H(V_i)` term is in the formula but the system that produces honeypots does not exist as published code.

This isn't speculation — the page literally says "(design)" and there's no implementation referenced anywhere in their docs.

---

## Why This Wins the Spark Grant

| Builder requirement | How Honeynet hits it |
|---|---|
| "Working prototype, not slideware" | Generate honeypots, inject into testnet, demo dashboard |
| "Team with ML / robotics / distributed systems background" | Procedural simulation, oracle design, statistical validation |
| "Commitment to ship on Konnex" | Plugs directly into validator metascore Layer 2 |
| "Open-source contributions — strong plus" | First public Konnex companion infrastructure |

**RFP category match:** "Propose your own subnet" — Honeynet is meta-infrastructure that all subnets need.

This is a **stronger fit for "propose your own"** than for the listed categories because honeypot generation is cross-cutting: it serves drones, roboarm, AND SLAM subnets simultaneously.

---

## What We Build

### Core: Honeypot Pipeline

```
Honeypot Generator → Task Submission (with hidden ground truth) → Validator Pool → Score Comparison Oracle → Per-validator H(V_i) score
```

**Pipeline stages:**

1. **Task Generator** — Procedural generation of subnet-appropriate tasks
   - **Roboarm:** kitchen scenes via PyBullet (e.g. "pick apple, place on plate") with deterministic seed
   - **Drone:** synthetic 3D environments via PyBullet/Open3D with target waypoints
   - **SLAM:** point cloud reconstruction tasks against held-out ground-truth meshes

2. **Ground-Truth Anchor** — Each generated task has a known-correct outcome computed at generation time:
   - Success/failure verdict
   - Expected per-metric scores (accuracy, safety, etc.)
   - Hash of ground-truth bundle stored offchain, commitment hash anchored onchain

3. **Indistinguishability Layer** — Honeypots must look identical to organic tasks:
   - Same JSON schema as real Konnex tasks (per `https://docs.konnex.world/subnets-workload-classes/roboarm-vla`)
   - Same fee/reward structure
   - Same deadline distribution
   - Same operator signature pattern

4. **Injection Scheduler** — Configurable rate (default 5–10% of task volume), randomized per validator subset, governance-tunable

5. **Comparison Oracle** — After validators vote, compare each validator's score vector for honeypot tasks against ground truth:
   - Per-validator honeypot accuracy `H(V_i) ∈ [0, 1]`
   - Streaming aggregation, rolling windows
   - Severity tiering for divergence (matches their slashing model)

6. **Anti-Detection Hardening** — Validators will try to detect honeypots:
   - Statistical fingerprinting tests run continuously
   - Generator parameters tuned so honeypot distribution matches organic distribution
   - Adversarial validator simulation in test suite

### Killer Demo: Lazy Validator Detection

A web dashboard that:
1. Spins up 5 simulated validators with different behavior profiles:
   - **Honest validator** — runs full pipeline
   - **Lazy validator** — copies the median of others
   - **Stake-pump validator** — always votes "success" with high score
   - **Colluding pair (V1, V2)** — vote identically regardless of task
   - **Random validator** — uniformly random scores
2. Submits 100 organic tasks + 10 honeypots over 5 minutes
3. Live-updates the metascore `S(V_i)` for each validator
4. Shows the honeypot accuracy `H(V_i)` column "outing" the bad actors within minutes

This is undeniable: the chart visibly separates honest from lazy/malicious validators using only honeypot accuracy.

---

## Tech Stack (All Open-Source, All Free)

| Component | Library | Purpose |
|---|---|---|
| Task generation | `pybullet`, `numpy` | Deterministic scene synthesis |
| Schema validation | `pydantic` | Match Konnex task JSON exactly |
| Oracle comparison | `scipy.spatial` (cosine distance) | Score-vector comparison |
| Anti-detection | `scipy.stats` (KS test, etc.) | Distributional matching |
| Backend | `fastapi` + `uvicorn` | HTTP API |
| Streaming aggregation | `redis` (optional) or in-memory | Rolling honeypot accuracy |
| Dashboard | React + Vite + Tailwind + Recharts | Live metascore visualization |

---

## Konnex Documentation References (All Verified Working)

### Core spec we implement
- **Validator metascore (design)** — Layer 2 honeypots: https://docs.konnex.world/understand-konnex/validator-metascore
- **Validating overview:** https://docs.konnex.world/participate/validating
- **Mining overview** — what gets validated: https://docs.konnex.world/participate/mining

### Task schemas we mirror
- **Roboarm VLA task shape:** https://docs.konnex.world/subnets-workload-classes/roboarm-vla
- **Drone navigation task shape:** https://docs.konnex.world/subnets-workload-classes/drone-navigation
- **SLAM 3D map task shape:** https://docs.konnex.world/subnets-workload-classes/slam-3d-map
- **Subnets overview:** https://docs.konnex.world/subnets-workload-classes/subnets

### Protocol context
- **Protocol architecture** — registries, ScoreRoot, gossip channels: https://docs.konnex.world/understand-konnex/protocol-architecture
- **Proof-of-Physical-Work:** https://docs.konnex.world/understand-konnex/contracts-and-popw
- **AI ecosystem:** https://docs.konnex.world/understand-konnex/ai-ecosystem
- **Roadmap:** https://docs.konnex.world/understand-konnex/roadmap

### Builder program
- **Apply page:** https://subnets.testnet.konnex.world/builders
- **Testnet explorer:** https://subnets.testnet.konnex.world/explorer

### Their funding (for the legitimacy section of the application)
- **SiliconANGLE:** https://siliconangle.com/2026/01/15/konnex-nabs-15m-decentralize-autonomous-robotic-labor/
- **The Robot Report:** https://www.therobotreport.com/konnex-raises-funding-advance-robotics-as-a-service-offering/

---

## Reality Check (Not Slop)

**Their public GitHub is 404** — same finding as Idea #1:
- `https://github.com/konnex-network` — 404
- `https://github.com/konnex-world/konnex` — 404

This applies the same way: we build standalone, mirror their schema from docs, drop our public GitHub URL into the application form.

---

## Comparison vs. Idea #1

| Factor | Idea #1 (DetVerify) | Idea #2 (Honeynet) |
|---|---|---|
| **Demo visual impact** | High — adversarial vs. GPT side-by-side | Medium — chart separation over time |
| **RFP category fit** | Direct ("Sensor fusion & PoPW validation") | Sideways ("Propose your own") |
| **Code novelty** | High — replaces published reference | Very high — implements unbuilt formula term |
| **Solo-buildable** | Yes | Yes |
| **Cross-subnet leverage** | High (every subnet uses verifiers) | Highest (honeypots serve all subnets simultaneously) |
| **Risk of being scooped** | Medium — obvious build | Low — fewer people understand validator metascore deeply |
| **Time to working prototype** | 2 weeks | 2–3 weeks |

**Honest take:** Idea #1 has a sexier demo. Idea #2 demonstrates deeper protocol understanding. Reviewers may weight #2 higher precisely because fewer applicants will have read the metascore design page.

---

## What We Do NOT Need

| Item | Why we skip it |
|---|---|
| Real robot hardware | Pure simulation by design — that's the point of honeypots |
| GPU compute | Procedural generation + classical statistics only |
| Onchain deployment | Off-chain oracle that posts commitment hashes; mainnet integration is Phase 1 work |
| Their actual SDK | Mirror their JSON schema from docs |
| OpenAI API | Not used — honeypots compare scores against ground truth, no LLM needed |

---

## Effort & Timeline

| Phase | Time | Output |
|---|---|---|
| **Week 1** | Task generators (roboarm + drone + SLAM), ground-truth anchoring | Generates indistinguishable honeypots for all 3 subnets |
| **Week 2** | Comparison oracle, anti-detection statistics, simulated validator pool | End-to-end pipeline runs locally |
| **Week 3** | React dashboard, live metascore visualization, demo recording | Public demo URL on VPS |
| **Week 4 (buffer)** | Anti-detection hardening, tests, application polish | Submit |

**Total:** ~100–140 hours focused dev. The validator simulator harness is the slowest part because it needs to convincingly fake organic validator behavior.

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Grant rejection | Medium-high | Code reusable for any Bittensor-style subnet validator metascore |
| "Propose your own" treated as lower priority than listed RFP categories | Medium | Frame the application around metascore Layer 2 explicitly — not as a standalone subnet |
| Konnex builds it themselves | Low — they've had the design for months without shipping | Ship fast, become reference implementation |
| Generator detection by smart validators | Medium | Continuous statistical hardening; future enhancement: ML-based generation tuning |
| Validator simulator not convincing in demo | Medium | Multiple behavior archetypes, real timing variance, replay actual roboarm tasks |

---

## How This Becomes Mainnet ($200K+)

1. **Spark ($25K):** Working honeypot generator + oracle + lazy-validator detection demo
2. **Launch ($75K):** Generator running against testnet validators, producing real `H(V_i)` scores feeding into validator scoring
3. **Mainnet ($200K+):** Honeypot oracle becomes a governance-controlled module; ongoing fees per honeypot generated; validator slashing fees flow back to Honeynet stake

This is one of the few Konnex builds that has **structural recurring revenue** at mainnet — every honeypot served generates protocol fees, scaling with network usage.

---

## Final Honest Take

Honeynet is the **highest-IQ pick** but the **hardest to demo simply**. It demonstrates that you read past the marketing pages into the actual cryptoeconomic design.

Pick this if:
- You want to stand out from applicants who pitch "another drone subnet"
- You're comfortable explaining validator metascore math in the tech call
- You value recurring mainnet revenue over a one-time grant

Pick Idea #1 instead if:
- You want a more visually obvious 30-second demo
- You'd rather hit a listed RFP category than "propose your own"
