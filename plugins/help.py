from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


@Client.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    text = """📋 **ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅꜱ**

/start — ꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ
/set — ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ (ʀᴇᴩʟʏ ᴛᴏ ᴀɴ ɪᴍᴀɢᴇ)
/del — ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ꜱᴀᴠᴇᴅ ᴛʜᴜᴍʙɴᴀɪʟ
/show — ᴠɪᴇᴡ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴛʜᴜᴍʙɴᴀɪʟ
/help — ꜱʜᴏᴡ ᴛʜɪꜱ ᴍᴇꜱꜱᴀɢᴇ

💡 **ʜᴏᴡ ᴛᴏ ᴜꜱᴇ:**
1️⃣ ꜱᴇɴᴅ /set ᴀɴᴅ ʀᴇᴩʟʏ ᴡɪᴛʜ ᴀɴ ɪᴍᴀɢᴇ
2️⃣ ꜱᴇɴᴅ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ
3️⃣ ᴛʜᴇ ʙᴏᴛ ᴡɪʟʟ ᴀᴩᴩʟʏ ᴛʜᴇ ᴛʜᴜᴍʙɴᴀɪʟ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ!"""

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 ʙᴀᴄᴋ ᴛᴏ ꜱᴛᴀʀᴛ", callback_data="start")]]
    )
    await message.reply_text(text, reply_markup=buttons)
