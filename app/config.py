"""Bot sozlamalari — hammasi environment variable orqali beriladi."""
import os


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'")


BOT_TOKEN = _clean(os.getenv("BOT_TOKEN", ""))

# Majburiy obuna kanali: "@kanal" yoki "-100..." ko'rinishida.
CHANNEL_ID = _clean(os.getenv("CHANNEL_ID", "@sultonov_samandar_ai"))

# Kanalning odamlarga ko'rsatiladigan nomi va havolasi.
CHANNEL_TITLE = _clean(os.getenv("CHANNEL_TITLE", "Sultonov Samandar AI"))
CHANNEL_URL = _clean(
    os.getenv("CHANNEL_URL", "")
) or f"https://t.me/{CHANNEL_ID.lstrip('@')}"

# Telegram Bot API orqali yuborish chegarasi 50 MB.
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "48"))
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024

# Video note (doira video) uchun Telegram chegarasi — 60 soniya.
NOTE_MAX_SECONDS = int(os.getenv("NOTE_MAX_SECONDS", "60"))
NOTE_SIZE = int(os.getenv("NOTE_SIZE", "480"))

# Instagram yopiq postlari uchun ixtiyoriy cookies (Netscape formatdagi matn).
INSTAGRAM_COOKIES = os.getenv("INSTAGRAM_COOKIES", "")

# Yuklangan fayllar vaqtinchalik saqlanadigan joy.
WORK_DIR = _clean(os.getenv("WORK_DIR", "/tmp/instatube"))


def validate() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. @BotFather bergan tokenni environment variable "
            "sifatida qo'ying (Railway -> Variables -> BOT_TOKEN)."
        )
