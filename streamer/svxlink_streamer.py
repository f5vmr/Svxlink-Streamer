#!/usr/bin/env python3

import configparser
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

SOCKET_PATH = "/run/svxlink-audio-monitor/tx.sock"
CONFIG_PATH = "/etc/svxlink-streamer.conf"

PCM_RATE = "48000"
PCM_CHANNELS = "2"


def load_config():
    config = configparser.ConfigParser()

    if not config.read(CONFIG_PATH):
        raise RuntimeError(f"Cannot read {CONFIG_PATH}")

    if "stream" not in config:
        raise RuntimeError(f"Missing [stream] section in {CONFIG_PATH}")

    section = config["stream"]

    required = (
        "host",
        "port",
        "mount",
        "password",
    )

    missing = [
        key
        for key in required
        if not section.get(key, "").strip()
    ]

    if missing:
        raise RuntimeError(
            "Missing configuration value(s): "
            + ", ".join(missing)
        )

    return section


def build_ffmpeg_command(stream):
    host = stream["host"].strip()
    port = stream["port"].strip()
    mount = stream["mount"].strip().lstrip("/")
    password = stream["password"]

    bitrate = stream.get("bitrate", "32k").strip()
    name = stream.get("name", "SvxLink TX").strip()

    destination = (
        f"icecast://source:{password}"
        f"@{host}:{port}/{mount}"
    )

    return [
        "/usr/bin/ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",

        "-f",
        "s16le",
        "-ar",
        PCM_RATE,
        "-ac",
        PCM_CHANNELS,
        "-i",
        "pipe:0",

        # SvxLink AUDIO_CHANNEL=0:
        # use the left TX channel only.
        "-af",
        "pan=mono|c0=c0",

        "-codec:a",
        "libmp3lame",
        "-b:a",
        bitrate,

        "-content_type",
        "audio/mpeg",

        "-ice_name",
        name,

        "-f",
        "mp3",

        destination,
    ]


def open_socket():
    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass

    sock = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_DGRAM,
    )

    sock.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o660)

    return sock


def start_encoder(command):
    return subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        bufsize=0,
    )


def main():
    stream = load_config()
    command = build_ffmpeg_command(stream)

    sock = open_socket()

    print(
        f"Listening for SvxLink TX audio on {SOCKET_PATH}",
        flush=True,
    )

    encoder = start_encoder(command)

    try:
        while True:
            data = sock.recv(65536)

            if encoder.poll() is not None:
                print(
                    "Encoder stopped; restarting",
                    file=sys.stderr,
                    flush=True,
                )

                encoder = start_encoder(command)

            try:
                encoder.stdin.write(data)
            except (BrokenPipeError, OSError):
                try:
                    encoder.kill()
                except OSError:
                    pass

                time.sleep(1)
                encoder = start_encoder(command)

    finally:
        if encoder.poll() is None:
            encoder.terminate()

        sock.close()
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
