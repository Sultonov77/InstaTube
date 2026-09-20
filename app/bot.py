"""InstaTube — YouTube/Instagram video yuklovchi va doira video yasovchi bot."""
import asyncio
import contextlib
import logging
import shutil
import time
import uuid
from html import escape
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app import config, downloader, subscription, video_note

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
log = logging.getLogger("instatube")

router = Router()

# Telegram bot getFile orqali 20 MB gacha fayl ola oladi.
TELEGRAM_DOWNLOAD_LIMIT = 20 * 1024 * 1024

def welcome(name: str) -> str:
    return (
        f"✨ <b>InstaTube</b>\n"
        f"<i>Video yuklovchi va doira video ustasi</i>\n\n"
        f"Salom, <b>{name}</b>! Mana nima qila olaman:\n\n"
        f"📥  <b>Video yuklash</b>\n"
        f"      <i>YouTube yoki Instagram havolasini tashlang</i>\n\n"
        f"🔵  <b>Doira video</b>\n"
        f"      <i>Oddiy videoni tashlang — video note qilib qaytaraman</i>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Boshlash uchun havola yoki video yuboring 👇"
    )


HOW_DOWNLOAD = (
    "📥 <b>Video yuklash</b>\n\n"
    "Menga quyidagilardan birining havolasini tashlang:\n\n"
    "▸ <b>YouTube</b> — oddiy video, Shorts, jonli efir yozuvi\n"
    "▸ <b>Instagram</b> — post, Reels, IGTV\n\n"
    "<code>https://youtu.be/...</code>\n"
    "<code>https://instagram.com/reel/...</code>\n\n"
    f"<i>Cheklov: {config.MAX_FILE_MB} MB gacha. Yopiq (private) postlar yuklanmaydi.</i>"
)

HOW_NOTE = (
    "🔵 <b>Doira video</b>\n\n"
    "Menga <b>video</b> yoki <b>GIF</b> yuboring — markazidan kvadrat kesib, "
    "Telegram'ning doira videosi (video note) qilib qaytaraman.\n\n"
    "Yuklab olingan videoning tagidagi <b>«🔵 Doira video qilish»</b> "
    "tugmasi ham xuddi shuni qiladi.\n\n"
    f"<i>Cheklov: {config.NOTE_MAX_SECONDS} soniyagacha (uzunrog'i qirqiladi), "
    "kiruvchi fayl 20 MB gacha.</i>"
)

HELP = (
    "ℹ️ <b>Yordam</b>\n\n"
    "📥 <b>Yuklash</b> — YouTube yoki Instagram havolasini yuboring\n"
    "🔵 <b>Doira video</b> — video yoki GIF yuboring\n\n"
    "<b>Komandalar</b>\n"
    "/start — boshlash\n"
    "/help — shu yordam\n\n"
    "<b>Cheklovlar</b>\n"
    f"▸ Yuboriladigan fayl — {config.MAX_FILE_MB} MB gacha\n"
    "▸ Qabul qilinadigan fayl — 20 MB gacha (Telegram qoidasi)\n"
    f"▸ Doira video — {config.NOTE_MAX_SECONDS} soniyagacha\n"
    "▸ Yopiq (private) postlar yuklanmaydi"
)


def main_keyboard(channel_url: str = "") -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="📥 Yuklash", callback_data="how:download"),
            InlineKeyboardButton(text="🔵 Doira video", callback_data="how:note"),
        ]
    ]
    if channel_url:
        rows.append([InlineKeyboardButton(text="📢 Kanalimiz", url=channel_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


BACK_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="how:back")]]
)

# make_note tugmasi uchun vaqtinchalik fayl ombori: token -> (yo'l, vaqt).
_pending: dict[str, tuple[Path, float]] = {}
_PENDING_TTL = 30 * 60


def _remember(path: Path) -> str:
    token = uuid.uuid4().hex[:12]
    _pending[token] = (path, time.time())
    return token


async def _sweep_pending() -> None:
    """Eskirgan vaqtinchalik fayllarni tozalab turadi."""
    while True:
        await asyncio.sleep(300)
        now = time.time()
        for token, (path, created) in list(_pending.items()):
            if now - created > _PENDING_TTL:
                _pending.pop(token, None)
                shutil.rmtree(path.parent, ignore_errors=True)


