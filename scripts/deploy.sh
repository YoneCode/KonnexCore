#!/usr/bin/env bash
#
# Build the dashboard locally and ship it (plus any code changes) to
# a remote VPS over SSH+rsync. Triggers a service restart at the end.
#
# Usage
# -----
#   REMOTE_USER=<user> REMOTE_HOST=<vps-ip> ./scripts/deploy.sh
#
# Optional env:
#   REMOTE_PATH    target dir on the VPS  (default ~/KonnexCore)
#   SERVICE_NAME   systemd unit name      (default konnexcore)
#   SKIP_BUILD=1   skip pnpm build
#   DRY_RUN=1      show rsync plan only
#
# Pre-conditions on the VPS:
#   * setup_vps.sh has been run there at least once
#   * SSH keys configured for passwordless login

set -euo pipefail

REMOTE_USER="${REMOTE_USER:?must set REMOTE_USER}"
REMOTE_HOST="${REMOTE_HOST:?must set REMOTE_HOST}"
REMOTE_PATH="${REMOTE_PATH:-~/KonnexCore}"
SERVICE_NAME="${SERVICE_NAME:-konnexcore}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

log() { printf '[deploy] %s\n' "$*"; }

# ---------------------------------------------------------------------------
# 1. Build dashboard locally
# ---------------------------------------------------------------------------
if [[ -z "${SKIP_BUILD:-}" ]]; then
    log "building dashboard locally"
    (cd dashboard && pnpm install --frozen-lockfile && pnpm run build)
fi

# ---------------------------------------------------------------------------
# 2. rsync to VPS — exclude build artefacts and venvs
# ---------------------------------------------------------------------------
RSYNC_FLAGS=(
    --archive
    --compress
    --delete
    --human-readable
    --verbose
)
if [[ -n "${DRY_RUN:-}" ]]; then
    RSYNC_FLAGS+=(--dry-run)
fi

EXCLUDES=(
    ".git/"
    ".venv/"
    "venv/"
    "__pycache__/"
    "*.pyc"
    ".pytest_cache/"
    ".mypy_cache/"
    ".ruff_cache/"
    ".coverage"
    "htmlcov/"
    "dashboard/node_modules/"
    "bundle.json"
    ".env"
    ".env.local"
)
EXCLUDE_FLAGS=()
for e in "${EXCLUDES[@]}"; do
    EXCLUDE_FLAGS+=("--exclude" "$e")
done

log "rsync to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}"
rsync "${RSYNC_FLAGS[@]}" "${EXCLUDE_FLAGS[@]}" \
    "$PROJECT_DIR"/ "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/"

if [[ -n "${DRY_RUN:-}" ]]; then
    log "DRY_RUN — stopping before remote install/restart"
    exit 0
fi

# ---------------------------------------------------------------------------
# 3. Refresh deps + restart service on the VPS
# ---------------------------------------------------------------------------
log "refreshing python deps and restarting ${SERVICE_NAME}"
ssh "${REMOTE_USER}@${REMOTE_HOST}" bash <<EOF
set -euo pipefail
cd "${REMOTE_PATH}"
./venv/bin/python -m pip install --quiet -r requirements.txt
sudo systemctl restart "${SERVICE_NAME}"
sudo systemctl reload nginx
sleep 1
curl -fsS http://127.0.0.1:8000/api/health
EOF

log "done."
