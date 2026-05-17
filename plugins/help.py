from pyrogram import Client, enums, filters
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

HELP_TEXT = (
    "<b>📖 Help — Anime Thumbnail Bot</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "<b>🎌 Thumbnail Commands:</b>\n"
    "├ /anime &lt;name&gt; — Generate thumbnail (Season 1)\n"
    "├ /anime &lt;name&gt; S02 — Specify season number\n"
    "└ /settings — Manage GFX &amp; Cover channels\n\n"
    "<b>🎨 Thumbnail Controls:</b>\n"
    "├ ◀️ ▶️ — Cycle through artwork images\n"
    "├ ⬆️⬇️⬅️➡️ — Pan the image position\n"
    "├ ➕ ➖ — Zoom in / out\n"
    "└ ✅ Done — Finalize &amp; post thumbnail\n\n"
    "<b>📤 After Done:</b>\n"
    "├ 🔒 Spoiler image with AniList info\n"
    "├ 🖼 Thumbnail with Powered By caption\n"
    "├ 📢 Main Post — add Watch &amp; Download link\n"
    "├ 🎬 Anime GFX — send to your GFX channels\n"
    "└ 🖼 Cover — send to your Cover channels\n\n"
    "<b>🛠 Other Commands:</b>\n"
    "├ /ping — Check bot response time\n"
    "├ /help — Show this message\n"
    "└ /start — Back to home\n\n"
    "<b>💡 Examples:</b>\n"
    "<code>/anime Fairy Tail</code>\n"
    "<code>/anime One Piece S02</code>\n"
    "<code>/anime Shield Hero S01</code>"
)

OWNER_HELP_TEXT = (
    "<b>👑 Owner Commands</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "<b>🔧 Bot Management:</b>\n"
    "├ /restart — Restart the bot immediately\n"
    "├ /update — Pull latest code from GitHub &amp; restart\n"
    "├ /update_repo &lt;url&gt; — Pull from a different repo &amp; restart\n"
    "└ /shell &lt;cmd&gt; — Run a shell command on the server\n\n"
    "<b>📊 Monitoring:</b>\n"
    "├ /stats — Users, sessions, uptime &amp; mode\n"
    "└ /ping — Bot latency &amp; uptime\n\n"
    "<b>📡 Broadcasting:</b>\n"
    "└ /broadcast &lt;text&gt; — Send message to all users\n\n"
    "<b>🚫 User Control:</b>\n"
    "├ /ban &lt;user_id&gt; — Ban a user from the bot\n"
    "├ /unban &lt;user_id&gt; — Remove a ban\n"
    "├ /addadmin &lt;user_id&gt; — Add an admin\n"
    "├ /deladmin &lt;user_id&gt; — Remove an admin\n"
    "├ /admins — List all admins\n"
    "├ /pvt — Switch to private mode\n"
    "└ /pub — Switch to public mode"
)


@Client.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    from config import OWNER_ID
    uid = message.from_user.id

    # Show owner commands section to the owner
    full_text = HELP_TEXT
    if uid == OWNER_ID:
        full_text += f"\n\n{OWNER_HELP_TEXT}"

    await message.reply_text(
        full_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Home", callback_data="start|back"),
        ]]),
        parse_mode=enums.ParseMode.HTML,
    )
