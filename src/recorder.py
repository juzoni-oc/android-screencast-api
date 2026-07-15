"""Recording for android-screencast-api.

Saves a device's screen to an MP4 file for a fixed duration using
``adb exec-out screenrecord`` written straight to disk.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import List, Optional


class Recorder:
    def __init__(self, out_dir: str = "./recordings"):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self._active: dict[str, asyncio.subprocess.Process] = {}

    def _default_path(self, serial: str) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = serial.replace(":", "_")
        return os.path.join(self.out_dir, f"{safe}_{ts}.mp4")

    async def start(
        self,
        serial: str,
        duration: Optional[int] = None,
        bitrate_mbps: int = 8,
        out_path: Optional[str] = None,
    ) -> str:
        """Start recording; returns the output file path. Duration in seconds."""
        if serial in self._active:
            raise RuntimeError(f"already recording {serial}")
        path = out_path or self._default_path(serial)
        cmd = [
            "adb", "-s", serial, "exec-out", "screenrecord",
            f"--bit-rate={bitrate_mbps * 1000000}",
        ]
        if duration:
            cmd.append(f"--time-limit={duration}")
        cmd += ["-"]  # stdout
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        self._active[serial] = proc

        # Stream to file in the background.
        async def _drain():
            with open(path, "wb") as fh:
                assert proc.stdout
                while True:
                    chunk = await proc.stdout.read(65536)
                    if not chunk:
                        break
                    fh.write(chunk)

        asyncio.create_task(_drain())
        return path

    async def stop(self, serial: str) -> None:
        proc = self._active.pop(serial, None)
        if proc and proc.returncode is None:
            proc.terminate()
            await proc.wait()

    def list_recordings(self) -> List[str]:
        if not os.path.isdir(self.out_dir):
            return []
        return sorted(
            os.path.join(self.out_dir, f)
            for f in os.listdir(self.out_dir)
            if f.endswith(".mp4")
        )
