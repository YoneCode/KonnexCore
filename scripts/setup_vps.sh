#!/usr/bin/env bash
#
# KonnexCore — idempotent VPS bootstrap.
#
# Run as the project owner (the user who will own the venv and the
# checked-out repo). The script invokes ``sudo`` for system-level
# changes — apt-get, ufw, systemctl, nginx reload.
#
# Idempotency
# -----------
# Re-running setup_vps.sh on an already-provisioned host is safe:
#   * apt-get install only adds missing packages
#   * `ufw allow` is a no-op for already-permitted ports
#   * `python -m venv` skips if the venv already exists
#   * pip install is a no-op when requirements are satisfied
#   * pnpm build re-runs (always cheap; adds the latest source)
#   * symlinks are removed first, then re-created
#   * `systemctl enable --now` is the documented idempotent form
#
# Usage
# -----
#   ./scripts/setup_vps.sh                    # default config
#   PROJECT_DIR=$HOME/KonnexCore ./scripts/setup_vps.sh
#   SERVER_NAME=demo.example.com ./scripts/setup_vps.sh
#
# Run uninstall.sh from the same directory to undo (preserves source).

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SERVER_NAME="${SERVER_NAME:-_}"  # `_` matches any host (Nginx default-server)
PYTHON_BIN="${PYTHON_BIN:-python3}"
SERVICE_NAME="${SERVICE_NAME:-konnexcore}"
SITE_NAME="${SITE_NAME:-konnexcore}"

log()  { printf '[setup_vps] %s\n' "$*"; }
warn() { printf '[setup_vps] WARN: %s\n' "$*" >&2; }

if [[ "$(id -u)" -eq 0 ]]; then
    warn "running as root — recommended is to run as the project owner with sudo prompts"
fi

cd "$PROJECT_DIR"
log "project directory: $PROJECT_DIR"

# ---------------------------------------------------------------------------
# 1. System packages
# ---------------------------------------------------------------------------
log "installing system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    build-essential pkg-config \
    nginx ufw curl git ca-certificates \
    libgl1 libglib2.0-0   # required by pybullet's headless renderer

# Node + pnpm only if dashboard ships from this host.
if ! command -v node >/dev/null 2>&1; then
    log "installing Node 20 (NodeSource)"
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y -qq nodejs
fi
if ! command -v pnpm >/dev/null 2>&1; then
    log "installing pnpm"
    sudo npm install -g pnpm@9
fi

# ---------------------------------------------------------------------------
# 2. Firewall
# ---------------------------------------------------------------------------
log "configuring ufw"
sudo ufw allow OpenSSH >/dev/null
sudo ufw allow 80/tcp >/dev/null
sudo ufw allow 443/tcp >/dev/null
# Backend port 8000 is *not* exposed publicly — Nginx proxies to it
# locally. Keep 8000 closed at the firewall.
if ! sudo ufw status | grep -q "Status: active"; then
    log "enabling ufw"
    sudo ufw --force enable
fi

# ---------------------------------------------------------------------------
# 3. Python venv + dependencies
# ---------------------------------------------------------------------------
if [[ ! -x "$PROJECT_DIR/venv/bin/python" ]]; then
    log "creating Python venv"
    "$PYTHON_BIN" -m venv "$PROJECT_DIR/venv"
fi
log "installing/refreshing Python dependencies"
"$PROJECT_DIR/venv/bin/python" -m pip install --upgrade --quiet pip
"$PROJECT_DIR/venv/bin/python" -m pip install --quiet -r "$PROJECT_DIR/requirements.txt"

# ---------------------------------------------------------------------------
# 4. Dashboard build
# ---------------------------------------------------------------------------
log "building dashboard"
pushd "$PROJECT_DIR/dashboard" >/dev/null
pnpm install --frozen-lockfile
pnpm run build
popd >/dev/null

# ---------------------------------------------------------------------------
# 5. Nginx site
# ---------------------------------------------------------------------------
NGINX_TEMPLATE="$PROJECT_DIR/scripts/nginx.conf"
NGINX_TARGET="/etc/nginx/sites-available/${SITE_NAME}"

log "rendering and installing Nginx config (server_name=$SERVER_NAME)"
sudo bash -c "
    sed -e 's|@PROJECT_DIR@|$PROJECT_DIR|g' \
        -e 's|@SERVER_NAME@|$SERVER_NAME|g' \
        '$NGINX_TEMPLATE' > '$NGINX_TARGET'
"
sudo ln -sfn "$NGINX_TARGET" "/etc/nginx/sites-enabled/${SITE_NAME}"

# Disable the stock default if it's still active.
if [[ -L /etc/nginx/sites-enabled/default ]]; then
    log "removing default Nginx site"
    sudo rm /etc/nginx/sites-enabled/default
fi

log "validating Nginx config"
sudo nginx -t

log "reloading Nginx"
sudo systemctl reload nginx

# ---------------------------------------------------------------------------
# 6. Systemd unit
# ---------------------------------------------------------------------------
SERVICE_TEMPLATE="$PROJECT_DIR/scripts/konnexcore.service"
SERVICE_TARGET="/etc/systemd/system/${SERVICE_NAME}.service"

log "installing systemd unit ($SERVICE_NAME)"
sudo bash -c "
    sed -e 's|@PROJECT_DIR@|$PROJECT_DIR|g' \
        -e 's|@USER@|$(id -un)|g' \
        '$SERVICE_TEMPLATE' > '$SERVICE_TARGET'
"
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"

# ---------------------------------------------------------------------------
# 7. Health check
# ---------------------------------------------------------------------------
sleep 2
log "verifying backend health on 127.0.0.1:8000"
if curl -fsS http://127.0.0.1:8000/api/health >/dev/null; then
    log "backend OK"
else
    warn "backend not responding — check 'journalctl -u $SERVICE_NAME -n 50'"
    exit 1
fi

log "verifying dashboard via Nginx on localhost:80"
if curl -fsS http://localhost/ -o /dev/null; then
    log "dashboard OK"
else
    warn "dashboard not responding — check Nginx error log"
    exit 1
fi

cat <<EOF
[setup_vps] done.

  Backend log:    journalctl -u $SERVICE_NAME -f
  Nginx log:      sudo tail -f /var/log/nginx/error.log
  Restart all:    sudo systemctl restart $SERVICE_NAME && sudo systemctl reload nginx

  HTTP:  http://${SERVER_NAME//_/$(hostname -I | awk '{print $1}')}/
  Docs:  http://${SERVER_NAME//_/$(hostname -I | awk '{print $1}')}/docs

  For HTTPS, run scripts/setup_letsencrypt.sh after pointing DNS at this host.
EOF
