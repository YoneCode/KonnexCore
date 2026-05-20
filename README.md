# KonnexCore

> TEE-attested sensor capture + deterministic Layer-3 verifier + honeypot oracle.
> The validator stack Konnex specced.

**Status:** Phase 0 — Foundation.

KonnexCore is a working open-source prototype combining three Konnex builder ideas
into one unified validator infrastructure stack:

- **RootID** (Layer A) — TEE-simulated sensor signing pipeline that anchors the
  Konnex `RobotIdentity` contract to capture-time provenance.
- **DetVerify** (Layer B) — six-stage deterministic verifier that emits the
  Konnex AI Verifier `ScoreVector` and catches adversarial bundles which fool
  the GPT-4o reference verifier.
- **Honeynet** (Layer C) — honeypot generator + comparison oracle implementing
  Layer 2 of the Konnex validator metascore (`H(V_i)`).

## Quick start

```bash
make dev        # install pinned Python dependencies
make test       # run the test suite
make lint       # ruff + black + mypy strict on core/
```

Full local-run instructions land at the end of Phase 6 (FastAPI backend) and
Phase 7 (React dashboard).

## Project layout

See [`how-to-creat-stong-dapp-from-3-idea.md`](how-to-creat-stong-dapp-from-3-idea.md)
Section 3 for the full directory tree and per-module responsibilities.

## License

MIT — see [`LICENSE`](LICENSE).
