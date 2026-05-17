import asyncio
import os
import sys
import shutil
import subprocess
import tempfile
from datetime import datetime
from urllib.parse import urlparse

from pyrogram import Client, enums, filters
from pyrogram.types import Message
from config import OWNER_ID, GITHUB_PAT


def _is_owner(uid: int) -> bool:
    return uid == OWNER_ID


# ─────────────────────────────────────────────────────────────────────────────
# /update — pull from same origin repo and restart
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("update") & filters.private, group=-2)
async def update_cmd(client: Client, message: Message):
    """Runs at group=-2, BEFORE pvt_gate. Owner check is inside."""
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

    try:
        before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        before = ""

    try:
        subprocess.run(["git", "fetch", "--all"], capture_output=True, timeout=30)
        pull = subprocess.run(
            ["git", "pull"],
            capture_output=True, text=True, timeout=60,
        )
        pull_out = pull.stdout.strip()
    except subprocess.TimeoutExpired:
        await status.edit_text(
            "❌ <b>Update failed</b> — git pull timed out.",
            parse_mode=enums.ParseMode.HTML,
        )
        return
    except FileNotFoundError:
        await status.edit_text(
            "❌ <b>Update failed</b> — <code>git</code> not installed.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    if "Already up to date" in pull_out or "Already up-to-date" in pull_out:
        await status.edit_text(
            "✅ <b>Already up to date!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "No new changes on GitHub. Bot is on the latest version.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    commits_text = ""
    try:
        raw_log = subprocess.run(
            ["git", "log", "--pretty=format:%h — %s", f"{before}..HEAD"],
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

    now = datetime.now().strftime("%d %b %Y · %H:%M")
    msg = (
        "✅ <b>Update Successful!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 <b>Updated at:</b> <code>{now}</code>\n"
    )
    if commits_text:
        msg += f"\n📝 <b>New Commits:</b>\n<blockquote>{commits_text}</blockquote>\n"
    if files_text:
        msg += (
            f"\n📁 <b>Changed Files:</b>\n"
            f"<blockquote>{files_text}\n\n"
            f"🟢 Added  🟡 Modified  🔴 Deleted  🔵 Renamed</blockquote>\n"
        )
    msg += "\n⚡ <b>Restarting bot in 3 seconds...</b>"

    await status.edit_text(msg, parse_mode=enums.ParseMode.HTML)
    await asyncio.sleep(3)
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ─────────────────────────────────────────────────────────────────────────────
# /update_repo — clone a *different* (but similar) repo, replace files, restart
# ─────────────────────────────────────────────────────────────────────────────

# Files that must never be overwritten from the foreign repo
_PRESERVE = {
    "config.py",
    ".env",
    "thumbnail_bot.session",
    "thumbnail_bot.session-journal",
    "Procfile",
}

# Top-level entries that are never copied (git internals, OS noise)
_SKIP_ALWAYS = {".git", ".gitignore", "__pycache__", ".DS_Store"}


@Client.on_message(filters.command("update_repo") & filters.private, group=-2)
async def update_repo_cmd(client: Client, message: Message):
    """
    /update_repo <github_url>

    Clones the given GitHub repository (a similar Thumbnail-Bot fork from
    a different user), copies all files except config.py and session files
    into the current bot directory, then restarts the bot.

    Owner-only command.
    """
    if not _is_owner(message.from_user.id):
        await message.reply_text(
            "❌ <b>Owner only command.</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    args = message.command[1:]
    if not args:
        await message.reply_text(
            "⚠️ <b>Usage:</b>\n"
            "<code>/update_repo https://github.com/user/repo</code>\n\n"
            "<blockquote>"
            "Clones the given GitHub repo (a similar Thumbnail-Bot fork),\n"
            "copies all its files into the current bot directory — preserving\n"
            "your <code>config.py</code> and session files — then restarts."
            "</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    repo_url = args[0].strip().rstrip("/")

    if not repo_url.startswith("https://github.com/"):
        await message.reply_text(
            "❌ <b>Invalid URL.</b>\n"
            "Please provide a valid GitHub HTTPS URL.\n\n"
            "<b>Example:</b>\n"
            "<code>/update_repo https://github.com/someuser/Thumbnail-Bot</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    parsed = urlparse(repo_url)
    path_parts = parsed.path.strip("/").split("/")
    repo_display = "/".join(path_parts[:2]) if len(path_parts) >= 2 else repo_url

    status = await message.reply_text(
        f"📦 <b>Cloning repository...</b>\n"
        f"<blockquote>Source: <code>{repo_display}</code></blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )

    # Build authenticated URL if PAT is available
    if GITHUB_PAT:
        auth_url = f"https://{GITHUB_PAT}@{parsed.netloc}{parsed.path}"
    else:
        auth_url = repo_url

    tmpdir = tempfile.mkdtemp(prefix="tgbot_repo_")
    try:
        # ── Clone ──────────────────────────────────────────────────────────
        clone = subprocess.run(
            ["git", "clone", "--depth=1", auth_url, tmpdir],
            capture_output=True, text=True, timeout=120,
        )

        if clone.returncode != 0:
            err = clone.stderr.replace(GITHUB_PAT, "***") if GITHUB_PAT else clone.stderr
            err_short = err.strip()[:600] or "Unknown error."
            await status.edit_text(
                "❌ <b>Clone Failed!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<blockquote>{err_short}</blockquote>\n\n"
                "Make sure the URL is correct and the repo is accessible.",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        await status.edit_text(
            f"📦 <b>Cloned successfully.</b>\n"
            f"<blockquote>Source: <code>{repo_display}</code></blockquote>\n\n"
            "⚙️ <b>Copying files...</b>",
            parse_mode=enums.ParseMode.HTML,
        )

        # ── Get latest commits from the cloned repo ────────────────────────
        commit_log = ""
        try:
            raw_log = subprocess.run(
                ["git", "-C", tmpdir, "log", "--pretty=format:%h — %s", "-6"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
            if raw_log:
                lines = raw_log.split("\n")
                commit_log = "\n".join(
                    f"  {'└' if i == len(lines) - 1 else '├'} <code>{l}</code>"
                    for i, l in enumerate(lines)
                )
        except Exception:
            pass

        # ── Determine bot root (two levels up: plugins/ → bot root) ───────
        bot_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # ── Copy files ─────────────────────────────────────────────────────
        copied, preserved = [], []
        for entry in os.listdir(tmpdir):
            if entry in _SKIP_ALWAYS:
                continue
            if entry in _PRESERVE:
                preserved.append(entry)
                continue

            src = os.path.join(tmpdir, entry)
            dst = os.path.join(bot_dir, entry)

            try:
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                copied.append(entry)
            except Exception as copy_err:
                preserved.append(f"{entry} ⚠️ error: {copy_err}")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ── Build rich success message ─────────────────────────────────────────
    now = datetime.now().strftime("%d %b %Y · %H:%M")

    copied_text = ""
    if copied:
        c_lines = [
            f"  {'└' if i == len(copied) - 1 else '├'} <code>{f}</code>"
            for i, f in enumerate(copied)
        ]
        copied_text = "\n".join(c_lines)

    preserved_text = ""
    if preserved:
        p_lines = [
            f"  {'└' if i == len(preserved) - 1 else '├'} <code>{f}</code>"
            for i, f in enumerate(preserved)
        ]
        preserved_text = "\n".join(p_lines)

    msg = (
        "✅ <b>Repo Update Successful!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Source:</b> <code>{repo_display}</code>\n"
        f"🕐 <b>Updated at:</b> <code>{now}</code>\n"
    )

    if commit_log:
        msg += f"\n📝 <b>Latest Commits:</b>\n<blockquote>{commit_log}</blockquote>\n"

    if copied_text:
        msg += (
            f"\n📂 <b>Files Replaced</b> ({len(copied)}):\n"
            f"<blockquote>{copied_text}</blockquote>\n"
        )

    if preserved_text:
        msg += (
            f"\n🔒 <b>Preserved</b> ({len(preserved)}):\n"
            f"<blockquote>{preserved_text}</blockquote>\n"
        )

    msg += "\n⚡ <b>Restarting bot in 3 seconds...</b>"

    await status.edit_text(msg, parse_mode=enums.ParseMode.HTML)
    await asyncio.sleep(3)
    os.execv(sys.executable, [sys.executable] + sys.argv)
