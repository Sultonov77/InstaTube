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

# YouTube server IP'laridan kelgan so'rovlarni "bot" deb hisoblab, oddiy web
# mijozni bloklaydi. Bu mijozlar PO Token talab qilmaydi, shuning uchun ularni
# navbat bilan sinab ko'ramiz.
# Tartib muhim: birinchi uchtasi 1080p+ beradi, android_* zaxira sifatida
# 360p bo'lsa ham ishlaydi. (2026-09-20 da haqiqiy videolarda tekshirilgan.)
_YT_CLIENT_SETS: tuple[list[str], ...] = (
    ["tv_embedded"],
    ["ios_music"],
    ["android_music"],
    ["android_vr"],
    ["android"],
)

# Shu belgilar uchrasa — mijoz bloklangan/format bermagan, keyingisini sinaymiz.
_BOT_WALL_MARKERS = (
    "not a bot",
    "sign in to confirm",
    "please sign in",
    "po token",
    "page needs to be reloaded",
    "failed to extract any player response",
    "unable to extract",
    "requested format is not available",
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


def _cookie_file(workdir: Path, source: str) -> str | None:
    raw = config.YOUTUBE_COOKIES if source == "YouTube" else config.INSTAGRAM_COOKIES
    if not raw.strip():
        return None
    path = workdir / "cookies.txt"
    path.write_text(raw.replace("\\n", "\n"), encoding="utf-8")
    return str(path)


def _ydl_options(workdir: Path, source: str, clients: list[str] | None) -> dict:
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
    extractor_args: dict[str, dict] = {}
    if clients:
        extractor_args["youtube"] = {"player_client": clients}
    if config.POT_BASE_URL:
        extractor_args["youtubepot-bgutilhttp"] = {"base_url": [config.POT_BASE_URL]}
    if extractor_args:
        opts["extractor_args"] = extractor_args
    if config.PROXY:
        opts["proxy"] = config.PROXY
    if cookies := _cookie_file(workdir, source):
        opts["cookiefile"] = cookies
    return opts


def _download_sync(url: str, source: str, clients: list[str] | None) -> Downloaded:
    workdir = Path(tempfile.mkdtemp(prefix=f"dl-{uuid.uuid4().hex[:8]}-", dir=config.WORK_DIR))
    try:
        with yt_dlp.YoutubeDL(_ydl_options(workdir, source, clients)) as ydl:
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
            source=info.get("extractor_key") or source,
            workdir=workdir,
        )
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise


def _is_bot_wall(raw: str) -> bool:
    low = raw.lower()
    return any(marker in low for marker in _BOT_WALL_MARKERS)


def _humanize(raw: str, source: str) -> str:
    low = raw.lower()
    if _is_bot_wall(low):
        if source == "YouTube":
            return (
                "YouTube hozir bu serverdan yuklashga ruxsat bermayapti "
                "(«bot emasligingizni tasdiqlang» to'sig'i). Biroz kutib qayta "
                "urinib ko'ring yoki boshqa video tashlang."
            )
        return "Manba hozir yuklashga ruxsat bermayapti. Birozdan so'ng urinib ko'ring."
    if "private" in low or "login required" in low or "log in" in low:
        return "Bu post yopiq (private) yoki login talab qiladi — uni yuklab bo'lmaydi."
    if "unavailable" in low or "not exist" in low or "404" in low or "removed" in low:
        return "Video topilmadi yoki o'chirilgan."
    if "age" in low and "restrict" in low:
        return "Video yosh chekloviga ega, yuklab bo'lmaydi."
    if "copyright" in low or "blocked" in low:
        return "Video mualliflik huquqi sababli bloklangan."
    if "live" in low and "not started" in low:
        return "Bu jonli efir hali boshlanmagan."
    return "Videoni yuklab bo'lmadi. Havolani tekshirib qayta urinib ko'ring."


def _attempts(source: str) -> list[list[str] | None]:
    """Qaysi player mijozlari bilan urinib ko'rish kerakligini qaytaradi."""
    if source != "YouTube":
        return [None]

    attempts: list[list[str] | None] = []
    if config.POT_ENABLED or config.YOUTUBE_COOKIES.strip():
        # PO Token yoki cookies bo'lsa yt-dlp'ning odatdagi (web) mijozi ishlaydi
        # va eng yaxshi sifatni beradi.
        attempts.append(None)
    attempts.extend(list(clients) for clients in _YT_CLIENT_SETS)
    return attempts


async def pot_ping() -> str:
    """PO Token serveri javob beryaptimi — loglar uchun qisqa holat."""
    if not config.POT_BASE_URL:
        return "sozlanmagan"

    import aiohttp  # aiogram bilan birga keladi

    url = config.POT_BASE_URL.rstrip("/") + "/ping"
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                body = (await response.text())[:150]
        return f"OK ({response.status}) {body}"
    except Exception as err:  # noqa: BLE001
        return f"XATO ({type(err).__name__}: {str(err)[:100]})"


def _probe_sync(url: str, source: str, clients: list[str] | None) -> tuple[int, int]:
    """Yuklamasdan formatlarni tekshiradi -> (formatlar soni, maksimal balandlik)."""
    workdir = Path(tempfile.mkdtemp(prefix="probe-", dir=config.WORK_DIR))
    try:
        opts = _ydl_options(workdir, source, clients) | {"skip_download": True}
        opts.pop("postprocessors", None)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        videos = [
            f for f in (info.get("formats") or []) if f.get("vcodec") not in (None, "none")
        ]
        return len(videos), max((f.get("height") or 0) for f in videos) if videos else 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def selftest(url: str) -> str:
    """Server IP'sidan qaysi YouTube mijozi ishlayotganini aniqlaydi (loglar uchun)."""
    Path(config.WORK_DIR).mkdir(parents=True, exist_ok=True)
    lines = []
    for clients in _attempts("YouTube"):
        label = ",".join(clients) if clients else "default"
        try:
            count, height = await asyncio.to_thread(_probe_sync, url, "YouTube", clients)
        except Exception as err:  # noqa: BLE001
            lines.append(f"{label}=XATO({str(err)[:60]})")
        else:
            lines.append(f"{label}=OK({count} format, {height}p)")

    # Haqiqiy yuklashni ham sinaymiz — ffmpeg birlashtiruvi shu yerda tekshiriladi.
    try:
        item = await download(url, "YouTube")
    except Exception as err:  # noqa: BLE001
        lines.append(f"to'liq-yuklash=XATO({str(err)[:80]})")
    else:
        size_mb = item.path.stat().st_size / 1024 / 1024
        lines.append(
            f"to'liq-yuklash=OK({size_mb:.1f}MB, {item.width}x{item.height}, {item.duration}s)"
        )
        item.cleanup()

    return " | ".join(lines)


async def download(url: str, source: str = "") -> Downloaded:
    Path(config.WORK_DIR).mkdir(parents=True, exist_ok=True)
    last_error = ""

    for clients in _attempts(source):
        try:
            item = await asyncio.to_thread(_download_sync, url, source, clients)
        except DownloadError:
            raise
        except yt_dlp.utils.DownloadError as err:
            last_error = str(err)
            if _is_bot_wall(last_error):
                # Bu mijoz bloklandi — keyingisini sinaymiz.
                log.warning("Mijoz ishlamadi (%s): %s", clients or "default", last_error[:200])
                continue
            log.warning("yt-dlp xatosi: %s", last_error[:300])
            raise DownloadError(_humanize(last_error, source)) from err
        except Exception as err:  # noqa: BLE001
            log.exception("Yuklashda kutilmagan xato")
            raise DownloadError(
                "Videoni yuklab bo'lmadi. Havolani tekshirib qayta urinib ko'ring."
            ) from err
        else:
            if clients:
                log.info("Yuklandi (%s mijozi bilan): %s", ",".join(clients), item.title[:60])
            return item

    raise DownloadError(_humanize(last_error, source))
