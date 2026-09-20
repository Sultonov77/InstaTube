"""Majburiy obuna tekshiruvi."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app import config

log = logging.getLogger(__name__)

# Obuna hisoblanadigan statuslar.
_MEMBER_STATUSES = {"creator", "administrator", "member"}


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """Foydalanuvchi kanalga a'zomi? Tekshirib bo'lmasa — o'tkazib yuboramiz."""
    try:
        member = await bot.get_chat_member(config.CHANNEL_ID, user_id)
    except (TelegramBadRequest, TelegramForbiddenError) as err:
        # Bot kanalga admin qilib qo'yilmagan bo'lsa, foydalanuvchini bloklamaymiz.
        log.warning("Obunani tekshirib bo'lmadi (%s): %s", config.CHANNEL_ID, err)
        return True
    return member.status in _MEMBER_STATUSES


def subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"📢 {config.CHANNEL_TITLE}", url=config.CHANNEL_URL)],
            [InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check_sub")],
        ]
    )


SUBSCRIBE_TEXT = (
    "🔒 <b>Botdan foydalanish uchun avval kanalimizga obuna bo'ling.</b>\n\n"
    f"👉 <a href=\"{config.CHANNEL_URL}\">{config.CHANNEL_TITLE}</a>\n\n"
    "Obuna bo'lgach <b>«✅ Obuna bo'ldim»</b> tugmasini bosing."
)
