# Svxlink-Streamer

`Svxlink-Streamer` provides a lightweight live audio stream of the complete
SvxLink transmitter audio path.

It was developed as a replacement for the earlier WebSocket-based audio
monitor used with previous versions of SvxLink-Dash.

The streamer operates independently of the dashboard and does **not** require
changes to `svxlink.conf`.

The current implementation is intended for **single-node Simplex and Repeater
installations**.

Multi-port and ICS installations are deliberately excluded from the supported
scope at this stage.

---

## Overview

Svxlink-Streamer creates a copy of the final PCM audio that SvxLink sends to
the transmitter.

The normal transmitter audio path remains unchanged.

```text
SvxLink
   │
   ▼
libasyncaudio
   │
   ▼
snd_pcm_writei()
   │
   ├──────────────► ALSA ► Radio transmitter
   │
   └──────────────► Svxlink-Streamer TX tap
                           │
                           ▼
                    Unix datagram socket
                           │
                           ▼
                        ffmpeg
                           │
                           ▼
                         MP3
                           │
                           ▼
                    Local Flask stream
```

The monitoring path is deliberately non-blocking.

If the streamer is stopped, unavailable, or unable to receive audio, the
normal SvxLink transmitter path continues operating.

---

## Design Goals

The project was designed around several requirements:

- Do not modify `svxlink.conf`.
- Do not use `MultiTx` solely for streaming.
- Do not alter ALSA mixer settings.
- Do not interfere with the normal transmitter path.
- Do not expose an additional streaming port directly to remote browsers.
- Keep the audio streamer independent of SvxLink-Dash.
- Allow the streamer service to stop or restart without affecting radio
  operation.
- Keep dashboard configuration actions independent of the audio stream.
- Provide substantially lower startup latency than the previous streaming
  arrangement.
- Allow installation and removal without rebuilding the SvxLink
  configuration.

---

## Current Supported Scope

The current release is intended for:

- Single-node Simplex installations.
- Single-node Repeater installations.
- ALSA-backed local transmitters.
- SvxLink installations using `libasyncaudio`.
- Systems where SvxLink ultimately writes transmitter PCM using
  `snd_pcm_writei()`.

The development and field testing has so far used conventional single-node
ALSA audio paths such as CM108/CM119-style USB sound devices.

The tested PCM format is:

```text
Format:       S16_LE
Channels:     2
Sample rate:  48000 Hz
Access:       RW_INTERLEAVED
```

SvxLink commonly places the configured transmit audio on channel 0.

The streamer therefore selects the first channel and converts the stream to
mono MP3.

---

## Multi-Port and ICS Systems

Multi-port and ICS installations are **not currently supported**.

The underlying interception method is expected to be applicable to other ALSA
devices, but ICS installations can use significantly more complicated ALSA
routing, including:

- multi-channel PCM devices;
- named ALSA devices;
- `route` plugins;
- `ttable` mappings;
- multiple simultaneous transmitter paths;
- different PCM sample formats and channel counts.

These systems require separate validation before support is enabled.

SvxLink-Dash therefore deliberately hides the Live Stream control on
multi-port installations.

---

## How the TX Tap Works

SvxLink dynamically links against `libasyncaudio` and ALSA.

The tested `libasyncaudio` implementation uses:

```text
snd_pcm_open()
snd_pcm_prepare()
snd_pcm_writei()
snd_pcm_start()
snd_pcm_close()
```

Svxlink-Streamer provides a small preload library which intercepts
`snd_pcm_writei()`.

The real ALSA function is always called first.

Only frames that ALSA reports as successfully accepted are copied to the
streaming path.

```text
SvxLink TX audio
        │
        ▼
snd_pcm_writei()
        │
        ├── real ALSA playback
        │
        └── non-blocking monitor copy
```

The tap communicates with the streamer using a Unix datagram socket:

```text
/run/svxlink-audio-monitor/tx.sock
```

Unix datagrams were selected so that:

- the SvxLink process never waits for the streamer;
- no FIFO reader is required;
- streamer restarts do not affect SvxLink;
- a missing receiver simply causes the monitor copy to be discarded;
- the radio path remains authoritative.

---

## LD_PRELOAD Integration

The TX tap is loaded into SvxLink using a systemd drop-in.

The original SvxLink service file is not modified.

Installed drop-in:

```text
/etc/systemd/system/svxlink.service.d/audio-monitor.conf
```

The drop-in supplies:

```ini
[Service]
Environment="LD_PRELOAD=/opt/Svxlink-Streamer/libsvxlink_tx_tap.so"
```

Removing this drop-in restores normal SvxLink operation without the streamer.

---

## Audio Encoding

The streamer receives raw PCM audio from the TX tap and passes it to
`ffmpeg`.

Current encoding is:

```text
Input:
    S16_LE
    48000 Hz
    stereo

Selected channel:
    channel 0

Output:
    mono MP3
    32 kbit/s
```

A single encoder process is used.

Multiple browser listeners consume the same encoded MP3 stream rather than
starting separate encoder processes.

---

## HTTP Service

The streamer provides a small local Flask service.

It listens only on:

