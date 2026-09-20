"""Majburiy obuna tekshiruvi."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app import config

log = logging.getLogger(__name__)

# Obuna hisoblanadigan statuslar.
_MEMBER_STATUSES = {"creator", "administrator", "member"}

# get_chat natijasi keshlanadi — har xabarda qayta so'ramaslik uchun.
_cached_url: str | None = None


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """Foydalanuvchi kanalga a'zomi? Tekshirib bo'lmasa — o'tkazib yuboramiz."""
    try:
        member = await bot.get_chat_member(config.CHANNEL_ID, user_id)
    except (TelegramBadRequest, TelegramForbiddenError) as err:
        # Bot kanalga admin qilib qo'yilmagan bo'lsa, foydalanuvchini bloklamaymiz.
        log.warning("Obunani tekshirib bo'lmadi (%s): %s", config.CHANNEL_ID, err)
        return True
    return member.status in _MEMBER_STATUSES


async def channel_url(bot: Bot) -> str:
    """Kanal havolasi: sozlamadan, yoki kanalning o'zidan (username/invite link)."""
    global _cached_url

    if config.CHANNEL_URL:
        return config.CHANNEL_URL
    if _cached_url:
        return _cached_url

    try:
        chat = await bot.get_chat(config.CHANNEL_ID)
    except (TelegramBadRequest, TelegramForbiddenError) as err:
        # Bot kanalga qo'shilmagan bo'lsa havolani bilib bo'lmaydi.
        log.warning("Kanal havolasini olib bo'lmadi: %s", err)
        return ""

    if chat.username:
        _cached_url = f"https://t.me/{chat.username}"
    elif chat.invite_link:
        _cached_url = chat.invite_link
    else:
        # Yopiq kanal: bot admin bo'lsa yangi havola yaratadi.
        try:
            link = await bot.create_chat_invite_link(config.CHANNEL_ID, name="InstaTube bot")
            _cached_url = link.invite_link
        except (TelegramBadRequest, TelegramForbiddenError) as err:
            log.warning("Invite link yaratib bo'lmadi: %s", err)
            return ""
    return _cached_url


async def channel_title(bot: Bot) -> str:
    if config.CHANNEL_TITLE:
        return config.CHANNEL_TITLE
    try:
        chat = await bot.get_chat(config.CHANNEL_ID)
    except (TelegramBadRequest, TelegramForbiddenError):
        return "Kanal"
    return chat.title or "Kanal"


async def subscribe_keyboard(bot: Bot) -> InlineKeyboardMarkup:
    rows = []
    url = await channel_url(bot)
    if url:
        title = await channel_title(bot)
        rows.append([InlineKeyboardButton(text=f"📢 {title}", url=url)])
    rows.append([InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def subscribe_text(bot: Bot) -> str:
    title = await channel_title(bot)
    url = await channel_url(bot)
    link = f'<a href="{url}">{title}</a>' if url else f"<b>{title}</b>"
    return (
        "🔒 <b>Botdan foydalanish uchun avval kanalimizga obuna bo'ling.</b>\n\n"
        f"👉 {link}\n\n"
        "Obuna bo'lgach <b>«✅ Obuna bo'ldim»</b> tugmasini bosing."
    )
