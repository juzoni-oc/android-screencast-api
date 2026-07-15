"""Screen capture for android-screencast-api.

Captures a live MJPEG frame stream from an Android device using
``adb exec-out screenrecord`` piped through FFmpeg. The class also yields a
clean async generator of individual JPEG frames, splitting FFmpeg's concatenated
MJPEG output on JPEG SOI/EOI markers.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, List

from .ffmpeg_pipe import FFmpegPipe, screenrecord_cmd, h264_to_mjpeg_cmd


# JPEG markers
SOI = b"\xff\xd8"
EOI = b"\xff\xd9"


def split_jpeg_frames(buffer: bytes) -> tuple[List[bytes], bytes]:
    """Split a buffer that may contain several concatenated JPEGs.

    Returns ``(complete_frames, remainder)`` where ``remainder`` is the trailing
    partial frame that should be prepended to the next chunk.
    """
    frames: List[bytes] = []
    start = 0
    while True:
        i = buffer.find(SOI, start)
        if i == -1:
            break
        j = buffer.find(EOI, i + 2)
        if j == -1:
            break
        frames.append(buffer[i : j + 2])
        start = j + 2
    return frames, buffer[start:]


class ScreenCapture:
    def __init__(self, serial: str, bitrate_mbps: int = 8, fps: int = 30):
        self.serial = serial
        self.bitrate_mbps = bitrate_mbps
        self.fps = fps
        self._adb: Optional[asyncio.subprocess.Process] = None
        self._ffmpeg: Optional[FFmpegPipe] = None

    async def _pump_adb_to_ffmpeg(self) -> None:
        """Forward raw H.264 bytes from adb into FFmpeg's stdin."""
        assert self._adb and self._adb.stdout and self._ffmpeg
        while True:
            chunk = await self._adb.stdout.read(65536)
            if not chunk:
                break
            await self._ffmpeg.write(chunk)

    async def frames(self) -> AsyncIterator[bytes]:
        """Yield individual JPEG frames until the device stops streaming."""
        self._adb = await asyncio.create_subprocess_exec(
            *screenrecord_cmd(self.serial, self.bitrate_mbps, self.fps),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._ffmpeg = FFmpegPipe(h264_to_mjpeg_cmd(self.fps))
        await self._ffmpeg.start()

        pump = asyncio.create_task(self._pump_adb_to_ffmpeg())
        remainder = b""
        try:
            while True:
                chunk = await self._ffmpeg.read(65536)
                if not chunk:
                    if self._adb.returncode is not None:
                        break
                    continue
                remainder += chunk
                complete, remainder = split_jpeg_frames(remainder)
                for frame in complete:
                    yield frame
        finally:
            pump.cancel()
            await self.stop()

    async def stop(self) -> None:
        if self._adb and self._adb.returncode is None:
            self._adb.terminate()
            await self._adb.wait()
        if self._ffmpeg:
            await self._ffmpeg.stop()

    async def single_frame(self) -> bytes:
        """Grab one screenshot (PNG) via ``screencap`` — no FFmpeg needed."""
        proc = await asyncio.create_subprocess_exec(
            "adb", "-s", self.serial, "exec-out", "screencap", "-p",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        return out