```text
127.0.0.1:8766
```

The two principal endpoints are:

```text
http://127.0.0.1:8766/health
http://127.0.0.1:8766/stream.mp3
```

The health endpoint returns JSON similar to:

```json
{
  "listeners": 0,
  "status": "ok",
  "stream": "/stream.mp3"
}
```

The MP3 endpoint provides the continuous encoded transmitter audio.

The local Flask service is **not intended to be exposed directly to the
network**.

---

## SvxLink-Dash V4.0 Integration

SvxLink-Dash V4.0 acts as the external interface to the streamer.

The dashboard checks:

```text
http://127.0.0.1:8766/health
```

to determine whether the streamer is available.

The dashboard then provides a same-origin proxy:

```text
/stream/live.mp3
```

which internally connects to:

```text
http://127.0.0.1:8766/stream.mp3
```

This means the browser always uses the same hostname, address, port and
protocol that it used to access the dashboard.

For example:

```text
http://192.168.1.214:5000/status
```

uses:

```text
http://192.168.1.214:5000/stream/live.mp3
```

A remotely accessed dashboard therefore does not need direct access to port
`8766`.

This also avoids mixed-content problems where the dashboard may later be
served using HTTPS.

---

## Dashboard Status Page

On supported single-node installations, the V4 Status page displays a compact
Live Stream control in the title header.

When the streamer is unavailable:

```text
Live Stream
[ Not Fitted ]
```

When available:

```text
Live Stream
[ Listen ]
```

While playing:

```text
Live Stream
[ Stop ]
```

The HTML5 audio element itself is hidden.

This avoids the native browser audio controls changing the dashboard layout.

Multi-port installations display no Live Stream control.

---

## Stream Latency

Field testing has shown typical startup latency of approximately:

```text
1–2 seconds
```

This is substantially shorter than the previous streaming arrangement, which
could occasionally approach ten seconds.

Latency depends on:

- browser buffering;
- MP3 frame generation;
- network conditions;
- host CPU performance.

The current settings favour reliability over extreme low-latency tuning.

---

## Repository Layout

```text
Svxlink-Streamer/
├── Makefile
├── README.md
├── scripts/
│   ├── install.sh
│   ├── retrofit-v4.py
│   ├── retrofit-v4.sh
│   └── uninstall.sh
├── src/
│   └── svxlink_tx_tap.c
├── streamer/
│   └── svxlink_streamer.py
├── systemd/
│   ├── svxlink-streamer.service
│   └── svxlink.service.d/
│       └── audio-monitor.conf
└── tools/
    └── tx_capture.py
```

Generated shared libraries are not stored in Git.

The repository `.gitignore` excludes:

```text
*.so
.DS_Store
__pycache__/
*.pyc
```

---

## Building

The TX tap is built using the supplied `Makefile`.

On a supported Linux system:

```bash
make
```

Validation:

```bash
make check
```

Remove the generated library:

```bash
make clean
```

The project should normally be edited in the development repository and built
on the target Linux system.

The ALSA tap cannot be compiled natively on macOS because the required Linux
ALSA development environment is not present.

---

## Required Packages

The installer installs the required packages automatically.

These include:

```text
ffmpeg
python3-flask
build-essential
libasound2-dev
```

The system must also have a working SvxLink installation.

---

## Standalone Installation

Clone the repository:

```bash
git clone https://github.com/f5vmr/Svxlink-Streamer.git
cd Svxlink-Streamer
```

Run:

```bash
sudo ./scripts/install.sh
```

The installer:

1. installs required packages;
2. builds the TX tap library;
3. installs files under `/opt/Svxlink-Streamer`;
4. installs the streamer systemd service;
5. installs the SvxLink systemd preload drop-in;
6. reloads systemd;
7. restarts SvxLink;
8. enables and starts `svxlink-streamer.service`;
9. verifies the local health endpoint.

Installed application directory:

```text
/opt/Svxlink-Streamer
```

---

## Systemd Services

The normal SvxLink service remains:

```text
svxlink.service
```

The streamer runs independently as:

```text
svxlink-streamer.service
```

Check the streamer:

```bash
sudo systemctl status svxlink-streamer --no-pager -l
```

Check SvxLink:

```bash
sudo systemctl status svxlink --no-pager -l
```

View streamer logs:

```bash
sudo journalctl -u svxlink-streamer -n 100 --no-pager
```

---

## Health Check

The local health endpoint can be tested with Python:

```bash
python3 - <<'PY'
import json
import urllib.request

with urllib.request.urlopen(
    "http://127.0.0.1:8766/health",
    timeout=2,
) as response:
    print(json.load(response))
PY
```

Expected result:

```text
{'listeners': 0, 'status': 'ok', 'stream': '/stream.mp3'}
```

---

## Testing the Local MP3 Stream

The local stream can be tested directly:

```bash
python3 - <<'PY'
import urllib.request

with urllib.request.urlopen(
    "http://127.0.0.1:8766/stream.mp3",
    timeout=5,
) as response:
    print(response.status)
    print(response.headers.get_content_type())

    data = response.read(4096)

    print(f"{len(data)} bytes received")
PY
```

