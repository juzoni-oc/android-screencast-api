# android-screencast-api

> **Live Android screen streaming & recording over HTTP** — powered by ADB +
> FFmpeg. Watch a device's screen as an MJPEG stream, grab snapshots, and record
> MP4 clips, all through a tiny HTTP API.

`android-screencast-api` pipes `adb exec-out screenrecord` (raw H.264) into
FFmpeg and serves the resulting frames over HTTP as a `multipart/x-mixed-replace`
MJPEG stream. No app install on the device, no root — just `adb` access.

## Features

- 📺 **Live MJPEG streaming** at configurable bitrate / FPS.
- 📸 **Snapshots** — one-shot `screencap` to PNG.
- 🎬 **Recording** — save an MP4 clip for a fixed duration.
- 🔌 **Device discovery** — `/devices` reflects `adb devices -l`.
- 🐳 Single-container Docker image (ADB + FFmpeg included).

## Requirements

- Python 3.8+
- `adb` (Android platform tools) on `PATH` (or in the container)
- `ffmpeg` on `PATH`

## Install & run

```bash
pip install -r requirements.txt
python -m src.stream_server
# open http://localhost:8080/
```

With Docker:

```bash
docker build -t android-screencast-api .
docker run --rm -p 8080:8080 \
  -v /path/to/recordings:/recordings \
  android-screencast-api
```

## Usage

```bash
# List connected devices
curl http://localhost:8080/devices

# Live stream (open in a browser or VLC)
#   http://localhost:8080/stream/emulator-5554

# Single snapshot
curl http://localhost:8080/snapshot/emulator-5554 -o shot.png

# Start a 30s recording, then stop early if you like
curl -X POST "http://localhost:8080/record/start?serial=emulator-5554&duration=30"
curl -X POST "http://localhost:8080/record/stop?serial=emulator-5554"
curl http://localhost:8080/recordings
```

## API reference

| Route                          | Method | Description                       |
|--------------------------------|--------|-----------------------------------|
| `/`                            | GET    | HTML landing page                 |
| `/healthz`                     | GET    | liveness probe                    |
| `/devices`                     | GET    | JSON list of adb devices          |
| `/stream/{serial}`             | GET    | MJPEG live stream                 |
| `/snapshot/{serial}`           | GET    | single PNG snapshot               |
| `/record/start?serial=&duration=` | POST | start recording                 |
| `/record/stop?serial=`         | POST   | stop recording                    |
| `/recordings`                  | GET    | list saved recordings             |

## Project layout

```
android-screencast-api/
├── src/
│   ├── stream_server.py   # HTTP streaming server (aiohttp)
│   ├── screen_capture.py  # screen capture (adb + ffmpeg)
│   ├── ffmpeg_pipe.py     # FFmpeg pipeline helpers
│   └── recorder.py        # recording to MP4
├── Dockerfile
├── requirements.txt
└── README.md
```

## Contact

Maintained by **juzoni-oc**. For hosted device streaming, cloud screen-cast
services or custom device-API integrations, contact
**[qtphone.com](https://qtphone.com)**.

## License

MIT
