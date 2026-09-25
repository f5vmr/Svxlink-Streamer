#!/usr/bin/env python3

import os
import queue
import socket
import subprocess
import threading
import time

from flask import Flask, Response

SOCKET_PATH = "/run/svxlink-audio-monitor/tx.sock"

PCM_RATE = "48000"
PCM_CHANNELS = "2"
PCM_SAMPLE_BYTES = 2
SILENCE_INTERVAL = 0.02

SILENCE_BYTES = (
    int(PCM_RATE)
    * int(PCM_CHANNELS)
    * PCM_SAMPLE_BYTES
    * SILENCE_INTERVAL
)

SILENCE_CHUNK = bytes(int(SILENCE_BYTES))

HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8766

STREAM_BITRATE = "32k"

app = Flask(__name__)

listeners = set()
listeners_lock = threading.Lock()


def build_ffmpeg_command():
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
        # stream the left TX channel only.
        "-map_channel",
        "0.0.0",
        "-ac",
        "1",

        "-codec:a",
        "libmp3lame",
        "-b:a",
        STREAM_BITRATE,

        "-f",
        "mp3",
        "pipe:1",
    ]


def open_audio_socket():
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
    sock.settimeout(SILENCE_INTERVAL)

    return sock


def start_encoder():
    return subprocess.Popen(
        build_ffmpeg_command(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        bufsize=0,
    )


def publish_mp3(data):
    dead = []

    with listeners_lock:
        for listener in listeners:
            try:
                listener.put_nowait(data)
            except queue.Full:
                dead.append(listener)

        for listener in dead:
            listeners.discard(listener)


def encoder_output_worker(encoder):
    while True:
        data = encoder.stdout.read(4096)

        if not data:
            break

        publish_mp3(data)


def audio_worker():
    sock = open_audio_socket()

    print(
        f"Listening for SvxLink TX audio on {SOCKET_PATH}",
        flush=True,
    )

    while True:
        encoder = start_encoder()

        output_thread = threading.Thread(
            target=encoder_output_worker,
            args=(encoder,),
            daemon=True,
        )
        output_thread.start()

        try:
            while encoder.poll() is None:
                try:
                    data = sock.recv(65536)
                except socket.timeout:
                    data = SILENCE_CHUNK

                try:
                    encoder.stdin.write(data)
                except (BrokenPipeError, OSError):
                    break

        finally:
            try:
                encoder.kill()
            except OSError:
                pass

            try:
                encoder.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

        time.sleep(1)


def stream_generator():
    listener = queue.Queue(maxsize=64)

    with listeners_lock:
        listeners.add(listener)

    try:
        while True:
            data = listener.get()
            yield data

    finally:
        with listeners_lock:
            listeners.discard(listener)


@app.route("/stream.mp3")
def stream():
    return Response(
        stream_generator(),
        mimetype="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.route("/health")
def health():
    with listeners_lock:
        listener_count = len(listeners)

    return {
        "status": "ok",
        "listeners": listener_count,
        "stream": "/stream.mp3",
    }


def main():
    worker = threading.Thread(
        target=audio_worker,
        daemon=True,
    )
    worker.start()

    app.run(
        host=HTTP_HOST,
        port=HTTP_PORT,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
