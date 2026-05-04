import asyncio
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN
from database.db import Database


async def main():
    bot = Client(
        "thumbnail_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=dict(root="plugins"),
    )

    db = Database()
    bot.db = db

    print("ꜱᴛᴀʀᴛɪɴɢ ʙᴏᴛ...")
    async with bot:
        print("ʙᴏᴛ ɪꜱ ʀᴜɴɴɪɴɢ ✅")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
