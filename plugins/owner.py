"""
Owner-only commands:

  /restart              — restart the bot immediately
  /stats                — bot statistics (users, banned, sessions, uptime)
  /ping                 — measure bot response latency
  /broadcast <text>     — send a message to every user in the database
  /ban <user_id>        — ban a user from using the bot
  /unban <user_id>      — remove a ban
  /shell <command>      — run a shell command on the server (dangerous!)
"""
import asyncio
import os
import sys
import io
import time
import subprocess
from datetime import datetime, timezone

from pyrogram import Client, enums, filters
from pyrogram.types import Message
from config import OWNER_ID

# Track when the bot process started
_START_TIME = datetime.now(timezone.utc)


def _is_owner(uid: int) -> bool:
    return uid == OWNER_ID


def _uptime() -> str:
    delta = datetime.now(timezone.utc) - _START_TIME
    total = int(delta.total_seconds())
    days,  rem  = divmod(total, 86400)
    hours, rem  = divmod(rem,   3600)
    mins,  secs = divmod(rem,   60)
    parts = []
    if days:  parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if mins:  parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# /restart
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("restart") & filters.private, group=-2)
async def restart_cmd(client: Client, message: Message):
    if not _is_owner(message.from_user.id):
        await message.reply_text(
            "❌ <b>Owner only command.</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    now = datetime.now().strftime("%d %b %Y · %H:%M:%S")
    await message.reply_text(
        "🔄 <b>Restarting Bot...</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 <b>Time:</b> <code>{now}</code>\n"
        f"⏱ <b>Uptime before restart:</b> <code>{_uptime()}</code>\n\n"
        "⚡ Bot will be back in a few seconds.",
        parse_mode=enums.ParseMode.HTML,
    )
    await asyncio.sleep(1)
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ─────────────────────────────────────────────────────────────────────────────
# /stats
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("stats") & filters.private, group=-2)
async def stats_cmd(client: Client, message: Message):
    if not _is_owner(message.from_user.id):
        await message.reply_text(
            "❌ <b>Owner only command.</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    status = await message.reply_text(
        "📊 <b>Fetching stats...</b>",
        parse_mode=enums.ParseMode.HTML,
    )

    try:
        total_users  = await client.db.total_users()
        banned_users = await client.db.total_banned()
        admins       = await client.db.get_admins()
        is_pvt       = await client.db.get_pvt_mode()
    except Exception as e:
        await status.edit_text(
            f"❌ <b>DB error:</b> <code>{e}</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # Import live session counts from anime.py state
    try:
        from plugins.anime import sessions, post_sessions
        active_sessions = len(sessions)
        post_s          = len(post_sessions)
    except Exception:
        active_sessions = post_s = 0

    mode_icon = "🔒 Private" if is_pvt else "🌐 Public"
    now       = datetime.now().strftime("%d %b %Y · %H:%M")

    await status.edit_text(
        "📊 <b>Bot Statistics</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Total Users:</b> <code>{total_users}</code>\n"
        f"🚫 <b>Banned Users:</b> <code>{banned_users}</code>\n"
        f"👮 <b>Admins:</b> <code>{len(admins)}</code>\n"
        f"🔐 <b>Bot Mode:</b> {mode_icon}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎨 <b>Active Previews:</b> <code>{active_sessions}</code>\n"
        f"📤 <b>Pending Posts:</b> <code>{post_s}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>Uptime:</b> <code>{_uptime()}</code>\n"
        f"🕐 <b>Checked at:</b> <code>{now}</code>",
        parse_mode=enums.ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /ping
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("ping") & filters.private)
async def ping_cmd(client: Client, message: Message):
    start = time.monotonic()
    reply = await message.reply_text(
        "🏓 <b>Pong!</b>",
        parse_mode=enums.ParseMode.HTML,
    )
    latency = (time.monotonic() - start) * 1000

    await reply.edit_text(
        "🏓 <b>Pong!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>Latency:</b> <code>{latency:.1f} ms</code>\n"
        f"⏱ <b>Uptime:</b> <code>{_uptime()}</code>",
        parse_mode=enums.ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /broadcast
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("broadcast") & filters.private, group=-2)
async def broadcast_cmd(client: Client, message: Message):
    if not _is_owner(message.from_user.id):
        await message.reply_text(
            "❌ <b>Owner only command.</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    text = " ".join(message.command[1:]).strip()
    if not text:
        await message.reply_text(
            "⚠️ <b>Usage:</b>\n"
            "<code>/broadcast Your message here</code>\n\n"
            "<blockquote>"
            "Sends the message to every user in the database.\n"
            "Supports HTML formatting."
            "</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    status = await message.reply_text(
        "📡 <b>Broadcasting...</b>",
        parse_mode=enums.ParseMode.HTML,
    )

    user_ids = await client.db.get_all_user_ids()
    total    = len(user_ids)
    sent = failed = blocked = 0

    for uid in user_ids:
        try:
            await client.send_message(
                chat_id=uid,
                text=text,
                parse_mode=enums.ParseMode.HTML,
            )
            sent += 1
        except Exception as e:
            err = str(e).lower()
            if "blocked" in err or "deactivated" in err or "not found" in err:
                blocked += 1
            else:
                failed += 1
        await asyncio.sleep(0.05)   # ~20 msg/s, stay under limits

    now = datetime.now().strftime("%d %b %Y · %H:%M")
    await status.edit_text(
        "📡 <b>Broadcast Complete!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Total Users:</b> <code>{total}</code>\n"
        f"✅ <b>Delivered:</b> <code>{sent}</code>\n"
        f"🚫 <b>Blocked/Inactive:</b> <code>{blocked}</code>\n"
        f"❌ <b>Failed:</b> <code>{failed}</code>\n"
        f"🕐 <b>Finished at:</b> <code>{now}</code>",
        parse_mode=enums.ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /ban  /unban
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("ban") & filters.private, group=-2)
async def ban_cmd(client: Client, message: Message):
    if not _is_owner(message.from_user.id):
        await message.reply_text(
            "❌ <b>Owner only command.</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    args = message.command[1:]
    if not args or not args[0].lstrip("-").isdigit():
        await message.reply_text(
            "⚠️ <b>Usage:</b> <code>/ban &lt;user_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    target = int(args[0])
    if target == OWNER_ID:
        await message.reply_text(
            "❌ <b>You cannot ban yourself.</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    await client.db.ban_user(target)
    await message.reply_text(
        f"🚫 <b>User Banned</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User ID:</b> <code>{target}</code>\n\n"
        f"They can no longer use the bot.\n"
        f"Use <code>/unban {target}</code> to restore access.",
        parse_mode=enums.ParseMode.HTML,
    )


@Client.on_message(filters.command("unban") & filters.private, group=-2)
async def unban_cmd(client: Client, message: Message):
    if not _is_owner(message.from_user.id):
        await message.reply_text(
            "❌ <b>Owner only command.</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    args = message.command[1:]
    if not args or not args[0].lstrip("-").isdigit():
        await message.reply_text(
            "⚠️ <b>Usage:</b> <code>/unban &lt;user_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    target = int(args[0])
    await client.db.unban_user(target)
    await message.reply_text(
        f"✅ <b>User Unbanned</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User ID:</b> <code>{target}</code>\n\n"
        f"They can use the bot again.",
        parse_mode=enums.ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /shell
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("shell") & filters.private, group=-2)
async def shell_cmd(client: Client, message: Message):
    if not _is_owner(message.from_user.id):
        await message.reply_text(
            "❌ <b>Owner only command.</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    cmd = " ".join(message.command[1:]).strip()
    if not cmd:
        await message.reply_text(
            "⚠️ <b>Usage:</b> <code>/shell &lt;command&gt;</code>\n\n"
            "<blockquote>⚠️ This executes shell commands directly on the server. "
            "Use with extreme caution.</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    status = await message.reply_text(
        f"⚙️ <b>Running:</b> <code>{cmd}</code>",
        parse_mode=enums.ParseMode.HTML,
    )

    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        rc     = proc.returncode
    except subprocess.TimeoutExpired:
        await status.edit_text(
            f"⏱ <b>Timed out</b> after 30s\n"
            f"<code>{cmd}</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return
    except Exception as e:
        await status.edit_text(
            f"❌ <b>Error:</b> <code>{e}</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    icon = "✅" if rc == 0 else "❌"
    out  = stdout or stderr or "(no output)"

    # Truncate long output to fit Telegram's 4096-char limit
    if len(out) > 3500:
        out = out[:3500] + "\n…(truncated)"

    await status.edit_text(
        f"{icon} <b>Exit code:</b> <code>{rc}</code>\n"
        f"<b>Command:</b> <code>{cmd}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote><code>{out}</code></blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )
