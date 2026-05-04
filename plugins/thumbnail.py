from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


@Client.on_message(filters.command("set") & filters.private)
async def set_thumbnail(client: Client, message: Message):
    if message.reply_to_message and message.reply_to_message.photo:
        file_id = message.reply_to_message.photo.file_id
        await client.db.set_thumbnail(message.from_user.id, file_id)
        await message.reply_text(
            "✅ **ᴛʜᴜᴍʙɴᴀɪʟ ꜱᴇᴛ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ!**\n\n"
            "ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ ʜᴀꜱ ʙᴇᴇɴ ꜱᴀᴠᴇᴅ.\n"
            "ꜱᴇɴᴅ ᴍᴇ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴀᴩᴩʟʏ ɪᴛ! 🎨"
        )
    else:
        await message.reply_text(
            "⚠️ **ʜᴏᴡ ᴛᴏ ꜱᴇᴛ ᴛʜᴜᴍʙɴᴀɪʟ:**\n\n"
            "ʀᴇᴩʟʏ ᴛᴏ ᴀɴ ɪᴍᴀɢᴇ ᴡɪᴛʜ /set ᴄᴏᴍᴍᴀɴᴅ!"
        )


@Client.on_message(filters.command("del") & filters.private)
async def del_thumbnail(client: Client, message: Message):
    thumb = await client.db.get_thumbnail(message.from_user.id)
    if thumb:
        await client.db.del_thumbnail(message.from_user.id)
        await message.reply_text(
            "🗑️ **ᴛʜᴜᴍʙɴᴀɪʟ ᴅᴇʟᴇᴛᴇᴅ!**\n\n"
            "ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ ʜᴀꜱ ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ."
        )
    else:
        await message.reply_text(
            "❌ **ɴᴏ ᴛʜᴜᴍʙɴᴀɪʟ ꜰᴏᴜɴᴅ!**\n\n"
            "ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ꜱᴇᴛ ᴀɴʏ ᴛʜᴜᴍʙɴᴀɪʟ ʏᴇᴛ.\n"
            "ᴜꜱᴇ /set ᴛᴏ ꜱᴇᴛ ᴏɴᴇ!"
        )


@Client.on_message(filters.command("show") & filters.private)
async def show_thumbnail(client: Client, message: Message):
    thumb = await client.db.get_thumbnail(message.from_user.id)
    if thumb:
        await message.reply_photo(
            photo=thumb,
            caption=(
                "🖼️ **ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴛʜᴜᴍʙɴᴀɪʟ:**\n\n"
                "ᴜꜱᴇ /del ᴛᴏ ʀᴇᴍᴏᴠᴇ ɪᴛ."
            ),
        )
    else:
        await message.reply_text(
            "❌ **ɴᴏ ᴛʜᴜᴍʙɴᴀɪʟ ꜰᴏᴜɴᴅ!**\n\n"
            "ᴜꜱᴇ /set ᴛᴏ ꜱᴇᴛ ᴏɴᴇ!"
        )


@Client.on_message(
    (filters.document | filters.video | filters.audio) & filters.private
)
async def handle_file(client: Client, message: Message):
    thumb = await client.db.get_thumbnail(message.from_user.id)
    if not thumb:
        return
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ ᴀᴩᴩʟʏ ᴛʜᴜᴍʙɴᴀɪʟ",
                    callback_data=f"apply_{message.id}",
                ),
                InlineKeyboardButton("❌ ꜱᴋɪᴩ", callback_data="skip"),
            ]
        ]
    )
    await message.reply_text(
        "🎨 **ʏᴏᴜ ʜᴀᴠᴇ ᴀ ꜱᴀᴠᴇᴅ ᴛʜᴜᴍʙɴᴀɪʟ!**\n\n"
        "ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴀᴩᴩʟʏ ɪᴛ ᴛᴏ ᴛʜɪꜱ ꜰɪʟᴇ?",
        reply_markup=buttons,
    )


@Client.on_callback_query(filters.regex("^skip$"))
async def skip_callback(client, cq):
    await cq.message.delete()
    await cq.answer("ꜱᴋɪᴩᴩᴇᴅ!", show_alert=False)