async def _guard(bot: Bot, user_id: int, answer) -> bool:
    """Obuna bo'lmagan foydalanuvchiga taklif ko'rsatadi."""
    if await subscription.is_subscribed(bot, user_id):
        return True
    await answer(
        await subscription.subscribe_text(bot),
        reply_markup=await subscription.subscribe_keyboard(bot),
    )
    return False


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    if not await _guard(bot, message.from_user.id, message.answer):
        return
    await message.answer(
        welcome(message.from_user.first_name or "do'stim"),
        reply_markup=main_keyboard(await subscription.channel_url(bot)),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot) -> None:
    if not await _guard(bot, message.from_user.id, message.answer):
        return
    await message.answer(HELP, reply_markup=main_keyboard(await subscription.channel_url(bot)))


@router.callback_query(F.data.startswith("how:"))
async def cb_how(callback: CallbackQuery, bot: Bot) -> None:
    section = callback.data.split(":", 1)[1]
    if section == "download":
        text, markup = HOW_DOWNLOAD, BACK_KEYBOARD
    elif section == "note":
        text, markup = HOW_NOTE, BACK_KEYBOARD
    else:
        text = welcome(callback.from_user.first_name or "do'stim")
        markup = main_keyboard(await subscription.channel_url(bot))

    with contextlib.suppress(Exception):
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery, bot: Bot) -> None:
    if await subscription.is_subscribed(bot, callback.from_user.id):
        await callback.answer("Rahmat! Endi botdan foydalanishingiz mumkin ✅", show_alert=True)
        with contextlib.suppress(Exception):
            await callback.message.delete()
        await callback.message.answer(
            welcome(callback.from_user.first_name or "do'stim"),
            reply_markup=main_keyboard(await subscription.channel_url(bot)),
        )
    else:
        await callback.answer(
            "Hali obuna bo'lmagansiz 🙂 Kanalga qo'shiling va qayta tekshiring.",
            show_alert=True,
        )


@router.message(F.text.func(lambda t: bool(t) and bool(downloader.find_link(t))))
async def handle_link(message: Message, bot: Bot) -> None:
    if not await _guard(bot, message.from_user.id, message.answer):
        return

    found = downloader.find_link(message.text)
    if not found:
        return
    url, source = found

    status = await message.answer(f"⏬ <b>{source}</b>\n<i>Yuklanmoqda…</i>")
    await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)

    try:
        item = await downloader.download(url, source)
    except downloader.DownloadError as err:
        await status.edit_text(f"❌ <b>Yuklab bo'lmadi</b>\n\n{err}")
        return

    try:
        await status.edit_text("📤 <b>Telegram'ga yuklanmoqda…</b>")
        me = await bot.me()
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="🔵 Doira video qilish",
                    callback_data=f"note:{_remember(item.path)}",
                )
            ]]
        )
        await message.answer_video(
            FSInputFile(item.path),
            caption=(
                f"🎬 <b>{escape(item.title)}</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📥 @{me.username}"
            ),
            duration=item.duration or None,
            width=item.width or None,
            height=item.height or None,
            supports_streaming=True,
            reply_markup=keyboard,
        )
        await status.delete()
    except Exception:  # noqa: BLE001
        log.exception("Videoni yuborib bo'lmadi")
        item.cleanup()
        with contextlib.suppress(Exception):
            await status.edit_text("❌ Videoni yuborib bo'lmadi. Qaytadan urinib ko'ring.")


