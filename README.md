# KonnexCore

> TEE-attested sensor capture + deterministic Layer-3 verifier + honeypot oracle.
> The validator stack Konnex specced.

**Status:** Phase 8 — VPS deployment ready.

KonnexCore is a working open-source prototype combining three Konnex builder ideas
into one unified validator infrastructure stack:

- **RootID** (Layer A) — TEE-simulated sensor signing pipeline that anchors the
  Konnex `RobotIdentity` contract to capture-time provenance.
- **DetVerify** (Layer B) — six-stage deterministic verifier that emits the
  Konnex AI Verifier `ScoreVector` and catches adversarial bundles which fool
  the GPT-4o reference verifier.
- **Honeynet** (Layer C) — honeypot generator + comparison oracle implementing
  Layer 2 of the Konnex validator metascore (`H(V_i)`).

## Run locally in 60 seconds

```bash
git clone https://github.com/yoncode/konnex-detverify.git
cd konnex-detverify
make dev                      # install pinned Python deps
make test                     # 293 tests, ~6 s

# In one terminal — start the FastAPI backend.
venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000

# In another terminal — start the Vite dashboard.
make dashboard                # Vite dev server on :5173 with /api proxy

# Open http://localhost:5173 in a browser.
```

The dashboard's `/full-stack` page exercises the entire RootID → DetVerify chain
in one click; the `/honeynet` page renders the live oracle leaderboard.

## Run the example scripts (no UI needed)

```bash
python examples/01_sign_sensor.py            # RootID demo
python examples/01_sign_sensor.py --tamper signature
python examples/02_sim_bundle.py             # PyBullet → signed PoPWBundle → verify
python examples/03_verify_bundle.py          # DetVerify pipeline + ScoreVector
python examples/04_attack_lab.py             # 5 adversarial bundles vs DetVerify
python examples/05_honeypot_demo.py          # honeynet leaderboard, 100 + 10 tasks
```

## Deploy to a VPS

```bash
ssh user@vps
cd ~/konnex-detverify
./scripts/setup_vps.sh
# Done. Browse http://<vps-ip>/
```

`setup_vps.sh` is idempotent — apt-get install, ufw rules, venv refresh, dashboard
build, Nginx config render, systemd unit install, health-check.

For HTTPS, browser-level smoke tests, and continuous deploy from a developer
machine, see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Project layout

```
core/        # Pydantic schemas, crypto, sim engine, attack lab
rootid/      # Layer A — TEE simulator, signer, verifier, registry
detverify/   # Layer B — six-stage pipeline, score emitter, llm compare
honeynet/    # Layer C — oracle, validator pool, metascore, generators
api/         # FastAPI backend (14 endpoints per spec §7)
dashboard/   # Vite + React + TS frontend
examples/    # Runnable demos for each phase
scripts/     # setup_vps.sh, nginx.conf, systemd unit, deploy.sh
docs/        # DEPLOYMENT.md + per-phase plans + per-phase reports
```

See [`how-to-creat-stong-dapp-from-3-idea.md`](how-to-creat-stong-dapp-from-3-idea.md)
for the full build spec the project implements.

## Tests + CI

```bash
make test                    # 293 tests
make test-fast               # skip pybullet-backed slow tests
make lint                    # ruff + black --check + mypy --strict on core/
make build-dashboard         # tsc + vite build
```

GitHub Actions runs the matrix on every push (Python 3.10 / 3.11 / 3.12).

## License

MIT — see [`LICENSE`](LICENSE).
