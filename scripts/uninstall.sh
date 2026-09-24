#!/bin/bash

set -euo pipefail

INSTALL_ROOT="/opt/Svxlink-Streamer"
SERVICE_FILE="/etc/systemd/system/svxlink-streamer.service"
SVXLINK_DROPIN_FILE="/etc/systemd/system/svxlink.service.d/audio-monitor.conf"

if [[ $EUID -ne 0 ]]; then
    echo "Run this uninstaller as root."
    exit 1
fi

echo "Svxlink-Streamer uninstaller"
echo "============================"
echo

echo "Stopping and disabling Svxlink-Streamer..."

systemctl disable --now svxlink-streamer.service 2>/dev/null || true

echo
echo "Removing streamer service..."

rm -f "${SERVICE_FILE}"

echo
echo "Removing SvxLink audio monitor drop-in..."

rm -f "${SVXLINK_DROPIN_FILE}"

echo
echo "Removing installed project files..."

rm -rf "${INSTALL_ROOT}"

echo
echo "Reloading systemd..."

systemctl daemon-reload

echo
echo "Restarting SvxLink without TX monitor preload..."

systemctl restart svxlink.service

if ! systemctl is-active --quiet svxlink.service; then
    echo "ERROR: svxlink.service failed to restart."
    systemctl status svxlink.service --no-pager -l || true
    exit 1
fi

echo "SvxLink is active."

echo
echo "Removal complete."