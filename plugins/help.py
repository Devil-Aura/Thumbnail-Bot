from pyrogram import Client, enums, filters
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

HELP_TEXT = (
    "<b>📖 Help — Anime Thumbnail Bot</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "<b>🎌 Generate Thumbnails:</b>\n"
    "  <code>/anime &lt;name&gt;</code>          — Season 1 by default\n"
    "  <code>/anime &lt;name&gt; S02</code>      — Specify season\n\n"
    "<b>🎨 Thumbnail Controls:</b>\n"
    "  ◀️ ▶️  — Cycle through artwork images\n"
    "  ⬆️⬇️⬅️➡️ — Pan the image position\n"
    "  ➕ ➖  — Zoom in / out\n"
    "  ✅ Done — Finalize &amp; post the thumbnail\n\n"
    "<b>📤 After Finalizing:</b>\n"
    "  🔒  Spoiler image with AniList info\n"
    "  🖼  Thumbnail with Powered By caption\n"
    "  📢  Main Post — add Watch &amp; Download link\n"
    "  🎬  GFX — send to your Anime GFX channels\n"
    "  🖼  Cover — send to your Cover channels\n\n"
    "<b>⚙️ Channel Settings:</b>\n"
    "  <code>/settings</code> — Add or remove GFX &amp; Cover channels\n\n"
    "<b>🛠 Other Commands:</b>\n"
    "  <code>/ping</code>  — Check bot response time &amp; uptime\n"
    "  <code>/start</code> — Back to home screen\n\n"
    "<b>💡 Examples:</b>\n"
    "  <code>/anime Fairy Tail</code>\n"
    "  <code>/anime One Piece S02</code>\n"
    "  <code>/anime Shield Hero S01</code>"
)

OWNER_HELP_TEXT = (
    "\n\n<b>👑 Owner Commands</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "<b>🔧 Bot Management:</b>\n"
    "  <code>/restart</code>              — Restart the bot immediately\n"
    "  <code>/update</code>               — Pull latest code from GitHub &amp; restart\n"
    "  <code>/update_repo &lt;url&gt;</code>  — Pull from a different repo &amp; restart\n\n"
    "<b>📊 Monitoring:</b>\n"
    "  <code>/stats</code>  — Users, sessions, uptime &amp; mode\n"
    "  <code>/ping</code>   — Bot latency &amp; uptime\n\n"
    "<b>📡 Broadcasting:</b>\n"
    "  <code>/broadcast &lt;text&gt;</code>  — Send message to all users\n\n"
    "<b>🚫 User Control:</b>\n"
    "  <code>/ban &lt;user_id&gt;</code>    — Ban a user from the bot\n"
    "  <code>/unban &lt;user_id&gt;</code>  — Remove a ban\n"
    "  <code>/addadmin &lt;id&gt;</code>    — Add an admin\n"
    "  <code>/deladmin &lt;id&gt;</code>    — Remove an admin\n"
    "  <code>/admins</code>               — List all admins\n"
    "  <code>/pvt</code>  — Switch to private mode\n"
    "  <code>/pub</code>  — Switch to public mode"
)


@Client.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    from config import OWNER_ID
    uid = message.from_user.id

    full_text = HELP_TEXT
    if uid == OWNER_ID:
        full_text += OWNER_HELP_TEXT

    await message.reply_text(
        full_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Home", callback_data="start|back"),
        ]]),
        parse_mode=enums.ParseMode.HTML,
    )
