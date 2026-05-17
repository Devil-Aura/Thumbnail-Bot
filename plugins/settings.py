"""
/settings — per-user settings for GFX and Cover channels.

State machine (in-memory):
  settings_state[uid] = {
      "step": "gfx_add_ch" | "gfx_add_cmd" | "cover_add_ch" | "cover_add_cmd",
      "pending_ch_id": int,
      "pending_title": str,
  }
"""
import logging
from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery, Message,
    InlineKeyboardButton, InlineKeyboardMarkup,
)

logger = logging.getLogger(__name__)

# uid → {"step": ..., "pending_ch_id": ..., "pending_title": ...}
settings_state: dict[int, dict] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Anime GFX Channels", callback_data="cfg|gfx"),
            InlineKeyboardButton("🖼 Cover Channels",     callback_data="cfg|cover"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="cfg|close")],
    ])


def _gfx_kb(channels: list) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        label = ch["title"] or str(ch["id"])
        rows.append([
            InlineKeyboardButton(f"📺 {label}", callback_data="cfg|noop"),
            InlineKeyboardButton("🗑 Remove",   callback_data=f"cfg|gfx_del|{ch['id']}"),
        ])
    rows.append([
        InlineKeyboardButton("➕ Add Channel", callback_data="cfg|gfx_add"),
        InlineKeyboardButton("⬅️ Back",        callback_data="cfg|main"),
    ])
    return InlineKeyboardMarkup(rows)


def _cover_kb(channels: list) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        label = ch["title"] or str(ch["id"])
        cmd   = ch.get("command", "")
        rows.append([
            InlineKeyboardButton(f"📺 {label} → {cmd}", callback_data="cfg|noop"),
            InlineKeyboardButton("🗑 Remove",            callback_data=f"cfg|cov_del|{ch['id']}"),
        ])
    rows.append([
        InlineKeyboardButton("➕ Add Channel", callback_data="cfg|cover_add"),
        InlineKeyboardButton("⬅️ Back",        callback_data="cfg|main"),
    ])
    return InlineKeyboardMarkup(rows)


SETTINGS_TEXT = (
    "⚙️ <b>Settings</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "🎬 <b>Anime GFX Channels</b> — channels where the thumbnail is sent with GFX caption.\n\n"
    "🖼 <b>Cover Channels</b> — channels where the thumbnail + reply command is sent.\n\n"
    "Use the buttons below to manage your channels."
)


# ── /settings command ──────────────────────────────────────────────────────────
@Client.on_message(filters.command("settings") & filters.private)
async def settings_cmd(client: Client, message: Message):
    await client.db.add_user(message.from_user.id)
    await message.reply_text(
        SETTINGS_TEXT,
        reply_markup=_main_kb(),
        parse_mode=enums.ParseMode.HTML,
    )