Expected result:

```text
200
audio/mpeg
4096 bytes received
```

---

## TX Capture Diagnostic

`tools/tx_capture.py` is retained as a diagnostic utility.

It can be used to verify the raw TX tap independently of the MP3 encoder and
Flask streamer.

The captured PCM format for the currently supported simple-node profile is:

```text
S16_LE
48000 Hz
2 channels
```

A raw capture can be converted to WAV using SoX:

```bash
sox \
    -t raw \
    -r 48000 \
    -e signed-integer \
    -b 16 \
    -c 2 \
    -L \
    /tmp/svxlink_tx_capture.raw \
    /tmp/svxlink_tx_capture.wav
```

The resulting WAV can then be inspected using:

```bash
sox /tmp/svxlink_tx_capture.wav -n stat
```

---

## Existing SvxLink-Dash V4.0 Installations

Existing configured V4.0 installations should **not** rerun the complete V4
installer simply to gain streaming support.

The repository therefore provides a dedicated retrofit path.

Run:

```bash
sudo ./scripts/retrofit-v4.sh
```

The retrofit process:

1. verifies the expected V4 dashboard files exist;
2. backs up the existing dashboard files;
3. installs Svxlink-Streamer;
4. patches the required V4 dashboard integration;
5. checks Python syntax;
6. restarts only `svxlink-dash.service`;
7. validates the local Status page;
8. rolls the dashboard files back automatically if validation fails.

The existing SvxLink configuration and V4 node model are not rebuilt.

Backups are stored beneath:

```text
/var/backups/svxlink-streamer-v4/
```

---

## New SvxLink-Dash V4.0 Installations

Current SvxLink-Dash V4.0 installations automatically install
Svxlink-Streamer.

The V4 installer:

1. installs its normal dashboard dependencies;
2. temporarily clones the Svxlink-Streamer repository;
3. runs the streamer's own `scripts/install.sh`;
4. removes the temporary source checkout;
5. continues with the normal V4 installation.

Svxlink-Streamer therefore remains responsible for its own installation
logic.

The V4 installer does not duplicate the streamer's package, build or systemd
configuration.

---

## Uninstalling

To remove Svxlink-Streamer:

```bash
sudo ./scripts/uninstall.sh
```

The uninstaller:

1. stops and disables `svxlink-streamer.service`;
2. removes the streamer service;
3. removes the SvxLink preload drop-in;
4. removes `/opt/Svxlink-Streamer`;
5. reloads systemd;
6. restarts SvxLink without the TX audio tap;
7. verifies SvxLink is active.

The normal radio path is restored without changing `svxlink.conf`.

---

## Failure Behaviour

The monitoring path is deliberately fail-safe.

If any of the following fail:

```text
Svxlink-Streamer
ffmpeg
Flask
the Unix socket
the dashboard
the browser connection
```

the radio transmitter path remains independent.

The TX tap always services the real ALSA playback operation first.

Streaming failures must never delay or alter the audio delivered to the radio.

---

## Security Model

The streamer HTTP service binds only to:

```text
127.0.0.1
```

It is therefore not directly exposed to the network.

Remote listening is provided through the existing SvxLink-Dash HTTP service.

This avoids:

- another externally reachable TCP service;
- additional authentication configuration;
- direct access to the internal streamer;
- hard-coded node addresses;
- separate streaming host configuration.

---

## Development Status

The following has been successfully demonstrated:

- TX-side PCM interception using `snd_pcm_writei()`;
- complete SvxLink outbound programme capture;
- Simplex operation;
- Repeater operation;
- continuous zero-filled Repeater playback behaviour;
- non-blocking Unix datagram transport;
- MP3 encoding with ffmpeg;
- local Flask streaming;
- V4 dashboard health detection;
- V4 same-origin MP3 proxying;
- compact Listen/Stop dashboard control;
- approximately 1–2 second stream startup;
- standalone installation;
- V4 retrofit installation on an existing remote repeater;
- automatic integration into new V4 installations.

---

## Known Limitations

The current implementation does not yet claim support for:

- multi-port V4 installations;
- ICS 2x/4x/8x multi-channel audio paths;
- multiple simultaneous TX stream selection;
- arbitrary ALSA PCM formats;
- per-port streaming;
- browser volume controls within the custom dashboard control.

These areas may be investigated in later releases.

---

## Project Philosophy

Svxlink-Streamer is intended to remain a bolt-on facility.

SvxLink remains responsible for radio operation.

Svxlink-Streamer observes the final transmitter audio and provides a monitoring
copy.

SvxLink-Dash presents that stream to the user but does not own or control the
radio audio path.

This separation is intentional.

---

## Credits

SvxLink© is written and maintained by Tobias Blomberg, SM0SVX.

Svxlink-Streamer was developed as an additional monitoring facility for
SvxLink-Dash© V4.0 both written by Chris JACKSON G4NAB for SvxLink-based nodes.

---

## Licence

Svxlink-Streamer© should be distributed under the licence selected for the
project repository.

The SvxLink project itself is separate software and remains subject to its own
licensing terms.