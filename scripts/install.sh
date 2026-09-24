#!/bin/bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

INSTALL_ROOT="/opt/Svxlink-Streamer"
SERVICE_FILE="/etc/systemd/system/svxlink-streamer.service"
SVXLINK_DROPIN_DIR="/etc/systemd/system/svxlink.service.d"
SVXLINK_DROPIN_FILE="${SVXLINK_DROPIN_DIR}/audio-monitor.conf"
CONFIG_FILE="/etc/svxlink-streamer.conf"

if [[ $EUID -ne 0 ]]; then
    echo "Run this installer as root."
    exit 1
fi

echo "Building TX tap library..."
make -C "${PROJECT_ROOT}" clean
make -C "${PROJECT_ROOT}"

echo "Installing project files..."
install -d -m 0755 "${INSTALL_ROOT}"
install -d -m 0755 "${INSTALL_ROOT}/streamer"

install -m 0755 \
    "${PROJECT_ROOT}/streamer/svxlink_streamer.py" \
    "${INSTALL_ROOT}/streamer/svxlink_streamer.py"

install -m 0755 \
    "${PROJECT_ROOT}/libsvxlink_tx_tap.so" \
    "${INSTALL_ROOT}/libsvxlink_tx_tap.so"

echo "Installing systemd units..."
install -m 0644 \
    "${PROJECT_ROOT}/systemd/svxlink-streamer.service" \
    "${SERVICE_FILE}"

install -d -m 0755 "${SVXLINK_DROPIN_DIR}"

install -m 0644 \
    "${PROJECT_ROOT}/systemd/svxlink.service.d/audio-monitor.conf" \
    "${SVXLINK_DROPIN_FILE}"

if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "Installing example configuration..."
    install -m 0600 \
        "${PROJECT_ROOT}/config/svxlink-streamer.conf.example" \
        "${CONFIG_FILE}"
else
    echo "Preserving existing ${CONFIG_FILE}"
fi

systemctl daemon-reload

echo
echo "Installation complete."
echo
echo "Before enabling the streamer:"
echo "  1. Edit ${CONFIG_FILE}"
echo "  2. Install ffmpeg"
echo "  3. Restart svxlink"
echo "  4. Enable and start svxlink-streamer.service"
echo
echo "Example:"
echo "  sudo nano ${CONFIG_FILE}"
echo "  sudo systemctl restart svxlink"
echo "  sudo systemctl enable --now svxlink-streamer.service"
