import asyncio
import logging
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN
from database.db import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%d %b %Y %H:%M:%S",
)
logger = logging.getLogger(__name__)


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

    # Attach Telegram log handler BEFORE starting, so it's ready when bot starts
    from plugins.tg_logger import setup_tg_logger
    setup_tg_logger(bot)

    logger.info("Starting bot...")
    async with bot:
        me = await bot.get_me()
        logger.info("Bot running as @%s (id=%s)", me.username, me.id)
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
