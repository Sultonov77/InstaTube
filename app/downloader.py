"""Instagram'dan video yuklab olish (yt-dlp orqali)."""
import asyncio
import logging
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from app import config, video_note

log = logging.getLogger(__name__)

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
    """Matndan Instagram havolasini topadi -> (url, manba)."""
    if match := INSTAGRAM_RE.search(text):
        return match.group(0), "Instagram"
    return None


def _cookie_file(workdir: Path) -> str | None:
    raw = config.INSTAGRAM_COOKIES
    if not raw.strip():
        return None
    path = workdir / "cookies.txt"
    path.write_text(raw.replace("\\n", "\n"), encoding="utf-8")
    return str(path)


def _ydl_options(workdir: Path) -> dict:
    opts = {
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        # Telegram faqat H.264 (avc1) videoni hamma qurilmada o'ynatadi. AV1/VP9
        # kelsa, video bitta qotgan rasm bo'lib ko'rinadi — shuning uchun H.264
        # birinchi o'ringa qo'yiladi. Baribir boshqa kodek kelsa, bot uni
        # yuborishdan oldin H.264 ga o'giradi (video_note.ensure_h264).
        "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
        "format_sort": ["vcodec:h264", "res:1080", "acodec:aac", "ext:mp4:m4a"],
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "nocheckcertificate": True,
        "retries": 3,
        "socket_timeout": 30,
        "concurrent_fragment_downloads": 4,
        "postprocessors": [
            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
        ],
    }
    if config.PROXY:
        opts["proxy"] = config.PROXY
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

        return Downloaded(
            path=files[0],
            title=(info.get("title") or "Video")[:200],
            duration=int(info.get("duration") or 0),
            width=int(info.get("width") or 0),
            height=int(info.get("height") or 0),
            source=info.get("extractor_key") or "Instagram",
            workdir=workdir,
        )
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


def _humanize(raw: str) -> str:
    low = raw.lower()
    if "private" in low or "login required" in low or "log in" in low or "empty media" in low:
        return "Bu post yopiq (private) yoki login talab qiladi — uni yuklab bo'lmaydi."
    if "no video" in low or "there is no video" in low:
        return "Bu postda video yo'q (faqat rasm)."
    if "unavailable" in low or "not exist" in low or "404" in low or "removed" in low:
        return "Video topilmadi yoki o'chirilgan."
    if "rate" in low and "limit" in low:
        return "Instagram hozir so'rovlarni cheklayapti. Birozdan so'ng urinib ko'ring."
    return "Videoni yuklab bo'lmadi. Havolani tekshirib qayta urinib ko'ring."


async def download(url: str) -> Downloaded:
    """Videoni yuklaydi va Telegram o'ynata oladigan holatga keltiradi."""
    Path(config.WORK_DIR).mkdir(parents=True, exist_ok=True)

    try:
        item = await asyncio.to_thread(_download_sync, url)
    except DownloadError:
        raise
    except yt_dlp.utils.DownloadError as err:
        log.warning("yt-dlp xatosi: %s", str(err)[:300])
        raise DownloadError(_humanize(str(err))) from err
    except Exception as err:  # noqa: BLE001
        log.exception("Yuklashda kutilmagan xato")
        raise DownloadError(
            "Videoni yuklab bo'lmadi. Havolani tekshirib qayta urinib ko'ring."
        ) from err

    item.path = await video_note.ensure_h264(item.path)
    if item.path.stat().st_size > config.MAX_FILE_BYTES:
        item.cleanup()
        raise DownloadError(
            f"Video hajmi {config.MAX_FILE_MB} MB dan katta — Telegram bunday "
            "faylni yuborishga ruxsat bermaydi."
        )
    return item
