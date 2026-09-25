#!/usr/bin/env python3

from pathlib import Path
import sys


DASHBOARD_ROOT = Path("/opt/dashboard")

APP_PATH = DASHBOARD_ROOT / "app.py"
STATUS_PATH = DASHBOARD_ROOT / "templates" / "status.html"
CSS_PATH = DASHBOARD_ROOT / "static" / "site.css"


def replace_once(text, old, new, description):
    count = text.count(old)

    if count == 0:
        raise RuntimeError(
            f"Cannot locate expected {description}."
        )

    if count > 1:
        raise RuntimeError(
            f"Expected one {description}, found {count}."
        )

    return text.replace(old, new, 1)


def patch_app(path):
    text = path.read_text(encoding="utf-8")

    text = text.replace(
        "http://127.0.0.1:8765/health",
        "http://127.0.0.1:8766/health",
    )

    text = text.replace(
        "http://127.0.0.1:8765/stream.mp3",
        "http://127.0.0.1:8766/stream.mp3",
    )

    if "def streamer_is_available():" not in text:
        old = (
            "from flask import Flask, render_template, request, "
            "redirect, session, url_for, jsonify"
        )

        new = (
            "from flask import (\n"
            "    Flask,\n"
            "    Response,\n"
            "    jsonify,\n"
            "    redirect,\n"
            "    render_template,\n"
            "    request,\n"
            "    session,\n"
            "    url_for,\n"
            ")"
        )

        text = replace_once(
            text,
            old,
            new,
            "Flask import",
        )

        old = "import datetime \nfrom datetime import timedelta"

        new = (
            "import datetime\n"
            "import json\n"
            "import urllib.error\n"
            "import urllib.request\n"
            "from datetime import timedelta"
        )

        text = replace_once(
            text,
            old,
            new,
            "standard-library import block",
        )

        anchor = (
            '@app.route("/status", methods=["GET"])\n'
            "def status_page():"
        )

        helper = '''
STREAMER_HEALTH_URL = "http://127.0.0.1:8766/health"
STREAMER_AUDIO_URL = "http://127.0.0.1:8766/stream.mp3"


def streamer_is_available():
    try:
        with urllib.request.urlopen(
            STREAMER_HEALTH_URL,
            timeout=0.25,
        ) as response:
            if response.status != 200:
                return False

            data = json.load(response)

        return data.get("status") == "ok"

    except (
        OSError,
        ValueError,
        urllib.error.URLError,
    ):
        return False


@app.route("/stream/live.mp3", methods=["GET"])
def live_stream():
    try:
        upstream = urllib.request.urlopen(
            STREAMER_AUDIO_URL,
            timeout=2,
        )
    except (OSError, urllib.error.URLError):
        return Response(
            "Live stream unavailable\\n",
            status=503,
            mimetype="text/plain",
        )

    def generate():
        try:
            while True:
                chunk = upstream.read(4096)

                if not chunk:
                    break

                yield chunk
        finally:
            upstream.close()

    return Response(
        generate(),
        mimetype="audio/mpeg",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/status", methods=["GET"])
def status_page():
'''

        text = replace_once(
            text,
            anchor,
            helper.strip("\n"),
            "status route",
        )

    availability_marker = "streamer_available = ("

    if availability_marker not in text:
        old = '''    if not enabled_ports:
        enabled_ports = ["1"]

    selected_port = request.args.get("port", enabled_ports[0])
'''

        new = '''    if not enabled_ports:
        enabled_ports = ["1"]

    streamer_available = (
        len(enabled_ports) == 1
        and streamer_is_available()
    )

    selected_port = request.args.get("port", enabled_ports[0])
'''

        text = replace_once(
            text,
            old,
            new,
            "enabled-port status block",
        )

    if "streamer_available=streamer_available," not in text:
        old = "        port_count=len(enabled_ports),\n"

        new = (
            "        port_count=len(enabled_ports),\n"
            "        streamer_available=streamer_available,\n"
        )

        text = replace_once(
            text,
            old,
            new,
            "status template arguments",
        )

    path.write_text(text, encoding="utf-8")


