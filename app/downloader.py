"""YouTube va Instagram'dan video yuklab olish (yt-dlp orqali)."""
import asyncio
import logging
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from app import config

log = logging.getLogger(__name__)

YOUTUBE_RE = re.compile(
    r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch|shorts|live|embed)\S*"
    r"|youtu\.be/\S+)",
    re.IGNORECASE,
)
INSTAGRAM_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv|share)/\S+",
    re.IGNORECASE,
)


class DownloadError(RuntimeError):
    """Foydalanuvchiga ko'rsatiladigan xato."""


@dataclass
class Downloaded:
    path: Path
    title: str
    duration: int
    width: int
    height: int
    source: str
    workdir: Path

    def cleanup(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


def find_link(text: str) -> tuple[str, str] | None:
    """Matndan qo'llab-quvvatlanadigan havolani topadi -> (url, manba)."""
    if match := YOUTUBE_RE.search(text):
        return match.group(0), "YouTube"
    if match := INSTAGRAM_RE.search(text):
        return match.group(0), "Instagram"
    return None


def _cookie_file(workdir: Path) -> str | None:
    if not config.INSTAGRAM_COOKIES.strip():
        return None
    path = workdir / "cookies.txt"
    path.write_text(config.INSTAGRAM_COOKIES.replace("\n", "\n"), encoding="utf-8")
    return str(path)


def _ydl_options(workdir: Path) -> dict:
    opts = {
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "format": (
            f"best[ext=mp4][filesize<{config.MAX_FILE_MB}M]"
            f"/bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]"
            f"/best[height<=1080]/best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "retries": 3,
        "socket_timeout": 30,
        "concurrent_fragment_downloads": 4,
        "postprocessors": [
            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
        ],
    }
    if cookies := _cookie_file(workdir):
        opts["cookiefile"] = cookies
    return opts


def _download_sync(url: str) -> Downloaded:
    workdir = Path(tempfile.mkdtemp(prefix=f"dl-{uuid.uuid4().hex[:8]}-", dir=config.WORK_DIR))
    try:
        with yt_dlp.YoutubeDL(_ydl_options(workdir)) as ydl:
            info = ydl.extract_info(url, download=True)
        if info.get("entries"):
            info = info["entries"][0]

        files = sorted(
            (p for p in workdir.iterdir() if p.is_file() and p.suffix != ".txt"),
            key=lambda p: p.stat().st_size,
            reverse=True,
        )
        if not files:
            raise DownloadError("Video yuklab olinmadi.")

        video = files[0]
        if video.stat().st_size > config.MAX_FILE_BYTES:
            raise DownloadError(
                f"Video hajmi {config.MAX_FILE_MB} MB dan katta — Telegram bunday "
                "faylni yuborishga ruxsat bermaydi."
            )

        return Downloaded(
            path=video,
            title=(info.get("title") or "Video")[:200],
            duration=int(info.get("duration") or 0),
            width=int(info.get("width") or 0),
            height=int(info.get("height") or 0),
            source=info.get("extractor_key") or "",
            workdir=workdir,
        )
    except DownloadError:
        shutil.rmtree(workdir, ignore_errors=True)
        raise
    except yt_dlp.utils.DownloadError as err:
        shutil.rmtree(workdir, ignore_errors=True)
        log.warning("yt-dlp xatosi: %s", err)
        raise DownloadError(_humanize(str(err))) from err
    except Exception as err:  # noqa: BLE001
        shutil.rmtree(workdir, ignore_errors=True)
        log.exception("Yuklashda kutilmagan xato")
        raise DownloadError("Videoni yuklab bo'lmadi. Havolani tekshirib qayta urining.") from err


def _humanize(raw: str) -> str:
    low = raw.lower()
    if "private" in low or "login" in low or "cookies" in low:
        return "Bu post yopiq (private) yoki login talab qiladi — uni yuklab bo'lmaydi."
    if "unavailable" in low or "not exist" in low or "404" in low:
        return "Video topilmadi yoki o'chirilgan."
    if "age" in low and "restrict" in low:
        return "Video yosh chekloviga ega, yuklab bo'lmaydi."
    if "copyright" in low or "blocked" in low:
        return "Video mualliflik huquqi sababli bloklangan."
    return "Videoni yuklab bo'lmadi. Havolani tekshirib qayta urining."


async def download(url: str) -> Downloaded:
    Path(config.WORK_DIR).mkdir(parents=True, exist_ok=True)
    return await asyncio.to_thread(_download_sync, url)
