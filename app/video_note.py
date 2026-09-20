"""To'rtburchak videoni Telegram'ning doira videosiga (video note) aylantirish."""
import asyncio
import json
import logging
from pathlib import Path

from app import config

log = logging.getLogger(__name__)


class ConvertError(RuntimeError):
    """Foydalanuvchiga ko'rsatiladigan xato."""


async def _run(*args: str) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode or 0, stdout, stderr


async def probe_duration(path: Path) -> float:
    code, out, _ = await _run(
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", str(path),
    )
    if code != 0:
        return 0.0
    try:
        return float(json.loads(out)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return 0.0


async def to_video_note(src: Path, dst: Path) -> int:
    """Videoni kvadrat qilib kesadi va qayta kodlaydi. Davomiyligini qaytaradi."""
    size = config.NOTE_SIZE
    duration = await probe_duration(src)
    limit = min(duration, config.NOTE_MAX_SECONDS) if duration else config.NOTE_MAX_SECONDS

    # Markazdan kvadrat kesib, NOTE_SIZE x NOTE_SIZE ga keltiramiz.
    vf = (
        f"crop='min(iw,ih)':'min(iw,ih)',"
        f"scale={size}:{size}:flags=lanczos,"
        f"fps=30,format=yuv420p"
    )
    code, _, stderr = await _run(
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-t", str(config.NOTE_MAX_SECONDS),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-profile:v", "main", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-ac", "1", "-ar", "44100",
        "-movflags", "+faststart",
        str(dst),
    )
    if code != 0 or not dst.exists():
        log.error("ffmpeg xatosi: %s", stderr.decode(errors="ignore")[:500])
        raise ConvertError("Videoni doira shaklga o'tkazib bo'lmadi.")

    if dst.stat().st_size > config.MAX_FILE_BYTES:
        raise ConvertError(
            f"Natija {config.MAX_FILE_MB} MB dan katta chiqdi. Qisqaroq video yuboring."
        )
    return int(limit)
