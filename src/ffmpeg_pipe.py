"""FFmpeg process helpers for android-screencast-api.

All FFmpeg interaction goes through here so the rest of the code never has to
build command lines by hand. FFmpeg is invoked as a subprocess with pipes for
stdin/stdout, which lets us feed raw H.264 from ``adb screenrecord`` and read
back an MJPEG frame stream.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import List, Optional


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def screenrecord_cmd(
    serial: str,
    bitrate_mbps: int = 8,
    fps: int = 30,
) -> List[str]:
    """adb command that emits raw H.264 on stdout."""
    return [
        "adb",
        "-s", serial,
        "exec-out",
        "screenrecord",
        f"--bit-rate={bitrate_mbps * 1000000}",
        f"--output-format=h264",
        "-",  # stdout
    ]


def h264_to_mjpeg_cmd(fps: int = 30) -> List[str]:
    """FFmpeg command: H.264 from stdin -> MJPEG frames on stdout."""
    return [
        "ffmpeg",
        "-loglevel", "error",
        "-i", "-",                 # H.264 from stdin
        "-an",                     # no audio
        "-c:v", "mjpeg",
        "-q:v", "5",
        "-f", "mjpeg",
        "-r", str(fps),
        "-",                       # MJPEG to stdout
    ]


class FFmpegPipe:
    """Manage a long-running FFmpeg subprocess."""

    def __init__(self, args: List[str]):
        self.args = args
        self.proc: Optional[asyncio.subprocess.Process] = None

    async def start(self) -> None:
        if not ffmpeg_available():
            raise RuntimeError("ffmpeg not found on PATH")
        self.proc = await asyncio.create_subprocess_exec(
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def write(self, data: bytes) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(data)
        await self.proc.stdin.drain()

    async def read(self, n: int) -> bytes:
        assert self.proc and self.proc.stdout
        return await self.proc.stdout.read(n)

    async def stop(self) -> None:
        if self.proc and self.proc.returncode is None:
            try:
                self.proc.stdin.close()
            except Exception:
                pass
            self.proc.terminate()
            await self.proc.wait()


def transcode_to_mp4(src: str, dst: str) -> int:
    """One-shot transcode (blocking) — handy for post-processing recordings."""
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg not found on PATH")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-c:v", "libx264", "-preset", "fast", dst],
        capture_output=True,
        text=True,
    )
    return proc.returncode
