"""
/pvt — Make the bot private (only owner can use)
/pub — Make the bot public (everyone can use)
/addadmin <user_id> — Add an admin (owner only)
/deladmin <user_id> — Remove an admin (owner only)

When bot is private, all commands from non-owner / non-admin users are
blocked silently (no response). The owner is always allowed.
"""
from pyrogram import Client, enums, filters
from pyrogram.types import Message
from config import OWNER_ID


def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


async def _is_admin(client, user_id: int) -> bool:
    if _is_owner(user_id):
        return True
    try:
        return await client.db.is_admin(user_id)
    except Exception:
        return False


# ── Private mode gate — runs BEFORE all other handlers (group=-1) ─────────────
@Client.on_message(filters.private, group=-1)
async def pvt_gate(client: Client, message: Message):
    uid = message.from_user.id if message.from_user else None
    if uid is None:
        return

    # Owner always passes through
    if _is_owner(uid):
        return

    try:
        is_pvt = await client.db.get_pvt_mode()
    except Exception:
        return  # DB error — don't block

    if not is_pvt:
        return  # Bot is public

    # Check admin
    try:
        is_adm = await client.db.is_admin(uid)
    except Exception:
        is_adm = False

    if not is_adm:
        # Block the message — stop propagation so no other handler fires
        await message.stop_propagation()


# ── /pvt command ──────────────────────────────────────────────────────────────
@Client.on_message(filters.command("pvt") & filters.private)
async def pvt_cmd(client: Client, message: Message):
    uid = message.from_user.id
    if not _is_owner(uid):
        await message.reply_text("❌ <b>Owner only command.</b>",
                                 parse_mode=enums.ParseMode.HTML)
        return

    await client.db.set_pvt_mode(True)
    await message.reply_text(
        "🔒 <b>Bot is now PRIVATE</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Only you and admins can use the bot.\n\n"
        "Use /pub to make it public again.",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /pub command ──────────────────────────────────────────────────────────────
@Client.on_message(filters.command("pub") & filters.private)
async def pub_cmd(client: Client, message: Message):
    uid = message.from_user.id
    if not _is_owner(uid):
        await message.reply_text("❌ <b>Owner only command.</b>",
                                 parse_mode=enums.ParseMode.HTML)
        return

    await client.db.set_pvt_mode(False)
    await message.reply_text(
        "🌐 <b>Bot is now PUBLIC</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Everyone can use the bot now.\n\n"
        "Use /pvt to make it private again.",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /addadmin command ─────────────────────────────────────────────────────────
@Client.on_message(filters.command("addadmin") & filters.private)
async def addadmin_cmd(client: Client, message: Message):
    uid = message.from_user.id
    if not _is_owner(uid):
        await message.reply_text("❌ <b>Owner only command.</b>",
                                 parse_mode=enums.ParseMode.HTML)
        return

    args = message.command[1:]
    if not args or not args[0].isdigit():
        await message.reply_text(
            "⚠️ <b>Usage:</b> <code>/addadmin &lt;user_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    target_id = int(args[0])
    await client.db.add_admin(target_id)
    await message.reply_text(
        f"✅ <b>Admin added:</b> <code>{target_id}</code>",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /deladmin command ─────────────────────────────────────────────────────────
@Client.on_message(filters.command("deladmin") & filters.private)
async def deladmin_cmd(client: Client, message: Message):
    uid = message.from_user.id
    if not _is_owner(uid):
        await message.reply_text("❌ <b>Owner only command.</b>",
                                 parse_mode=enums.ParseMode.HTML)
        return

    args = message.command[1:]
    if not args or not args[0].isdigit():
        await message.reply_text(
            "⚠️ <b>Usage:</b> <code>/deladmin &lt;user_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    target_id = int(args[0])
    await client.db.remove_admin(target_id)
    await message.reply_text(
        f"✅ <b>Admin removed:</b> <code>{target_id}</code>",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /admins command — list all admins ─────────────────────────────────────────
@Client.on_message(filters.command("admins") & filters.private)
async def admins_cmd(client: Client, message: Message):
    uid = message.from_user.id
    if not _is_owner(uid):
        await message.reply_text("❌ <b>Owner only command.</b>",
                                 parse_mode=enums.ParseMode.HTML)
        return

    admins = await client.db.get_admins()
    is_pvt = await client.db.get_pvt_mode()
    status = "🔒 Private" if is_pvt else "🌐 Public"

    if admins:
        admin_list = "\n".join(f"├ <code>{a}</code>" for a in admins[:-1])
        admin_list += f"\n└ <code>{admins[-1]}</code>" if len(admins) > 1 else f"└ <code>{admins[0]}</code>" if admins else ""
    else:
        admin_list = "└ No admins added"

    await message.reply_text(
        f"<b>Bot Mode:</b> {status}\n"
        f"<b>Owner:</b> <code>{OWNER_ID}</code>\n\n"
        f"<b>Admins:</b>\n{admin_list}\n\n"
        f"<i>Use /addadmin &lt;id&gt; or /deladmin &lt;id&gt;</i>",
        parse_mode=enums.ParseMode.HTML,
    )
