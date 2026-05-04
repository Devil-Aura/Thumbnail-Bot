from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import START_PIC


START_TEXT = """ʜᴇʏ {mention}! 👋

ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ **ᴛʜᴜᴍʙɴᴀɪʟ ʙᴏᴛ** 🎨

ɪ ᴄᴀɴ ʜᴇʟᴘ ʏᴏᴜ ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟꜱ ꜰᴏʀ ʏᴏᴜʀ \
ᴛᴇʟᴇɢʀᴀᴍ ꜰɪʟᴇꜱ ᴀɴᴅ ᴍᴇᴅɪᴀ!

📌 **ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅꜱ:**
• /set — ꜱᴇᴛ ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ
• /del — ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ᴛʜᴜᴍʙɴᴀɪʟ
• /show — ꜱʜᴏᴡ ᴄᴜʀʀᴇɴᴛ ᴛʜᴜᴍʙɴᴀɪʟ
• /help — ɢᴇᴛ ʜᴇʟᴘ

**ꜱᴛᴀᴛᴜꜱ:** ᴏɴʟɪɴᴇ ✅"""

HELP_TEXT = """📋 **ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅꜱ**

/start — ꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ
/set — ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ ᴠɪᴀ ʀᴇᴩʟʏ ᴛᴏ ᴀɴ ɪᴍᴀɢᴇ
/del — ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ꜱᴀᴠᴇᴅ ᴛʜᴜᴍʙɴᴀɪʟ
/show — ᴠɪᴇᴡ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴛʜᴜᴍʙɴᴀɪʟ
/help — ꜱʜᴏᴡ ᴛʜɪꜱ ᴍᴇꜱꜱᴀɢᴇ

💡 **ʜᴏᴡ ᴛᴏ ᴜꜱᴇ:**
1️⃣ ꜱᴇɴᴅ /set ᴀɴᴅ ʀᴇᴩʟʏ ᴡɪᴛʜ ᴀɴ ɪᴍᴀɢᴇ
2️⃣ ꜱᴇɴᴅ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ
3️⃣ ᴛʜᴇ ʙᴏᴛ ᴡɪʟʟ ᴀᴩᴩʟʏ ᴛʜᴇ ᴛʜᴜᴍʙɴᴀɪʟ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ!"""


def start_buttons():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("ꜱᴜᴩᴩᴏʀᴛ 💬", url="https://t.me/"),
                InlineKeyboardButton("ᴜᴩᴅᴀᴛᴇꜱ 📢", url="https://t.me/"),
            ],
            [InlineKeyboardButton("ʜᴇʟᴩ & ᴄᴏᴍᴍᴀɴᴅꜱ 📋", callback_data="help")],
        ]
    )


def back_button():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="start")]]
    )


@Client.on_message(filters.command("start") & filters.private)
async def start(client: Client, message: Message):
    await client.db.add_user(message.from_user.id)
    mention = message.from_user.mention
    await message.reply_photo(
        photo=START_PIC,
        caption=START_TEXT.format(mention=mention),
        reply_markup=start_buttons(),
    )


@Client.on_callback_query(filters.regex("^help$"))
async def help_callback(client, cq):
    await cq.message.edit_caption(
        caption=HELP_TEXT,
        reply_markup=back_button(),
    )


@Client.on_callback_query(filters.regex("^start$"))
async def start_callback(client, cq):
    mention = cq.from_user.mention
    await cq.message.edit_caption(
        caption=START_TEXT.format(mention=mention),
        reply_markup=start_buttons(),
    )