@router.callback_query(F.data.startswith("note:"))
async def cb_make_note(callback: CallbackQuery, bot: Bot) -> None:
    if not await subscription.is_subscribed(bot, callback.from_user.id):
        await callback.answer("Avval kanalga obuna bo'ling.", show_alert=True)
        return

    token = callback.data.split(":", 1)[1]
    entry = _pending.get(token)
    if not entry or not entry[0].exists():
        await callback.answer(
            "Fayl muddati tugadi. Videoni menga qayta yuboring.", show_alert=True
        )
        return

    await callback.answer("🔵 Doira video tayyorlanmoqda…")
    src = entry[0]
    dst = src.parent / f"note-{token}.mp4"
    await bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_VIDEO_NOTE)
    try:
        duration = await video_note.to_video_note(src, dst)
        await callback.message.answer_video_note(
            FSInputFile(dst), duration=duration, length=config.NOTE_SIZE
        )
    except video_note.ConvertError as err:
        await callback.message.answer(f"❌ {err}")
    finally:
        with contextlib.suppress(Exception):
            await callback.message.edit_reply_markup(reply_markup=None)


@router.message(F.video | F.animation | F.document)
async def handle_video(message: Message, bot: Bot) -> None:
    if not await _guard(bot, message.from_user.id, message.answer):
        return

    media = message.video or message.animation or message.document
    mime = (getattr(media, "mime_type", "") or "").lower()
    if message.document and not mime.startswith("video/"):
        await message.answer(
            "❌ <b>Bu video fayl emas</b>\n\nMenga video, GIF yoki havola yuboring."
        )
        return

    if (media.file_size or 0) > TELEGRAM_DOWNLOAD_LIMIT:
        await message.answer(
            "❌ <b>Fayl juda katta</b>\n\n"
            "Telegram botlarga 20 MB dan katta faylni yuklab olishga ruxsat bermaydi. "
            "Kichikroq video yuboring."
        )
        return

    status = await message.answer("🔵 <b>Doira video</b>\n<i>Tayyorlanmoqda…</i>")
    await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO_NOTE)

    workdir = Path(config.WORK_DIR) / f"note-{uuid.uuid4().hex[:8]}"
    workdir.mkdir(parents=True, exist_ok=True)
    src = workdir / "input.mp4"
    dst = workdir / "output.mp4"
    try:
        await bot.download(media.file_id, destination=src)
        duration = await video_note.to_video_note(src, dst)
        await message.answer_video_note(
            FSInputFile(dst), duration=duration, length=config.NOTE_SIZE
        )
        await status.delete()
    except video_note.ConvertError as err:
        await status.edit_text(f"❌ {err}")
    except Exception:  # noqa: BLE001
        log.exception("Doira videoga o'tkazib bo'lmadi")
        with contextlib.suppress(Exception):
            await status.edit_text("❌ Videoni qayta ishlab bo'lmadi. Qaytadan urinib ko'ring.")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@router.message(F.text)
async def handle_other_text(message: Message, bot: Bot) -> None:
    if not await _guard(bot, message.from_user.id, message.answer):
        return
    await message.answer(
        "🤔 <b>Bu havolani tanimadim</b>\n\n"
        "📥 YouTube yoki Instagram havolasini yuboring\n"
        "🔵 Yoki doira videoga aylantirish uchun video tashlang",
        reply_markup=main_keyboard(await subscription.channel_url(bot)),
    )


async def main() -> None:
    config.validate()
    Path(config.WORK_DIR).mkdir(parents=True, exist_ok=True)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    me = await bot.me()
    log.info("Bot ishga tushdi: @%s (kanal: %s)", me.username, config.CHANNEL_ID or "yo'q")
    if not config.CHANNEL_ID:
        log.warning("CHANNEL_ID berilmagan — majburiy obuna tekshiruvi o'chirilgan.")

    if version := await video_note.ffmpeg_version():
        log.info("ffmpeg topildi: %s", version)
    else:
        log.error("ffmpeg topilmadi — doira video yasash ishlamaydi!")

    log.info("PO Token serveri: %s", await downloader.pot_ping())

    # Diagnostika: shu serverning IP'sidan qaysi YouTube mijozi ishlayotganini
    # loglarga yozadi. SELFTEST_YOUTUBE=<video havolasi> bo'lganda ishlaydi.
    if selftest_url := config.SELFTEST_YOUTUBE:
        log.info("YouTube selftest boshlandi…")
        log.info("YouTube selftest: %s", await downloader.selftest(selftest_url))

    sweeper = asyncio.create_task(_sweep_pending())
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        sweeper.cancel()
        await bot.session.close()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(main())
