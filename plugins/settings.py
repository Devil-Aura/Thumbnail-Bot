"""
/settings — per-user settings for GFX and Cover channels.

State machine (in-memory):
  settings_state[uid] = {
      "step": "gfx_add_ch" | "cover_add_ch" | "cover_add_cmd",
      "pending_ch_id": int,
      "pending_title": str,
  }
"""
import logging
from pyrogram import Client, StopPropagation, enums, filters
from pyrogram.types import (
    CallbackQuery, Message,
    InlineKeyboardButton, InlineKeyboardMarkup,
)

logger = logging.getLogger(__name__)

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
    "🎬 <b>Anime GFX Channels</b>\n"
    "Thumbnails posted here include the GFX copyright caption.\n\n"
    "🖼 <b>Cover Channels</b>\n"
    "Thumbnail is sent + auto-replied with your chosen command.\n\n"
    "Use the buttons below to manage your channels."
)


# ── /settings command ──────────────────────────────────────────────────────────
@Client.on_message(filters.command("settings") & filters.private)
async def settings_cmd(client: Client, message: Message):
    await client.db.add_user(message.from_user.id)
    # Clear any stale state when user re-opens settings
    settings_state.pop(message.from_user.id, None)
    await message.reply_text(
        SETTINGS_TEXT,
        reply_markup=_main_kb(),
        parse_mode=enums.ParseMode.HTML,
    )


# ── Callback handler ───────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^cfg\|"))
async def settings_cb(client: Client, cq: CallbackQuery):
    uid    = cq.from_user.id
    parts  = cq.data.split("|")
    action = parts[1]

    if action == "noop":
        await cq.answer()
        return

    if action == "close":
        settings_state.pop(uid, None)
        await cq.message.delete()
        await cq.answer()
        return

    if action == "main":
        settings_state.pop(uid, None)
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
        await cq.message.edit_text(
            f"🎬 <b>Anime GFX Channels</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"You have <b>{len(chs)}</b> channel(s) added.\n\n"
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
            "Send the <b>channel ID</b>\n"
            "Example: <code>-1001234567890</code>\n\n"
            "Or simply <b>forward any message</b> from that channel.\n\n"
            "<i>Make sure the bot is an admin in that channel first.</i>",
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
            f"🎬 <b>Anime GFX Channels</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
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
            f"Thumbnail is sent + replied with your command + anime title.",
            reply_markup=_cover_kb(chs),
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer()
        return

    # ── Cover add ─────────────────────────────────────────────────────────────
    if action == "cover_add":
        settings_state[uid] = {"step": "cover_add_ch"}
        await cq.message.edit_text(
            "🖼 <b>Add Cover Channel — Step 1 of 2</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send the <b>channel ID</b>\n"
            "Example: <code>-1001234567890</code>\n\n"
            "Or simply <b>forward any message</b> from that channel.\n\n"
            "<i>Make sure the bot is an admin in that channel first.</i>",
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
            f"🖼 <b>Cover Channels</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"You have <b>{len(chs)}</b> channel(s) added.",
            reply_markup=_cover_kb(chs),
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer("✅ Channel removed.")
        return

    await cq.answer()


# ── Text/command input handler for active settings flows ──────────────────────
@Client.on_message(filters.private, group=1)
async def settings_input(client: Client, message: Message):
    """
    Group=1 so this runs AFTER all group=0 command handlers.
    Only processes messages when the user is in an active settings flow.
    Raises StopPropagation after handling so no other handler fires.
    """
    uid = message.from_user.id

    if uid not in settings_state:
        return

    state = settings_state[uid]
    step  = state["step"]

    # For every step EXCEPT cover_add_cmd, ignore slash-commands entirely
    # and clear the stale state so the real command handler can proceed.
    if message.text and message.text.startswith("/") and step != "cover_add_cmd":
        settings_state.pop(uid, None)
        return

    # ── GFX: waiting for channel ID / forward ─────────────────────────────────
    if step == "gfx_add_ch":
        ch_id, title = await _resolve_channel(client, message)
        if ch_id is None:
            await message.reply_text(
                "❌ <b>Could not identify that channel.</b>\n\n"
                "Please send the channel ID\n"
                "Example: <code>-1001234567890</code>\n\n"
                "Or forward a message from the channel.",
                parse_mode=enums.ParseMode.HTML,
            )
            raise StopPropagation

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
        raise StopPropagation

    # ── Cover: Step 1 — waiting for channel ID / forward ─────────────────────
    if step == "cover_add_ch":
        ch_id, title = await _resolve_channel(client, message)
        if ch_id is None:
            await message.reply_text(
                "❌ <b>Could not identify that channel.</b>\n\n"
                "Please send the channel ID\n"
                "Example: <code>-1001234567890</code>\n\n"
                "Or forward a message from the channel.",
                parse_mode=enums.ParseMode.HTML,
            )
            raise StopPropagation

        state["pending_ch_id"] = ch_id
        state["pending_title"] = title
        state["step"]          = "cover_add_cmd"

        await message.reply_text(
            f"✅ <b>Channel saved!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📺 <b>Channel :</b> <code>{title}</code>\n\n"
            f"<b>Step 2 of 2 — Send the command</b>\n"
            f"This is the bot command that will be auto-sent as a reply.\n\n"
            f"Type it with or without <code>/</code>:\n"
            f"  • <code>/cover</code>\n"
            f"  • <code>/thumb</code>\n"
            f"  • <code>cover</code>  (slash added automatically)",
            parse_mode=enums.ParseMode.HTML,
        )
        raise StopPropagation

    # ── Cover: Step 2 — waiting for the command (e.g. /cover, /thumb) ────────
    if step == "cover_add_cmd":
        raw_cmd = (message.text or "").strip()
        if not raw_cmd:
            await message.reply_text(
                "⚠️ Please send a command, e.g. <code>/cover</code>",
                parse_mode=enums.ParseMode.HTML,
            )
            raise StopPropagation

        # Auto-prefix slash if the user forgot it
        if not raw_cmd.startswith("/"):
            raw_cmd = "/" + raw_cmd

        # Strip any @BotUsername suffix Telegram may append
        raw_cmd = raw_cmd.split("@")[0]

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
                f"✅ <b>Cover Channel Added!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📺 <b>Channel :</b> <code>{title}</code>\n"
                f"💬 <b>Command :</b> <code>{command}</code>\n\n"
                f"Use /settings to manage your channels.",
                parse_mode=enums.ParseMode.HTML,
            )
        raise StopPropagation


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
