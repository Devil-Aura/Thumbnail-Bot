# 🎨 Thumbnail Bot

A Telegram bot that allows users to set custom thumbnails for their Telegram files.

## Features

- Set custom thumbnail via `/set` (reply to an image)
- Delete thumbnail via `/del`
- View current thumbnail via `/show`
- Auto-applies thumbnail when you send a file

## Setup

1. Clone this repo
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variable:
   ```bash
   export BOT_TOKEN="your_bot_token_from_botfather"
   ```
4. Run the bot:
   ```bash
   python bot.py
   ```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Your Telegram bot token from [@BotFather](https://t.me/BotFather) |

## Built With

- [Pyrogram](https://pyrogram.org/) — Telegram MTProto API framework
- [Motor](https://motor.readthedocs.io/) — Async MongoDB driver
- [MongoDB](https://www.mongodb.com/) — Database
