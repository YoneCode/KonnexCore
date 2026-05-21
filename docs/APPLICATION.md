# KonnexCore — Builder Spark Grant Application

> Pre-filled answers for the form at `https://subnets.testnet.konnex.world/builders`.
> Anything in `[FILL IN]` must be supplied by the operator before submission.

---

## Project / team name

KonnexCore

## Your name

[FILL IN]

## Role

Founder / Tech lead

## Work email

[FILL IN]

## Twitter / X

[FILL IN — @handle or leave blank]

## GitHub / portfolio

https://github.com/YoneCode/KonnexCore

## One-line pitch (140 chars max)

KonnexCore: TEE-attested sensor capture + deterministic Layer-3 verifier + honeypot oracle. The validator stack Konnex specced.

## What subnet are you building and why Konnex?

KonnexCore is the validator infrastructure stack Konnex's docs spec but doesn't yet ship as public reference code:

1. **RootID (Layer A)** — implements the off-chain attestation pipeline that anchors the RobotIdentity contract to TEE-signed sensor telemetry. Software-simulated TEE today; production binds to ARM PSA Crypto API.

2. **DetVerify (Layer B)** — implements Layer 3 of the validator metascore (deterministic tier). Six closed-form checks that catch adversarial bundles which fool the GPT-4o reference verifier.

3. **Honeynet (Layer C)** — implements Layer 2 of the validator metascore (honeypot generation). Indistinguishable reference tasks that compute H(V_i) per validator and surface lazy/colluding behavior.

Why Konnex: the $15M strategic round, doxxed robotics-industry founders (Ollwerther, Declet, Van Oostrum), and a public spec that explicitly leaves these layers to the builder ecosystem make this the right project to ship reference code for. Konnex needs deterministic verification primitives that don't depend on per-call LLM costs, and honeypot infrastructure to score the validators that score miners.

## Subnet category

Sensor fusion & PoPW validation

## Stage

Working demo

## Demo link

[FILL IN — e.g. https://demo.example.com or http://<vps-ip>]

(Backup video: [FILL IN — https://youtu.be/<unlisted-id>])

## Team size & key members

Solo founder: [FILL IN — name + 1-2 sentences on background].

## Optional: grant ask & funding history

Grant ask: Spark ($25,000) — milestones tied to:
- Public GitHub repo with MIT license (delivered at submission)
- Live demo URL with full 3-layer flow (delivered at submission)
- Integration with Konnex SDK once their public repo is available
- Documentation on protocol-architecture mapping (delivered at submission)

Funding history: none.
