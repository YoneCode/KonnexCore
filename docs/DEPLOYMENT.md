# DEPLOYMENT

End-to-end instructions for shipping KonnexCore to a fresh Ubuntu / Debian
VPS. Tested on 24.04 LTS. Adjust paths for other distros.

## Architecture

```
            ┌────────────── port 80 (HTTP) ──────────────┐
            │                                             │
   internet ┼──► nginx ──► /          (static SPA)        │
            │           ├──► /api/*    → 127.0.0.1:8000   │
            │           ├──► /docs     → 127.0.0.1:8000   │
            │           └──► /openapi.json                │
            │                                             │
            └─ systemd: konnexcore.service runs uvicorn ──┘
```

The dashboard is a static build served by Nginx; the FastAPI backend is a
local-only uvicorn process supervised by systemd. The 8000 port is **not**
exposed at the firewall — only Nginx talks to it.

## Prerequisites

- A VPS with **sudo + SSH key access**. Ubuntu 22.04 / 24.04 LTS recommended.
- Project source checked out at `~/konnex-detverify` (any path works; pass
  `PROJECT_DIR=` to override).
- A DNS A record pointing at the VPS IP (only required for HTTPS — HTTP
  works against the bare IP).

## One-shot install

SSH into the VPS as the user that should own the deployment, then:

```bash
git clone https://github.com/yoncode/konnex-detverify.git
cd konnex-detverify
./scripts/setup_vps.sh
```

`setup_vps.sh` is **idempotent** — re-running it on an already-provisioned
host upgrades dependencies and re-renders configs without breaking the
running service.

What it does:

1. `apt-get install` system packages (Python, Nginx, build-essential,
   libgl1, etc.).
2. Installs Node 20 + pnpm 9 if missing.
3. Configures `ufw` to allow OpenSSH + 80 + 443 (port 8000 stays closed).
4. Creates the Python venv and installs `requirements.txt`.
5. `pnpm install --frozen-lockfile && pnpm build` for the dashboard.
6. Renders `scripts/nginx.conf` into `/etc/nginx/sites-available/konnexcore`,
   enables it, removes the stock default site, runs `nginx -t`, reloads.
7. Renders `scripts/konnexcore.service` into `/etc/systemd/system/`,
   `daemon-reload`, `enable --now`.
8. Runs a curl health-check against `127.0.0.1:8000/api/health` and the
   public Nginx route.

When it finishes, the dashboard is reachable at `http://<vps-ip>/` and the
OpenAPI docs at `http://<vps-ip>/docs`.

## Customising the install

Override defaults via env vars:

```bash
PROJECT_DIR=/opt/konnex \
SERVER_NAME=demo.example.com \
SERVICE_NAME=konnex \
SITE_NAME=konnex \
./scripts/setup_vps.sh
```

`SERVER_NAME=_` (the default) tells Nginx to match any host — useful when
deploying against a bare IP. Set a real hostname before turning on HTTPS.

## Day-2 operations

```bash
# Live-tail the backend log.
journalctl -u konnexcore -f

# Manual restart after a code change.
sudo systemctl restart konnexcore && sudo systemctl reload nginx

# Re-run setup_vps.sh after pulling new code.
git pull && ./scripts/setup_vps.sh

# Uninstall (keeps the source).
./scripts/uninstall.sh
```

## Continuous deployment from a developer machine

`scripts/deploy.sh` builds the dashboard locally, rsyncs the project to the
VPS (excluding venvs and caches), refreshes Python deps, and restarts the
service:

```bash
REMOTE_USER=kiro3 REMOTE_HOST=37.120.175.12 ./scripts/deploy.sh

# Dry run — show the rsync plan without touching the remote.
DRY_RUN=1 REMOTE_USER=kiro3 REMOTE_HOST=37.120.175.12 ./scripts/deploy.sh

# Skip the dashboard build (e.g. after Python-only changes).
SKIP_BUILD=1 REMOTE_USER=kiro3 REMOTE_HOST=37.120.175.12 ./scripts/deploy.sh
```

## HTTPS

The shipped Nginx config is HTTP-only by design — Certbot rewrites it to
add the listen 443 ssl block in place. Once DNS points at the VPS:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d demo.example.com
```

Certbot adds an HTTP→HTTPS redirect automatically and schedules a renewal
timer.

## Browser-level smoke test

`scripts/playwright_smoke.py` drives a headless Chromium against a
deployed URL and asserts the home page + full-stack demo render with no
JS console errors. Run it from any host that has Playwright installed:

```bash
python -m pip install 'playwright==1.46.0'
python -m playwright install chromium
# Linux: install Chromium's system libraries (one-time, requires sudo).
sudo python -m playwright install-deps chromium
python scripts/playwright_smoke.py http://<vps-ip>
python scripts/playwright_smoke.py https://demo.example.com
```

Exit code `0` = pass. The test asserts the verdict flips from `success`
to `failure` when switching to the `deepfake` scenario, so it
exercises the full RootID → DetVerify path under load.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `502 Bad Gateway` from Nginx | uvicorn isn't running | `journalctl -u konnexcore -n 80` |
| Dashboard loads but API calls 404 | Nginx site not active | `sudo nginx -t && sudo systemctl reload nginx` |
| `pnpm build` runs out of memory | small VPS | `NODE_OPTIONS="--max-old-space-size=1024" pnpm build` |
| `pybullet` fails to import | missing GL libs | re-run `setup_vps.sh` (installs `libgl1`, `libglib2.0-0`) |
| `setup_vps.sh` aborts on `nginx -t` | server_name conflict | check `/etc/nginx/sites-enabled/` for old leftovers |
| 80 returns the stock Ubuntu page | default site re-enabled | `sudo rm /etc/nginx/sites-enabled/default && sudo systemctl reload nginx` |

## Security notes (for the Spark-tier demo)

- The backend has **no authentication**. Anyone hitting `/api/identity/create`
  can mint a server-held identity. This is intentional for the demo and
  documented in `api/deps.py`. Production deployments add bearer-token
  middleware before opening to the public internet.
- CORS is restricted to the dashboard origin via `KONNEXCORE_CORS_ORIGINS`.
  Default allows `http://localhost:5173` only; set this to your public
  origin in `/etc/systemd/system/konnexcore.service.d/override.conf`:

  ```ini
  [Service]
  Environment="KONNEXCORE_CORS_ORIGINS=https://demo.example.com"
  ```

  Then `sudo systemctl daemon-reload && sudo systemctl restart konnexcore`.
- The TEE simulator's private keys are held in process memory on the VPS.
  Production swaps this for hardware TEE bindings (ARM PSA Crypto API or
  Apple Secure Enclave). See `rootid/tee_simulator.py` module docstring.

## What's deliberately not deployed

- `skills/`, ``, `` — agent reference material,
  not runtime code. `deploy.sh` excludes them; the rsync excludes are
  documented in the script.
- Pytest test suites — they run in CI and locally; the VPS doesn't need
  them. (Re-running `pytest` on the VPS still works if you `cd` into the
  project and call `./venv/bin/pytest`.)
