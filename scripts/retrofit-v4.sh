#!/bin/bash

set -euo pipefail

DASHBOARD_ROOT="/opt/dashboard"
BACKUP_ROOT="/var/backups/svxlink-streamer-v4"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APP_FILE="${DASHBOARD_ROOT}/app.py"
STATUS_FILE="${DASHBOARD_ROOT}/templates/status.html"
CSS_FILE="${DASHBOARD_ROOT}/static/site.css"

if [[ $EUID -ne 0 ]]; then
    echo "Run this retrofit as root."
    exit 1
fi

for file in \
    "${APP_FILE}" \
    "${STATUS_FILE}" \
    "${CSS_FILE}"
do
    if [[ ! -f "${file}" ]]; then
        echo "ERROR: required dashboard file missing:"
        echo "  ${file}"
        exit 1
    fi
done

echo "Creating dashboard backup..."

install -d -m 0755 "${BACKUP_DIR}"

cp -a "${APP_FILE}" "${BACKUP_DIR}/app.py"
cp -a "${STATUS_FILE}" "${BACKUP_DIR}/status.html"
cp -a "${CSS_FILE}" "${BACKUP_DIR}/site.css"

rollback() {
    echo
    echo "Rolling back dashboard files..."

    cp -a "${BACKUP_DIR}/app.py" "${APP_FILE}"
    cp -a "${BACKUP_DIR}/status.html" "${STATUS_FILE}"
    cp -a "${BACKUP_DIR}/site.css" "${CSS_FILE}"

    systemctl restart svxlink-dash.service || true

    echo "Rollback complete."
}

trap rollback ERR

echo
echo "Installing Svxlink-Streamer..."

"${PROJECT_ROOT}/scripts/install.sh"

echo
echo "Applying V4 dashboard retrofit..."

python3 "${PROJECT_ROOT}/scripts/retrofit-v4.py"

echo
echo "Checking dashboard Python syntax..."

python3 -m py_compile "${APP_FILE}"

echo
echo "Restarting V4 dashboard..."

systemctl restart svxlink-dash.service

sleep 2

if ! systemctl is-active --quiet svxlink-dash.service; then
    echo "ERROR: svxlink-dash.service is not active."
    exit 1
fi

echo
echo "Checking local Status page..."

if ! python3 - <<'PY'
import urllib.request

with urllib.request.urlopen(
    "http://127.0.0.1:5000/status",
    timeout=5,
) as response:
    if response.status != 200:
        raise SystemExit(1)
PY
then
    echo "ERROR: Status page validation failed."
    exit 1
fi

trap - ERR

echo
echo "Retrofit complete."
echo
echo "Backup retained at:"
echo "  ${BACKUP_DIR}"
