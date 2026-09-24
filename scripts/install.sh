#!/bin/bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

INSTALL_ROOT="/opt/Svxlink-Streamer"
SERVICE_FILE="/etc/systemd/system/svxlink-streamer.service"
SVXLINK_DROPIN_DIR="/etc/systemd/system/svxlink.service.d"
SVXLINK_DROPIN_FILE="${SVXLINK_DROPIN_DIR}/audio-monitor.conf"

REQUIRED_PACKAGES=(
    ffmpeg
    python3-flask
    build-essential
    libasound2-dev
)

if [[ $EUID -ne 0 ]]; then
    echo "Run this installer as root."
    exit 1
fi

echo "Svxlink-Streamer installer"
echo "=========================="
echo

echo "Installing required packages..."
apt-get update
DEBIAN_FRONTEND=noninteractive \
    apt-get install -y "${REQUIRED_PACKAGES[@]}"

echo
echo "Building TX tap library..."

make -C "${PROJECT_ROOT}" clean
make -C "${PROJECT_ROOT}"

if [[ ! -f "${PROJECT_ROOT}/libsvxlink_tx_tap.so" ]]; then
    echo "ERROR: TX tap library was not built."
    exit 1
fi

echo
echo "Installing project files..."

install -d -m 0755 "${INSTALL_ROOT}"
install -d -m 0755 "${INSTALL_ROOT}/streamer"

install -m 0755 \
    "${PROJECT_ROOT}/streamer/svxlink_streamer.py" \
    "${INSTALL_ROOT}/streamer/svxlink_streamer.py"

install -m 0755 \
    "${PROJECT_ROOT}/libsvxlink_tx_tap.so" \
    "${INSTALL_ROOT}/libsvxlink_tx_tap.so"

echo
echo "Installing systemd service..."

install -m 0644 \
    "${PROJECT_ROOT}/systemd/svxlink-streamer.service" \
    "${SERVICE_FILE}"

echo
echo "Installing SvxLink audio monitor drop-in..."

install -d -m 0755 "${SVXLINK_DROPIN_DIR}"

install -m 0644 \
    "${PROJECT_ROOT}/systemd/svxlink.service.d/audio-monitor.conf" \
    "${SVXLINK_DROPIN_FILE}"

echo
echo "Reloading systemd..."

systemctl daemon-reload

echo
echo "Restarting SvxLink with TX monitor enabled..."

systemctl restart svxlink.service

if ! systemctl is-active --quiet svxlink.service; then
    echo "ERROR: svxlink.service failed to restart."
    systemctl status svxlink.service --no-pager -l || true
    exit 1
fi

echo "SvxLink is active."

echo
echo "Enabling and starting Svxlink-Streamer..."

systemctl enable svxlink-streamer.service
systemctl restart svxlink-streamer.service

if ! systemctl is-active --quiet svxlink-streamer.service; then
    echo "ERROR: svxlink-streamer.service failed to start."
    systemctl status svxlink-streamer.service --no-pager -l || true
    exit 1
fi

echo "Svxlink-Streamer is active."

echo
echo "Checking streamer health endpoint..."

health_ok=0

for attempt in 1 2 3 4 5; do
    if python3 - <<'PY'
import json
import urllib.request

with urllib.request.urlopen(
    "http://127.0.0.1:8765/health",
    timeout=2,
) as response:
    data = json.load(response)

if data.get("status") != "ok":
    raise SystemExit(1)
PY
    then
        health_ok=1
        break
    fi

    sleep 1
done

if [[ "${health_ok}" -ne 1 ]]; then
    echo "ERROR: streamer health check failed."
    systemctl status svxlink-streamer.service --no-pager -l || true
    exit 1
fi

echo
echo "Installation complete."
echo
echo "Services:"
echo "  svxlink.service          ACTIVE"
echo "  svxlink-streamer.service ACTIVE"
echo
echo "Local stream:"
echo "  http://127.0.0.1:8765/stream.mp3"
echo
echo "Health:"
echo "  http://127.0.0.1:8765/health"