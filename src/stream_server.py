#!/usr/bin/env python3
"""HTTP streaming server for android-screencast-api.

Exposes device screens over HTTP as MJPEG streams plus recording control.

Routes
------
* ``GET /``                       HTML landing page
* ``GET /devices``               JSON list of adb devices
* ``GET /stream/{serial}``       multipart MJPEG live stream
* ``GET /snapshot/{serial}``     single JPEG snapshot
* ``POST /record/start?serial=&duration=``
* ``POST /record/stop?serial=``
* ``GET /recordings``            list saved recordings
* ``GET /healthz``               liveness probe
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
from typing import Optional

from aiohttp import web

from .screen_capture import ScreenCapture
from .recorder import Recorder

MJPEG_BOUNDARY = "frame"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))

recorder = Recorder(out_dir=os.environ.get("RECORD_DIR", "./recordings"))


async def _adb_devices() -> list[dict]:
    proc = await asyncio.create_subprocess_exec(
        "adb", "devices", "-l",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    devices = []
    for line in out.decode().splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        devices.append({"serial": parts[0], "status": parts[1] if len(parts) > 1 else "unknown"})
    return devices


async def index(request: web.Request) -> web.Response:
    html = """<html><body style='font-family:sans-serif'>
<h1>android-screencast-api</h1>
<ul>
  <li><a href='/devices'>/devices</a> — list adb devices</li>
  <li><a href='/stream/emulator-5554'>/stream/&lt;serial&gt;</a> — MJPEG live stream</li>
  <li>/snapshot/&lt;serial&gt; — single frame</li>
  <li>/recordings — saved recordings</li>
</ul></body></html>"""
    return web.Response(text=html, content_type="text/html")


async def devices(request: web.Request) -> web.Response:
    return web.json_response(await _adb_devices())


async def healthz(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def stream(request: web.Request) -> web.StreamResponse:
    serial = request.match_info["serial"]
    resp = web.StreamResponse()
    resp.content_type = "multipart/x-mixed-replace"
    resp.headers["Boundary"] = MJPEG_BOUNDARY
    await resp.prepare(request)

    cap = ScreenCapture(serial)
    try:
        async for frame in cap.frames():
            await resp.write(
                f"--{MJPEG_BOUNDARY}\r\n"
                f"Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(frame)}\r\n\r\n".encode()
            )
            await resp.write(frame)
            await resp.write(b"\r\n")
    except (asyncio.CancelledError, Exception) as exc:  # client disconnected etc.
        await cap.stop()
    return resp


async def snapshot(request: web.Request) -> web.Response:
    serial = request.match_info["serial"]
    cap = ScreenCapture(serial)
    png = await cap.single_frame()
    return web.Response(body=png, content_type="image/png")


async def record_start(request: web.Request) -> web.Response:
    qs = urllib.parse.parse_qs(request.query_string)
    serial = qs.get("serial", [""])[0]
    duration = int(qs.get("duration", [0])[0] or 0) or None
    if not serial:
        return web.json_response({"error": "serial required"}, status=400)
    path = await recorder.start(serial, duration=duration)
    return web.json_response({"serial": serial, "file": path, "status": "recording"})


async def record_stop(request: web.Request) -> web.Response:
    qs = urllib.parse.parse_qs(request.query_string)
    serial = qs.get("serial", [""])[0]
    if not serial:
        return web.json_response({"error": "serial required"}, status=400)
    await recorder.stop(serial)
    return web.json_response({"serial": serial, "status": "stopped"})


async def recordings(request: web.Request) -> web.Response:
    return web.json_response({"files": recorder.list_recordings()})


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/devices", devices)
    app.router.add_get("/stream/{serial}", stream)
    app.router.add_get("/snapshot/{serial}", snapshot)
    app.router.add_post("/record/start", record_start)
    app.router.add_post("/record/stop", record_stop)
    app.router.add_get("/recordings", recordings)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host=HOST, port=PORT)
