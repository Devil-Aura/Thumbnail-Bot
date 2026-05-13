from pyrogram import Client, enums, filters
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from config import START_PIC, OWNER_ID

START_TEXT = """
<b>🎌 Welcome to Anime Thumbnail Bot!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

I create professional <b>CrunchyRoll-style 1280×720</b> anime thumbnails automatically using TMDB & FANART.TV artwork — and generate ready-to-post channel captions.

<b>✨ What I can do:</b>
├ 🖼 Generate stunning anime thumbnails
├ 🎨 Pan, zoom & swap artwork interactively
├ 📢 Post to your GFX & Cover channels
├ 📋 Build formatted channel posts with links
└ ⚙️ Full per-user channel settings

<b>🚀 Get started with /anime</b>
"""

START_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📖 Help",      callback_data="start|help"),
        InlineKeyboardButton("⚙️ Settings",  callback_data="start|settings"),
    ],
    [
        InlineKeyboardButton("📢 Channel",   url="https://t.me/CrunchyRollChannel"),
        InlineKeyboardButton("👨‍💻 Support",  url="https://t.me/CrunchyRollChannel"),
    ],
])

HELP_TEXT = """
<b>📖 Help — Anime Thumbnail Bot</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Commands:</b>
├ /anime &lt;name&gt; — Generate thumbnail (Season 1)
├ /anime &lt;name&gt; S02 — Specify season
├ /settings — Manage your GFX & Cover channels
└ /help — Show this message

<b>🎨 Thumbnail Controls:</b>
├ ◀️ ▶️ — Cycle through artwork images
├ ⬆️⬇️⬅️➡️ — Pan the image
├ ➕ ➖ — Zoom in / out
└ ✅ Done — Finalize & send

<b>📤 After Done:</b>
├ Spoiler image with AniList info is sent
├ Thumbnail is sent with "Powered By" caption
├ 📢 Main Post — send watch/download link
├ 🎬 Anime GFX — send to your GFX channels
└ 🖼 Cover — send to your Cover channels

<b>⚙️ Settings:</b>
├ Add/remove Anime GFX channels
└ Add/remove Cover channels (with command)

<b>Example:</b>
<code>/anime Fairy Tail S02</code>
<code>/anime One Piece</code>
"""

HELP_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("⬅️ Back", callback_data="start|back")],
])


@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    try:
        await client.db.add_user(message.from_user.id)
    except Exception:
        pass  # Don't let DB failures block the start message

    try:
        await message.reply_photo(
            photo=START_PIC,
            caption=START_TEXT,
            reply_markup=START_KB,
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        # Fallback to plain text if photo fails
        await message.reply_text(
            START_TEXT,
            reply_markup=START_KB,
            parse_mode=enums.ParseMode.HTML,
        )


@Client.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    await message.reply_text(
        HELP_TEXT,
        reply_markup=HELP_KB,
        parse_mode=enums.ParseMode.HTML,
    )


@Client.on_callback_query(filters.regex(r"^start\|"))
async def start_cb(client: Client, cq):
    action = cq.data.split("|")[1]

    if action == "help":
        try:
            await cq.message.edit_caption(
                caption=HELP_TEXT,
                reply_markup=HELP_KB,
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            await cq.message.reply_text(
                HELP_TEXT,
                reply_markup=HELP_KB,
                parse_mode=enums.ParseMode.HTML,
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
