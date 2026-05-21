#!/usr/bin/env bash
#
# Undo what setup_vps.sh installed at the system level.
# Source code, the venv, and the dashboard build are left in place.
#
# Run as the project owner (uses sudo for system-level changes).

set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-konnexcore}"
SITE_NAME="${SITE_NAME:-konnexcore}"

log() { printf '[uninstall] %s\n' "$*"; }

if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    log "stopping and disabling ${SERVICE_NAME}.service"
    sudo systemctl disable --now "$SERVICE_NAME" || true
    sudo rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    sudo systemctl daemon-reload
fi

if [[ -L "/etc/nginx/sites-enabled/${SITE_NAME}" ]]; then
    log "removing Nginx site ${SITE_NAME}"
    sudo rm -f "/etc/nginx/sites-enabled/${SITE_NAME}"
fi
sudo rm -f "/etc/nginx/sites-available/${SITE_NAME}"

if sudo nginx -t >/dev/null 2>&1; then
    sudo systemctl reload nginx
else
    log "Nginx config currently invalid — skipping reload, fix manually"
fi

log "done. The venv, dashboard build, and source files are untouched."
log "To remove the source itself, delete the project directory by hand."
