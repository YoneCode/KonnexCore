# KonnexCore

TEE-attested sensor capture · deterministic Layer-3 verifier · honeypot oracle.

The three validator-infrastructure layers Konnex's protocol architecture specifies — shipped as a working open-source prototype for the **Spark builder grant**.

---

## What this builds

Konnex validators score robotics workloads via a multi-layer metascore. Two of those layers — the deterministic verification tier and the honeypot oracle — have published designs but no reference code. KonnexCore fills that gap:

| Layer | Module | What it does |
|-------|--------|--------------|
| **A — RootID** | `rootid/` | Ed25519 keypair inside a software-simulated TEE. Signs every sensor packet at capture time with a monotonic per-`(job, channel)` nonce. Bound to a `did:knx:` identity. |
| **B — DetVerify** | `detverify/` | Six deterministic stages (signature, temporal, cross-modal, replay, anomaly, kinematic). Same input produces the same Konnex `ScoreVector` every time. No LLM. No network call. |
| **C — Honeynet** | `honeynet/` | Generates indistinguishable reference tasks with hidden ground truth. Computes `H(V_i)` per validator. Separates honest from lazy by ≥ 0.3 metascore points. |

A React dashboard, a FastAPI backend exposing all three layers over HTTP, and a PyBullet-backed simulation engine round out the prototype. 

---

## Run locally

```bash
git clone https://github.com/YoneCode/KonnexCore.git
cd KonnexCore

# Python backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
make test                       # 293 tests, ~6 s

# Start the API server
uvicorn api.main:app --host 127.0.0.1 --port 8000

# Dashboard (separate terminal)
cd dashboard && pnpm install && pnpm dev
# Open http://localhost:5173
```

## Run the examples (no UI required)

```bash
python examples/01_sign_sensor.py                # RootID: sign + verify
python examples/01_sign_sensor.py --tamper signature
python examples/02_sim_bundle.py                 # PyBullet sim → signed bundle
python examples/03_verify_bundle.py              # DetVerify pipeline
python examples/03_verify_bundle.py --tamper torque
python examples/04_attack_lab.py                 # 5 adversarial bundles
python examples/05_honeypot_demo.py              # Honeynet leaderboard
```

---

## Deploy to a VPS

```bash
ssh user@your-server
git clone https://github.com/YoneCode/KonnexCore.git
cd KonnexCore
./scripts/setup_vps.sh
```

Installs system packages, builds the dashboard, configures Nginx + systemd, runs health checks. Idempotent — safe to re-run after pulling new code. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for HTTPS setup, continuous deployment, and troubleshooting.

---

## Project structure

```
core/
├── models.py            Pydantic schemas (SensorPacket, ScoreVector, PoPWBundle, ...)
├── crypto.py            Ed25519 + SHA-3-256 + Merkle root
├── sensor_codec.py      Camera / IMU / torque byte codecs
├── sim_engine.py        PyBullet roboarm simulator
├── attack_lab.py        5 adversarial bundle generators
├── config.py            Constants + pydantic-settings
└── data_loaders/        TUM RGB-D / EuRoC / BridgeData v2 loaders

rootid/
├── tee_simulator.py     Software TEE (isolated keypair + monotonic nonce)
├── sensor_signer.py     Signs packets, builds PoPWBundles with Merkle root
├── verifier.py          11-class failure-reason taxonomy
├── did.py               did:knx: method (make / parse / build_document)
└── registry.py          Mock RobotIdentity contract

detverify/
├── pipeline.py          Orchestrates 6 stages, emits DetVerifyResult
├── score_emitter.py     Maps stage outcomes → Konnex ScoreVector
├── stages/              stage1_signature … stage6_kinematic
└── llm_compare.py       Optional GPT-4o adapter (graceful no-op without key)

honeynet/
├── oracle.py            Registers honeypots, records votes, computes S(V_i)
├── metascore.py         vector_similarity + S(V_i) = α·C + β·H − γ·P
├── validator_pool.py    5 archetypes (honest, lazy, stake-pump, collusion, random)
├── injector.py          Mixes organic + honeypot tasks, hides ground truth
└── generators/          Deterministic roboarm honeypot generator

api/
├── main.py              FastAPI app (14 endpoints)
├── deps.py              Shared state (registry, oracle, pipeline, TEE pool)
├── middleware.py        Request logging + error handler
└── routes/              health · identity · verify · honeypot · attack · demo

dashboard/
├── src/pages/           Home · RootIDDemo · DetVerifyDemo · HoneynetDemo · FullStackDemo
├── src/components/      Header · StageRow · ScorePanel
└── src/api/client.ts    Typed wrappers over all 14 backend endpoints

scripts/
├── setup_vps.sh         Idempotent VPS bootstrap
├── deploy.sh            Build + rsync + restart
├── nginx.conf           Templated site config
├── konnexcore.service   Systemd unit (sandboxed)
└── playwright_smoke.py  Browser-level end-to-end test

examples/                5 runnable demos (one per phase)
docs/                    DEPLOYMENT.md · APPLICATION.md · RECORDING_SCRIPT.md
```

---

## Tech stack

| Layer | Tool | Version |
|-------|------|---------|
| Crypto | `cryptography` (Ed25519) + `hashlib` (SHA-3-256) | 43.0.1+ |
| Simulation | PyBullet (headless DIRECT mode) | 3.2.6 |
| Anomaly detection | scikit-learn IsolationForest | 1.5.2 |
| Backend | FastAPI + uvicorn | 0.115.0 |
| Frontend | React 19 + Vite + TypeScript + Tailwind 3 | — |
| Charts | Recharts | 2.13.0 |
| Testing | pytest + Hypothesis (property-based) | 8.3.3 |

---

## Quality

```
293 tests · 99% line coverage · ruff strict · mypy strict · black formatted
```

Real sensor data tested end-to-end: TUM RGB-D freiburg1_desk (11,818 IMU readings + 595 depth frames) flows through the full RootID → DetVerify pipeline with zero mocks.

---

## Konnex protocol compliance

- **ScoreVector** mirrors `docs.konnex.world/supported-ai-models/verifier` exactly (9 fields, same types, `extra="forbid"`).
- **SHA-3-256** throughout (per `docs.konnex.world/understand-konnex/protocol-architecture`).
- **Validator metascore** formula `S(V_i) = α·C + β·H − γ·P` per `docs.konnex.world/understand-konnex/validator-metascore`.
- **RobotIdentity** interface per `docs.konnex.world/understand-konnex/contracts-and-popw`.
- **did:knx:** method follows W3C DID Core.

---

## What we do NOT claim

- Production hardware TEE — software simulation only (ARM PSA swap-in documented).
- Mainnet integration — testnet wiring is Launch-tier scope.
- Real robots — synthetic + recorded sensor data only.
- Replacing Konnex's AI Verifier — we augment Layer 3 with the deterministic tier. 

---

## License

MIT — see [`LICENSE`](LICENSE).
