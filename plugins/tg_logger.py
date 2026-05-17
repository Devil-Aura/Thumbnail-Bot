"""
Telegram logging handler — forwards ERROR+ logs to the owner's DM.

Setup (called once from bot.py after the Client is ready):
    from plugins.tg_logger import setup_tg_logger
    setup_tg_logger(bot)

Commands:
    /logs  — show the last 30 log entries (owner only)
"""
import asyncio
import logging
import traceback
from collections import deque
from datetime import datetime

from pyrogram import Client, enums, filters
from pyrogram.types import Message
from config import OWNER_ID

# ── In-memory ring buffer of the last 100 records ────────────────────────────
_log_queue: deque = deque(maxlen=100)

# Reference to the live Pyrogram Client (set by setup_tg_logger)
_bot_ref: Client | None = None

_ICONS = {
    "DEBUG":    "🔵",
    "INFO":     "ℹ️",
    "WARNING":  "⚠️",
    "ERROR":    "❌",
    "CRITICAL": "🔥",
}


# ── Custom handler ────────────────────────────────────────────────────────────
class TelegramLogHandler(logging.Handler):
    """Non-blocking handler: stores every record, DMs owner for ERROR+."""

    def emit(self, record: logging.LogRecord) -> None:
        _log_queue.append(record)
        if record.levelno < logging.ERROR:
            return
        if _bot_ref is None:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(_send_to_owner(record))
        except Exception:
            pass


async def _send_to_owner(record: logging.LogRecord) -> None:
    if _bot_ref is None:
        return
    try:
        icon = _ICONS.get(record.levelname, "⚪")
        now  = datetime.fromtimestamp(record.created).strftime("%d %b %Y · %H:%M:%S")

        body = record.getMessage()
        if record.exc_info:
            body += "\n\n" + "".join(traceback.format_exception(*record.exc_info))
        if len(body) > 3000:
            body = body[:3000] + "\n…(truncated)"

        text = (
            f"{icon} <b>{record.levelname}</b>  |  <code>{record.name}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 <code>{now}</code>\n\n"
            f"<blockquote><code>{body}</code></blockquote>"
        )
        await _bot_ref.send_message(
            chat_id=OWNER_ID,
            text=text,
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        pass  # Never recurse on logging errors


# ── Public setup function ─────────────────────────────────────────────────────
def setup_tg_logger(bot: Client) -> None:
    global _bot_ref
    _bot_ref = bot

    handler = TelegramLogHandler()
    handler.setLevel(logging.ERROR)
    handler.setFormatter(logging.Formatter("%(message)s"))

    root = logging.getLogger()
    root.addHandler(handler)

    # Surface pyrofork/pyrogram internal warnings too
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    logging.getLogger("pyrofork").setLevel(logging.WARNING)


# ── /logs command ─────────────────────────────────────────────────────────────
@Client.on_message(filters.command("logs") & filters.private, group=-2)
async def logs_cmd(client: Client, message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply_text(
            "❌ <b>Owner only command.</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    if not _log_queue:
        await message.reply_text(
            "📋 <b>No log entries yet.</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    level_arg = " ".join(message.command[1:]).strip().upper() or "ALL"
    level_map = {
        "DEBUG": 10, "INFO": 20, "WARNING": 30,
        "WARN": 30, "ERROR": 40, "CRITICAL": 50, "ALL": 0,
    }
    min_level = level_map.get(level_arg, 0)

    entries = [r for r in list(_log_queue) if r.levelno >= min_level][-30:]
    if not entries:
        await message.reply_text(
            f"📋 No <b>{level_arg}</b> logs found.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    lines = []
    for r in entries:
        icon = _ICONS.get(r.levelname, "⚪")
        t    = datetime.fromtimestamp(r.created).strftime("%H:%M:%S")
        msg  = r.getMessage()[:180].replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"{icon} <code>[{t}] {r.name}: {msg}</code>")

    await message.reply_text(
        f"📋 <b>Recent Logs</b>  ({len(entries)} entries, filter: {level_arg})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n".join(lines) +
        f"\n\n<i>Use /logs ERROR to see only errors</i>",
        parse_mode=enums.ParseMode.HTML,
    )
