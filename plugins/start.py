from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from config import START_PIC

START_TEXT = (
    "<b>🎌 Anime Thumbnail Bot</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "I create professional <b>CrunchyRoll-style 1280×720</b> anime thumbnails "
    "using TMDB & FANART.TV artwork.\n\n"
    "<b>✨ Features:</b>\n"
    "├ 🖼 Generate anime thumbnails\n"
    "├ 🎨 Pan, zoom &amp; swap artwork\n"
    "├ 📢 Post to GFX &amp; Cover channels\n"
    "└ ⚙️ Per-user channel settings\n\n"
    "<b>🚀 Start with /anime &lt;name&gt;</b>"
)

START_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📖 Help",     callback_data="start|help"),
        InlineKeyboardButton("⚙️ Settings", callback_data="start|settings"),
    ],
    [
        InlineKeyboardButton("📢 Channel", url="https://t.me/CrunchyRollChannel"),
        InlineKeyboardButton("👨‍💻 Support", url="https://t.me/CrunchyRollChannel"),
    ],
])

HELP_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("⬅️ Back", callback_data="start|back")],
])


@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    try:
        await client.db.add_user(message.from_user.id)
    except Exception:
        pass

    from plugins.help import HELP_TEXT as _HT  # reuse exact help text from help.py
    try:
        await message.reply_photo(
            photo=START_PIC,
            caption=START_TEXT,
            reply_markup=START_KB,
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        await message.reply_text(
            START_TEXT,
            reply_markup=START_KB,
            parse_mode=enums.ParseMode.HTML,
        )


@Client.on_callback_query(filters.regex(r"^start\|"))
async def start_cb(client: Client, cq: CallbackQuery):
    action = cq.data.split("|")[1]

    if action == "help":
        from plugins.help import HELP_TEXT as HT
        try:
            await cq.message.edit_caption(
                caption=HT,
                reply_markup=HELP_KB,
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            await cq.message.reply_text(
                HT, reply_markup=HELP_KB, parse_mode=enums.ParseMode.HTML,
            )
        await cq.answer()

    elif action == "settings":
        from plugins.settings import SETTINGS_TEXT, _main_kb
        await cq.message.reply_text(
            SETTINGS_TEXT,
            reply_markup=_main_kb(),
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer()

    elif action == "back":
        try:
            await cq.message.edit_caption(
                caption=START_TEXT,
                reply_markup=START_KB,
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            await cq.message.reply_text(
                START_TEXT,
                reply_markup=START_KB,
                parse_mode=enums.ParseMode.HTML,
            )
        await cq.answer()

    else:
        await cq.answer()
