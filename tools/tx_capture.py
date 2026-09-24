#!/usr/bin/env python3

import os
import socket
import time

SOCKET_PATH = "/run/svxlink-audio-monitor/tx.sock"
OUTPUT_PATH = "/tmp/svxlink_tx_capture.raw"
CAPTURE_SECONDS = 15

try:
    os.unlink(SOCKET_PATH)
except FileNotFoundError:
    pass

sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
sock.bind(SOCKET_PATH)

os.chown(SOCKET_PATH, 995, 992)
os.chmod(SOCKET_PATH, 0o660)

print(f"Listening on {SOCKET_PATH}", flush=True)
print(f"Capturing {CAPTURE_SECONDS} seconds to {OUTPUT_PATH}", flush=True)

start = time.monotonic()
total = 0

with open(OUTPUT_PATH, "wb") as out:
    while time.monotonic() - start < CAPTURE_SECONDS:
        data = sock.recv(65536)
        out.write(data)
        total += len(data)

print(f"Captured {total} bytes", flush=True)
