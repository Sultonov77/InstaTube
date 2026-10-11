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


async def ffmpeg_version() -> str:
    """ffmpeg mavjudligini tekshiradi. Topilmasa bo'sh satr qaytaradi."""
    try:
        code, out, _ = await _run("ffmpeg", "-version")
    except FileNotFoundError:
        return ""
    if code != 0:
        return ""
    return out.decode(errors="ignore").splitlines()[0]


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


async def video_codec(path: Path) -> str:
    code, out, _ = await _run(
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-select_streams", "v:0", "-show_streams", str(path),
    )
    if code != 0:
        return ""
    try:
        return json.loads(out)["streams"][0]["codec_name"]
    except (KeyError, IndexError, ValueError, json.JSONDecodeError):
        return ""


async def ensure_h264(path: Path) -> Path:
    """Video H.264 bo'lmasa (AV1, VP9...), Telegram o'ynatishi uchun qayta kodlaydi.

    Aks holda Telegram videoni bitta qotgan rasm qilib ko'rsatadi.
    """
    codec = await video_codec(path)
    if codec == "h264":
        return path

    log.info("Video kodeki %s — H.264 ga o'girilmoqda: %s", codec or "noma'lum", path.name)
    dst = path.with_name(f"{path.stem}-h264.mp4")
    code, _, stderr = await _run(
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(path),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(dst),
    )
    if code != 0 or not dst.exists():
        log.error("H.264 ga o'girib bo'lmadi: %s", stderr.decode(errors="ignore")[:500])
        return path
    path.unlink(missing_ok=True)
    return dst


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
