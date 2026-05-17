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


def _short(sha: str) -> str:
    return sha[:7] if sha else "unknown"


def _build_commit_block(raw_log: str) -> str:
    """Parse 'hash|subject|author|reltime' log lines into a rich block."""
    lines = raw_log.strip().split("\n")[:10]
    rows = []
    for line in lines:
        parts = line.split("|", 3)
        if len(parts) == 4:
            h, subject, author, reltime = parts
            rows.append(
                f"  <code>{h}</code>  {subject}\n"
                f"           👤 {author}  ·  🕐 {reltime}"
            )
        else:
            rows.append(f"  <code>{line}</code>")
    return "\n\n".join(rows)


def _build_file_block(raw_diff: str) -> tuple[str, int, int]:
    """Return (formatted text, added_files, deleted_files)."""
    STATUS = {"A": ("🟢", "added"), "M": ("🟡", "modified"),
              "D": ("🔴", "deleted"), "R": ("🔵", "renamed")}
    lines = raw_diff.strip().split("\n")[:20]
    rows, added, deleted = [], 0, 0
    for fl in lines:
        parts = fl.split("\t", 1)
        if len(parts) < 2:
            continue
        code = parts[0][0]
        icon, label = STATUS.get(code, ("⚪", "changed"))
        path = parts[1]
        rows.append(f"  {icon} <code>{path}</code>  <i>({label})</i>")
        if code == "A":
            added += 1
        elif code == "D":
            deleted += 1
    return "\n".join(rows), added, deleted


