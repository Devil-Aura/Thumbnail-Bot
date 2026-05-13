from pyrogram import Client, enums, filters
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

HELP_TEXT = """
<b>📖 Help — Anime Thumbnail Bot</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Commands:</b>
├ /anime &lt;name&gt; — Generate thumbnail (Season 1)
├ /anime &lt;name&gt; S02 — Specify season
├ /settings — Manage GFX &amp; Cover channels
└ /help — Show this message

<b>🎨 Thumbnail Controls:</b>
├ ◀️ ▶️ — Cycle through artwork images
├ ⬆️⬇️⬅️➡️ — Pan the image position
├ ➕ ➖ — Zoom in / out
└ ✅ Done — Finalize thumbnail

<b>📤 After Done:</b>
├ 🔒 Spoiler image with AniList info sent
├ 🖼 Thumbnail with "Powered By" caption
├ 📢 Main Post — add Watch &amp; Download link
├ 🎬 Anime GFX — send to your GFX channels
└ 🖼 Cover — send to your Cover channels

<b>⚙️ /settings:</b>
├ Add/remove Anime GFX channels
└ Add/remove Cover channels with commands

<b>Examples:</b>
<code>/anime Fairy Tail</code>
<code>/anime One Piece S02</code>
<code>/anime Shield Hero S01</code>
"""


@Client.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    await message.reply_text(
        HELP_TEXT,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Home", callback_data="start|back"),
        ]]),
        parse_mode=enums.ParseMode.HTML,
    )
