#!/bin/bash

set -euo pipefail

INSTALL_ROOT="/opt/Svxlink-Streamer"
SERVICE_FILE="/etc/systemd/system/svxlink-streamer.service"
SVXLINK_DROPIN_FILE="/etc/systemd/system/svxlink.service.d/audio-monitor.conf"
CONFIG_FILE="/etc/svxlink-streamer.conf"

if [[ $EUID -ne 0 ]]; then
    echo "Run this uninstaller as root."
    exit 1
fi

echo "Stopping streamer service..."
systemctl disable --now svxlink-streamer.service 2>/dev/null || true

echo "Removing streamer service..."
rm -f "${SERVICE_FILE}"

echo "Removing SvxLink preload drop-in..."
rm -f "${SVXLINK_DROPIN_FILE}"

echo "Removing installed project files..."
rm -rf "${INSTALL_ROOT}"

echo "Reloading systemd..."
systemctl daemon-reload

echo "Restarting SvxLink without the audio monitor preload..."
systemctl restart svxlink

echo
echo "SvxLink Streamer removed."
echo
echo "Configuration has been preserved at:"
echo "  ${CONFIG_FILE}"
echo
echo "Remove it manually if no longer required."