def _build_stat_line(raw_stat: str) -> str:
    """Extract the summary line '5 files changed, +128, -45'."""
    for line in raw_stat.strip().split("\n"):
        if "file" in line and "changed" in line:
            return line.strip()
    return ""


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
        "🔄 <b>Checking for updates...</b>\n"
        "<blockquote>Fetching latest commits from GitHub...</blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )

    # ── Capture current HEAD ──────────────────────────────────────────────────
    try:
        before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip() or "main"
    except Exception:
        before = ""
        branch = "main"

    # ── Fetch + hard-reset (never blocked by local changes) ──────────────────
    try:
        fetch = subprocess.run(
            ["git", "fetch", "--all"],
            capture_output=True, text=True, timeout=30,
        )
        if fetch.returncode != 0:
            raise RuntimeError(fetch.stderr.strip() or "git fetch failed")
    except subprocess.TimeoutExpired:
        await status.edit_text(
            "❌ <b>Update Failed</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⏱ <code>git fetch</code> timed out after 30s.\n"
            "Check your network connection and try again.",
            parse_mode=enums.ParseMode.HTML,
        )
        return
    except FileNotFoundError:
        await status.edit_text(
            "❌ <b>Update Failed</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<code>git</code> is not installed on this server.",
            parse_mode=enums.ParseMode.HTML,
        )
        return
    except RuntimeError as e:
        await status.edit_text(
            "❌ <b>Update Failed</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote><code>{e}</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # ── Check if already up to date (compare SHAs before touching anything) ──
    try:
        remote_sha = subprocess.run(
            ["git", "rev-parse", f"origin/{branch}"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        remote_sha = ""

    if remote_sha and remote_sha == before:
        now = datetime.now().strftime("%d %b %Y · %H:%M")
        await status.edit_text(
            "✅ <b>Already Up To Date</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌿 <b>Branch:</b>  <code>{branch}</code>\n"
            f"🔖 <b>Commit:</b>  <code>{_short(before)}</code>\n"
            f"📅 <b>Checked:</b> <code>{now}</code>\n\n"
            "No new changes on GitHub. Bot is already on the latest version.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # ── Hard reset — discards local changes, never conflicts ─────────────────
    try:
        reset = subprocess.run(
            ["git", "reset", "--hard", f"origin/{branch}"],
            capture_output=True, text=True, timeout=60,
        )
        if reset.returncode != 0:
            raise RuntimeError(reset.stderr.strip() or "git reset failed")
    except subprocess.TimeoutExpired:
        await status.edit_text(
            "❌ <b>Update Failed</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⏱ <code>git reset</code> timed out after 60s.",
            parse_mode=enums.ParseMode.HTML,
        )
        return
    except RuntimeError as e:
        await status.edit_text(
            "❌ <b>Update Failed</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote><code>{e}</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # ── Capture new HEAD ──────────────────────────────────────────────────────
    try:
        after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        after = ""

    # ── Commit log ───────────────────────────────────────────────────────────
    commit_block = ""
    try:
        raw_log = subprocess.run(
            ["git", "log",
             "--pretty=format:%h|%s|%an|%ar",
             f"{before}..HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if raw_log:
            commit_block = _build_commit_block(raw_log)
    except Exception:
        pass

    # ── Changed files ────────────────────────────────────────────────────────
    file_block = ""
    added_count = deleted_count = 0
    try:
        raw_diff = subprocess.run(
            ["git", "diff", "--name-status", before, "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if raw_diff:
            file_block, added_count, deleted_count = _build_file_block(raw_diff)
    except Exception:
        pass

    # ── Diff stat line ───────────────────────────────────────────────────────
    stat_line = ""
    try:
        raw_stat = subprocess.run(
            ["git", "diff", "--stat", before, "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        stat_line = _build_stat_line(raw_stat)
    except Exception:
        pass

    # ── Count commits ────────────────────────────────────────────────────────
    commit_count = 0
    try:
        commit_count = int(subprocess.run(
            ["git", "rev-list", "--count", f"{before}..HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip() or "0")
    except Exception:
        pass

    now = datetime.now().strftime("%d %b %Y · %H:%M")

    # ── Build the final message ───────────────────────────────────────────────
    msg = (
        "🚀 <b>Bot Updated Successfully!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌿 <b>Branch   :</b>  <code>{branch}</code>\n"
        f"🔖 <b>Revision :</b>  <code>{_short(before)}</code>  →  <code>{_short(after)}</code>\n"
        f"📅 <b>Updated  :</b>  <code>{now}</code>\n"
    )

    if commit_block:
        msg += (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Changelog</b>  ({commit_count} new commit{'s' if commit_count != 1 else ''})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote>{commit_block}</blockquote>\n"
        )

    if file_block:
        total_files = file_block.count("\n") + 1
        msg += (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 <b>Files Changed</b>  ({total_files} file{'s' if total_files != 1 else ''})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote>{file_block}</blockquote>\n"
            f"\n🟢 Added   🟡 Modified   🔴 Deleted   🔵 Renamed\n"
        )

    if stat_line:
        msg += f"\n📊 <code>{stat_line}</code>\n"

    msg += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <b>Restarting bot in 3 seconds...</b>"
    )

    await status.edit_text(msg, parse_mode=enums.ParseMode.HTML)
    await asyncio.sleep(3)
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ─────────────────────────────────────────────────────────────────────────────
# /update_repo — clone a *different* (but similar) repo, replace files, restart
# ─────────────────────────────────────────────────────────────────────────────

_PRESERVE = {
    "config.py",
    ".env",
    "thumbnail_bot.session",
    "thumbnail_bot.session-journal",
    "Procfile",
}

_SKIP_ALWAYS = {".git", ".gitignore", "__pycache__", ".DS_Store"}


@Client.on_message(filters.command("update_repo") & filters.private, group=-2)
async def update_repo_cmd(client: Client, message: Message):
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
        "🚀 <b>Deploying from Repository...</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Source:</b>  <code>{repo_display}</code>\n\n"
        "⏳ Cloning repository...",
        parse_mode=enums.ParseMode.HTML,
    )

    if GITHUB_PAT:
        auth_url = f"https://{GITHUB_PAT}@{parsed.netloc}{parsed.path}"
    else:
        auth_url = repo_url

    tmpdir = tempfile.mkdtemp(prefix="tgbot_repo_")
    try:
        clone = subprocess.run(
            ["git", "clone", "--depth=1", auth_url, tmpdir],
            capture_output=True, text=True, timeout=120,
        )

        if clone.returncode != 0:
            err = clone.stderr.replace(GITHUB_PAT, "***") if GITHUB_PAT else clone.stderr
            err_short = err.strip()[:500] or "Unknown error."
            await status.edit_text(
                "❌ <b>Clone Failed</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 <b>Source:</b>  <code>{repo_display}</code>\n\n"
                f"<blockquote>{err_short}</blockquote>",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        await status.edit_text(
            "🚀 <b>Deploying from Repository...</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>Source:</b>  <code>{repo_display}</code>\n\n"
            "✅ Cloned successfully.  ⏳ Copying files...",
            parse_mode=enums.ParseMode.HTML,
        )

        # ── Get latest commits from cloned repo ───────────────────────────────
        commit_block = ""
        try:
            raw_log = subprocess.run(
                ["git", "-C", tmpdir, "log",
                 "--pretty=format:%h|%s|%an|%ar", "-6"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
            if raw_log:
                commit_block = _build_commit_block(raw_log)
        except Exception:
            pass

        bot_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
                preserved.append(f"{entry} ⚠️ {copy_err}")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    now = datetime.now().strftime("%d %b %Y · %H:%M")

    # ── Build message ─────────────────────────────────────────────────────────
    msg = (
        "🚀 <b>Repo Deployment Successful!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 <b>Source  :</b>  <code>{repo_display}</code>\n"
        f"📅 <b>Deployed:</b>  <code>{now}</code>\n"
    )

    if commit_block:
        msg += (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Latest Commits in Source Repo</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote>{commit_block}</blockquote>\n"
        )

    if copied:
        c_lines = "\n".join(
            f"  {'└' if i == len(copied) - 1 else '├'} <code>{f}</code>"
            for i, f in enumerate(copied)
        )
        msg += (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📂 <b>Files Deployed</b>  ({len(copied)})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote>{c_lines}</blockquote>\n"
        )

    if preserved:
        p_lines = "\n".join(
            f"  {'└' if i == len(preserved) - 1 else '├'} 🔒 <code>{f}</code>"
            for i, f in enumerate(preserved)
        )
        msg += (
            f"\n🔒 <b>Preserved (not overwritten):</b>\n"
            f"<blockquote>{p_lines}</blockquote>\n"
        )

    msg += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <b>Restarting bot in 3 seconds...</b>"
    )

    await status.edit_text(msg, parse_mode=enums.ParseMode.HTML)
    await asyncio.sleep(3)
    os.execv(sys.executable, [sys.executable] + sys.argv)
