"""
/update — Pull latest changes from GitHub and restart the bot (owner only).
Shows a professional changelog: new commits + changed files, then hot-restarts.
Runs at group=-2 so it always fires before the pvt gate.
"""
import asyncio
import os
import sys
import subprocess
from datetime import datetime

from pyrogram import Client, enums, filters
from pyrogram.types import Message
from config import OWNER_ID


def _is_owner(uid: int) -> bool:
    return uid == OWNER_ID


# group=-2 → runs BEFORE pvt_gate (group=-1), owner check is inside
@Client.on_message(filters.command("update") & filters.private, group=-2)
async def update_cmd(client: Client, message: Message):
    if not _is_owner(message.from_user.id):
        await message.reply_text(
            "❌ <b>Owner only command.</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    status = await message.reply_text(
        "🔍 <b>Checking for updates...</b>",
        parse_mode=enums.ParseMode.HTML,
    )

    # ── Capture HEAD before pull ───────────────────────────────────────────────
    try:
        before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        before = ""

    # ── git fetch + pull ───────────────────────────────────────────────────────
    try:
        subprocess.run(["git", "fetch", "--all"],
                       capture_output=True, timeout=30)
        pull = subprocess.run(
            ["git", "pull"],
            capture_output=True, text=True, timeout=60,
        )
        pull_out = pull.stdout.strip()
    except subprocess.TimeoutExpired:
        await status.edit_text(
            "❌ <b>Update failed</b> — git pull timed out.\n"
            "Check your VPS internet connection.",
            parse_mode=enums.ParseMode.HTML,
        )
        return
    except FileNotFoundError:
        await status.edit_text(
            "❌ <b>Update failed</b> — <code>git</code> is not installed.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # ── Already up to date ─────────────────────────────────────────────────────
    if "Already up to date" in pull_out or "Already up-to-date" in pull_out:
        await status.edit_text(
            "✅ <b>Already up to date!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "No new changes were found on GitHub.\n\n"
            "<i>The bot is running the latest version.</i>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # ── New commits ────────────────────────────────────────────────────────────
    commits_text = ""
    try:
        raw_log = subprocess.run(
            ["git", "log", "--pretty=format:%h ─ %s", f"{before}..HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if raw_log:
            lines = raw_log.split("\n")[:12]
            commits_text = "\n".join(
                f"  {'└' if i == len(lines) - 1 else '├'} <code>{l}</code>"
                for i, l in enumerate(lines)
            )
    except Exception:
        pass

    # ── Changed files with status icons ───────────────────────────────────────
    files_text = ""
    try:
        raw_files = subprocess.run(
            ["git", "diff", "--name-status", before, "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if raw_files:
            icons = {"A": "🟢", "M": "🟡", "D": "🔴", "R": "🔵"}
            flines = []
            for fl in raw_files.split("\n")[:15]:
                parts = fl.split("\t", 1)
                if len(parts) == 2:
                    icon = icons.get(parts[0][0], "⚪")
                    flines.append(f"  ├ {icon} <code>{parts[1]}</code>")
            if flines:
                flines[-1] = flines[-1].replace("  ├", "  └")
                files_text = "\n".join(flines)
    except Exception:
        pass

    # ── Build changelog ────────────────────────────────────────────────────────
    now = datetime.now().strftime("%d %b %Y · %H:%M")
    msg = (
        "✅ <b>Update Successful!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 <b>Updated at:</b> {now}\n"
    )
    if commits_text:
        msg += f"\n📝 <b>New Commits:</b>\n{commits_text}\n"
    if files_text:
        msg += (
            f"\n📁 <b>Changed Files:</b>\n"
            f"<blockquote>{files_text}\n\n"
            f"🟢 Added  🟡 Modified  🔴 Deleted  🔵 Renamed</blockquote>\n"
        )
    msg += "\n⚡ <b>Restarting bot in 3 seconds...</b>"

    await status.edit_text(msg, parse_mode=enums.ParseMode.HTML)
    await asyncio.sleep(3)

    # ── Hot restart ────────────────────────────────────────────────────────────
    os.execv(sys.executable, [sys.executable] + sys.argv)
