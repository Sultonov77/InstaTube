"""Bot sozlamalari — hammasi environment variable orqali beriladi."""
import os


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'")


BOT_TOKEN = _clean(os.getenv("BOT_TOKEN", ""))

# Majburiy obuna kanali: "@kanal" yoki "-100..." ko'rinishida.
CHANNEL_ID = _clean(os.getenv("CHANNEL_ID", ""))

# Kanalning odamlarga ko'rsatiladigan nomi.
CHANNEL_TITLE = _clean(os.getenv("CHANNEL_TITLE", ""))

# Kanal havolasi. Ko'rsatilmasa: @username dan yasaladi, yoki bot kanalning
# o'zidan (invite link) olib keladi — qarang: app/subscription.py.
CHANNEL_URL = _clean(os.getenv("CHANNEL_URL", ""))
if not CHANNEL_URL and CHANNEL_ID.startswith("@"):
    CHANNEL_URL = f"https://t.me/{CHANNEL_ID.lstrip('@')}"

# Telegram Bot API orqali yuborish chegarasi 50 MB.
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "48"))
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024

# Video note (doira video) uchun Telegram chegarasi — 60 soniya.
NOTE_MAX_SECONDS = int(os.getenv("NOTE_MAX_SECONDS", "60"))
NOTE_SIZE = int(os.getenv("NOTE_SIZE", "480"))

# Instagram yopiq postlari uchun ixtiyoriy cookies (Netscape formatdagi matn).
INSTAGRAM_COOKIES = os.getenv("INSTAGRAM_COOKIES", "")

# YouTube "bot emasligingizni tasdiqlang" to'sig'ini kafolatli aylanib o'tish uchun
# ixtiyoriy cookies (Netscape formatdagi matn).
YOUTUBE_COOKIES = os.getenv("YOUTUBE_COOKIES", "")

# Ixtiyoriy proxy (masalan "http://user:pass@host:port") — YouTube server IP'larini
# bloklagan holatlar uchun.
PROXY = _clean(os.getenv("PROXY", ""))

# BgUtils PO Token serveri manzili (alohida servis sifatida ishlaydi).
# Masalan: http://pot-provider.railway.internal:4416
POT_BASE_URL = _clean(os.getenv("POT_BASE_URL", ""))
POT_ENABLED = bool(POT_BASE_URL)

# Diagnostika: shu havola bilan ishga tushganda qaysi YouTube mijozi ishlayotgani
# loglarga yoziladi. Bo'sh bo'lsa — tekshiruv o'tkazilmaydi.
SELFTEST_YOUTUBE = _clean(os.getenv("SELFTEST_YOUTUBE", ""))

# Yuklangan fayllar vaqtinchalik saqlanadigan joy.
WORK_DIR = _clean(os.getenv("WORK_DIR", "/tmp/instatube"))


def validate() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. @BotFather bergan tokenni environment variable "
            "sifatida qo'ying (Railway -> Variables -> BOT_TOKEN)."
        )