def patch_status(path):
    text = path.read_text(encoding="utf-8")

    if 'class="live-stream-status"' not in text:
        old = '''        <div class="dashboard-header">
            <h1 class="status-title">
'''

        new = '''        <div class="dashboard-header">

            {% if port_count == 1 %}
            <div class="live-stream-status">
                <div class="live-stream-title">
                    Live Stream
                </div>

                {% if streamer_available %}
                <button
                    type="button"
                    class="button-secondary live-stream-button"
                    id="live-stream-button"
                >
                    Listen
                </button>
                {% else %}
                <button
                    type="button"
                    class="button-secondary live-stream-button"
                    disabled
                >
                    Not Fitted
                </button>
                {% endif %}
            </div>
            {% endif %}

            <h1 class="status-title">
'''

        text = replace_once(
            text,
            old,
            new,
            "dashboard header",
        )

    if 'id="live-stream-audio"' not in text:
        old = '''        </div>
        {% include "navbar.html" %}
'''

        new = '''        </div>

        {% if port_count == 1 and streamer_available %}
        <audio
            id="live-stream-audio"
            preload="none"
            src="{{ url_for('live_stream') }}"
            hidden
        ></audio>
        {% endif %}

        {% include "navbar.html" %}
'''

        text = replace_once(
            text,
            old,
            new,
            "dashboard header closing block",
        )

    if 'button.textContent = "Stop";' not in text:
        old = "</body>"

        script = '''{% if port_count == 1 and streamer_available %}
<script>
document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("live-stream-button");
    const audio = document.getElementById("live-stream-audio");

    if (!button || !audio) {
        return;
    }

    let playing = false;

    button.addEventListener("click", () => {
        if (!playing) {
            const playPromise = audio.play();

            if (
                playPromise &&
                typeof playPromise.then === "function"
            ) {
                playPromise
                    .then(() => {
                        playing = true;
                        button.textContent = "Stop";
                    })
                    .catch(() => {});
            }

            return;
        }

        audio.pause();
        audio.currentTime = 0;
        playing = false;
        button.textContent = "Listen";
    });
});
</script>
{% endif %}

</body>'''

        text = replace_once(
            text,
            old,
            script,
            "body closing tag",
        )

    path.write_text(text, encoding="utf-8")


def patch_css(path):
    text = path.read_text(encoding="utf-8")

    if "position: relative;" not in text[
        text.find(".dashboard-header {"):
        text.find(".dashboard-header {") + 250
    ]:
        old = '''.dashboard-header {
    background: #0000ff;
'''

        new = '''.dashboard-header {
    position: relative;
    background: #0000ff;
'''

        text = replace_once(
            text,
            old,
            new,
            "dashboard-header CSS",
        )

    if ".live-stream-status {" not in text:
        anchor = '''.dashboard-header {
    position: relative;
    background: #0000ff;
    color: #ffffff;
    text-align: center;
    padding: 10px;
    border-radius: 10px;
    box-shadow: 2px 2px 8px #303030;
}
'''

        addition = anchor + '''
.live-stream-status {
    position: absolute;
    top: 18px;
    right: 22px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.35rem;
}

.live-stream-title {
    color: #ffffff;
    font-weight: 800;
}

.live-stream-button {
    min-height: 40px;
    padding: 0 1rem;
    cursor: default;
    opacity: 0.75;
}

@media (max-width: 720px) {
    .live-stream-status {
        position: static;
        margin-top: 0.75rem;
    }
}
'''

        text = replace_once(
            text,
            anchor,
            addition,
            "dashboard-header CSS block",
        )

    path.write_text(text, encoding="utf-8")


def main():
    paths = (
        APP_PATH,
        STATUS_PATH,
        CSS_PATH,
    )

    missing = [
        str(path)
        for path in paths
        if not path.is_file()
    ]

    if missing:
        print(
            "ERROR: required V4 dashboard files are missing:",
            file=sys.stderr,
        )

        for path in missing:
            print(f"  {path}", file=sys.stderr)

        return 1

    original = {
        path: path.read_bytes()
        for path in paths
    }

    try:
        patch_app(APP_PATH)
        patch_status(STATUS_PATH)
        patch_css(CSS_PATH)

    except Exception as exc:
        for path, contents in original.items():
            path.write_bytes(contents)

        print(
            f"ERROR: dashboard retrofit aborted: {exc}",
            file=sys.stderr,
        )
        print(
            "No dashboard files were changed.",
            file=sys.stderr,
        )
        return 1

    print("V4 dashboard streamer retrofit applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