# ── Callback handler ───────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^cfg\|"))
async def settings_cb(client: Client, cq: CallbackQuery):
    uid   = cq.from_user.id
    parts = cq.data.split("|")
    action = parts[1]

    if action == "noop":
        await cq.answer()
        return

    if action == "close":
        await cq.message.delete()
        await cq.answer()
        return

    if action == "main":
        await cq.message.edit_text(
            SETTINGS_TEXT,
            reply_markup=_main_kb(),
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer()
        return

    # ── GFX list ──────────────────────────────────────────────────────────────
    if action == "gfx":
        chs = await client.db.get_gfx_channels(uid)
        count = len(chs)
        await cq.message.edit_text(
            f"🎬 <b>Anime GFX Channels</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"You have <b>{count}</b> channel(s) added.\n\n"
            f"Thumbnails sent here will include the GFX copyright caption.",
            reply_markup=_gfx_kb(chs),
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer()
        return

    # ── GFX add ───────────────────────────────────────────────────────────────
    if action == "gfx_add":
        settings_state[uid] = {"step": "gfx_add_ch"}
        await cq.message.edit_text(
            "🎬 <b>Add Anime GFX Channel</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send the <b>channel ID</b> (e.g. <code>-1001234567890</code>) "
            "or <b>forward any message</b> from the channel.\n\n"
            "<i>Make sure the bot is admin in that channel.</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="cfg|gfx"),
            ]]),
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer()
        return

    # ── GFX delete ────────────────────────────────────────────────────────────
    if action == "gfx_del":
        ch_id = int(parts[2])
        await client.db.remove_gfx_channel(uid, ch_id)
        chs = await client.db.get_gfx_channels(uid)
        await cq.message.edit_text(
            f"🎬 <b>Anime GFX Channels</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"You have <b>{len(chs)}</b> channel(s) added.",
            reply_markup=_gfx_kb(chs),
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer("✅ Channel removed.")
        return

    # ── Cover list ────────────────────────────────────────────────────────────
    if action == "cover":
        chs = await client.db.get_cover_channels(uid)
        await cq.message.edit_text(
            f"🖼 <b>Cover Channels</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"You have <b>{len(chs)}</b> channel(s) added.\n\n"
            f"Thumbnail is sent + replied with <code>/command Anime Title</code>.",
            reply_markup=_cover_kb(chs),
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer()
        return

    # ── Cover add ─────────────────────────────────────────────────────────────
    if action == "cover_add":
        settings_state[uid] = {"step": "cover_add_ch"}
        await cq.message.edit_text(
            "🖼 <b>Add Cover Channel</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send the <b>channel ID</b> (e.g. <code>-1001234567890</code>) "
            "or <b>forward any message</b> from the channel.\n\n"
            "<i>Make sure the bot is admin in that channel.</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="cfg|cover"),
            ]]),
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer()
        return

    # ── Cover delete ──────────────────────────────────────────────────────────
    if action == "cov_del":
        ch_id = int(parts[2])
        await client.db.remove_cover_channel(uid, ch_id)
        chs = await client.db.get_cover_channels(uid)
        await cq.message.edit_text(
            f"🖼 <b>Cover Channels</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"You have <b>{len(chs)}</b> channel(s) added.",
            reply_markup=_cover_kb(chs),
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer("✅ Channel removed.")
        return

    await cq.answer()


# ── Text input handler for settings flow ──────────────────────────────────────
@Client.on_message(filters.private)
async def settings_input(client: Client, message: Message):
    uid = message.from_user.id

    # Drop users who are not in any settings flow
    if uid not in settings_state:
        return

    state = settings_state[uid]
    step  = state["step"]

    # When we are waiting for the cover command the user MUST send something
    # like "/cover" or "/thumb" — that starts with "/", so we must NOT block
    # it here.  For every other step we ignore slash-commands so they fall
    # through to their own handlers (e.g. /settings, /anime, etc.).
    if message.text and message.text.startswith("/") and step != "cover_add_cmd":
        settings_state.pop(uid, None)   # clear stale state so bot isn't stuck
        return

    # ── GFX: waiting for channel ──────────────────────────────────────────────
    if step == "gfx_add_ch":
        ch_id, title = await _resolve_channel(client, message)
        if ch_id is None:
            await message.reply_text(
                "❌ <b>Could not identify channel.</b>\n"
                "Send the channel ID (e.g. <code>-1001234567890</code>) "
                "or forward a message from the channel.",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        added = await client.db.add_gfx_channel(uid, ch_id, title)
        settings_state.pop(uid, None)

        if not added:
            await message.reply_text(
                f"⚠️ <b>{title}</b> is already in your GFX list.",
                parse_mode=enums.ParseMode.HTML,
            )
        else:
            await message.reply_text(
                f"✅ <b>{title}</b> added to Anime GFX Channels!\n\n"
                f"Use /settings to manage your channels.",
                parse_mode=enums.ParseMode.HTML,
            )
        return

    # ── Cover: waiting for channel ────────────────────────────────────────────
    if step == "cover_add_ch":
        ch_id, title = await _resolve_channel(client, message)
        if ch_id is None:
            await message.reply_text(
                "❌ <b>Could not identify channel.</b> Try again.",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        state["pending_ch_id"] = ch_id
        state["pending_title"] = title
        state["step"]          = "cover_add_cmd"

        await message.reply_text(
            f"✅ <b>Channel:</b> <code>{title}</code>\n\n"
            "Now send the <b>command</b> for this channel.\n"
            "<b>Example:</b> <code>/cover</code> or <code>/thumb</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # ── Cover: waiting for command (e.g. /cover or /thumb) ───────────────────
    if step == "cover_add_cmd":
        raw_cmd = (message.text or "").strip()
        if not raw_cmd:
            await message.reply_text(
                "⚠️ Please send the command, e.g. <code>/cover</code>",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        if not raw_cmd.startswith("/"):
            raw_cmd = "/" + raw_cmd

        ch_id   = state["pending_ch_id"]
        title   = state["pending_title"]
        command = raw_cmd

        added = await client.db.add_cover_channel(uid, ch_id, title, command)
        settings_state.pop(uid, None)

        if not added:
            await message.reply_text(
                f"⚠️ <b>{title}</b> is already in your Cover list.",
                parse_mode=enums.ParseMode.HTML,
            )
        else:
            await message.reply_text(
                f"✅ <b>{title}</b> added with command <code>{command}</code>!\n\n"
                f"Use /settings to manage your channels.",
                parse_mode=enums.ParseMode.HTML,
            )
        return


async def _resolve_channel(client: Client, message: Message) -> tuple[int | None, str]:
    """Return (channel_id, title) from forwarded message or text ID."""
    if message.forward_from_chat:
        chat = message.forward_from_chat
        return chat.id, chat.title or str(chat.id)

    text = (message.text or "").strip()
    if text.lstrip("-").isdigit():
        ch_id = int(text)
        try:
            chat = await client.get_chat(ch_id)
            return chat.id, chat.title or str(chat.id)
        except Exception:
            return ch_id, str(ch_id)

    if text.startswith("@"):
        try:
            chat = await client.get_chat(text)
            return chat.id, chat.title or text
        except Exception:
            pass

    return None, ""
