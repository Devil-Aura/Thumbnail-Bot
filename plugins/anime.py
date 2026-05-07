import io
import logging
from typing import Optional

import aiohttp
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import TMDB_API_KEY, FANART_TV_KEY
from utils.image_generator import make_thumbnail

logger = logging.getLogger(__name__)

TMDB_BASE   = "https://api.themoviedb.org/3"
TMDB_IMG    = "https://image.tmdb.org/t/p/w1280"
FANART_BASE = "https://webservice.fanart.tv/v3"

# ── In-memory sessions ────────────────────────────────────────────────────────
# { user_id: { title, subtitle, images:[url,...], img_idx, offset_x, offset_y,
#              scale, chat_id, msg_id } }
sessions: dict[int, dict] = {}

STEP_PX    = 60     # pixels per arrow press
STEP_SCALE = 0.15   # zoom step


# ── Keyboard builder ──────────────────────────────────────────────────────────
def _kb(uid: int) -> InlineKeyboardMarkup:
    s   = sessions[uid]
    idx = s["img_idx"]
    tot = len(s["images"])
    pct = int(s["scale"] * 100)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ ᴩʀᴇᴠ", callback_data=f"an|prev|{uid}"),
            InlineKeyboardButton(f"🖼 {idx+1}/{tot}",  callback_data="an|noop"),
            InlineKeyboardButton("ɴᴇxᴛ ▶️", callback_data=f"an|next|{uid}"),
        ],
        [
            InlineKeyboardButton("", callback_data="an|noop"),
            InlineKeyboardButton("⬆️",       callback_data=f"an|up|{uid}"),
            InlineKeyboardButton("", callback_data="an|noop"),
        ],
        [
            InlineKeyboardButton("⬅️",        callback_data=f"an|left|{uid}"),
            InlineKeyboardButton("⬇️",        callback_data=f"an|down|{uid}"),
            InlineKeyboardButton("➡️",        callback_data=f"an|right|{uid}"),
        ],
        [
            InlineKeyboardButton(f"➖",       callback_data=f"an|zout|{uid}"),
            InlineKeyboardButton(f"🔍 {pct}%",callback_data="an|noop"),
            InlineKeyboardButton(f"➕",       callback_data=f"an|zin|{uid}"),
        ],
        [
            InlineKeyboardButton("✅ ᴅᴏɴᴇ — ꜱᴀᴠᴇ ᴛʜᴜᴍʙɴᴀɪʟ", callback_data=f"an|done|{uid}"),
        ],
    ])


# ── TMDB helpers ──────────────────────────────────────────────────────────────
async def _tmdb(session: aiohttp.ClientSession, path: str, **params) -> dict:
    params["api_key"] = TMDB_API_KEY
    async with session.get(f"{TMDB_BASE}{path}", params=params) as r:
        return await r.json()


async def _fetch_images(name: str) -> tuple[str, str, list[str]]:
    """
    Returns (title, subtitle, list_of_image_urls).
    Combines TMDB backdrops + FANART.TV artwork.
    """
    async with aiohttp.ClientSession() as sess:
        # 1. Search TV
        search = await _tmdb(sess, "/search/tv", query=name, language="en-US")
        results = search.get("results", [])
        if not results:
            # Fallback: search movies
            search = await _tmdb(sess, "/search/movie", query=name, language="en-US")
            results = search.get("results", [])
            if not results:
                return name, "", []
            item   = results[0]
            tmdb_id = item["id"]
            title  = item.get("title", name)
            year   = (item.get("release_date") or "")[:4]
            media  = "movie"
        else:
            item    = results[0]
            tmdb_id = item["id"]
            title   = item.get("name", name)
            year    = (item.get("first_air_date") or "")[:4]
            media   = "tv"

        # 2. Genre names
        details = await _tmdb(sess, f"/{media}/{tmdb_id}", language="en-US")
        genres  = ", ".join(g["name"] for g in details.get("genres", [])[:3])
        subtitle = f"{year}  •  {genres}" if genres else year

        # 3. TMDB backdrops
        img_data = await _tmdb(sess, f"/{media}/{tmdb_id}/images")
        backdrops = img_data.get("backdrops", [])
        urls: list[str] = [
            f"{TMDB_IMG}{b['file_path']}"
            for b in sorted(backdrops, key=lambda x: x.get("vote_average", 0), reverse=True)[:10]
        ]

        # 4. FANART.TV (TV series only; needs TVDB id)
        if media == "tv":
            try:
                ext = await _tmdb(sess, f"/tv/{tmdb_id}/external_ids")
                tvdb_id = ext.get("tvdb_id")
                if tvdb_id:
                    async with sess.get(
                        f"{FANART_BASE}/tv/{tvdb_id}",
                        params={"api_key": FANART_TV_KEY},
                    ) as fr:
                        fd = await fr.json()
                    for key in ("showbackground", "tvthumb", "tvbanner"):
                        for art in fd.get(key, [])[:4]:
                            url = art.get("url", "")
                            if url and url not in urls:
                                urls.append(url)
            except Exception as e:
                logger.warning("FANART.TV error: %s", e)

        return title, subtitle, urls


async def _download(url: str) -> Optional[bytes]:
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    return await r.read()
    except Exception as e:
        logger.warning("Image download failed %s: %s", url, e)
    return None


async def _render_and_send(client: Client, uid: int, message: Message = None, edit_msg=None):
    s = sessions[uid]
    url = s["images"][s["img_idx"]]
    bg  = await _download(url)
    if not bg:
        text = "❌ ɪᴍᴀɢᴇ ʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ, ᴛʀʏ ɴᴇxᴛ ▶️"
        if edit_msg:
            await edit_msg.edit_caption(caption=text)
        return

    thumb_bytes = make_thumbnail(
        bg_bytes=bg,
        title=s["title"],
        subtitle=s["subtitle"],
        offset_x=s["offset_x"],
        offset_y=s["offset_y"],
        scale=s["scale"],
    )

    if edit_msg:
        await edit_msg.edit_media(
            media=__import__("pyrogram.types", fromlist=["InputMediaPhoto"]).InputMediaPhoto(
                media=io.BytesIO(thumb_bytes),
                caption=(
                    f"🎨 **{s['title']}**\n"
                    f"`{s['subtitle']}`\n\n"
                    "ᴜꜱᴇ ᴀʀʀᴏᴡꜱ ᴛᴏ ᴘᴀɴ · ➕➖ ᴛᴏ ᴢᴏᴏᴍ · ◀️▶️ ᴛᴏ ꜱᴡɪᴛᴄʜ ɪᴍᴀɢᴇ"
                ),
            ),
            reply_markup=_kb(uid),
        )
    elif message:
        sent = await message.reply_photo(
            photo=io.BytesIO(thumb_bytes),
            caption=(
                f"🎨 **{s['title']}**\n"
                f"`{s['subtitle']}`\n\n"
                "ᴜꜱᴇ ᴀʀʀᴏᴡꜱ ᴛᴏ ᴘᴀɴ · ➕➖ ᴛᴏ ᴢᴏᴏᴍ · ◀️▶️ ᴛᴏ ꜱᴡɪᴛᴄʜ ɪᴍᴀɢᴇ"
            ),
            reply_markup=_kb(uid),
        )
        s["msg_id"]  = sent.id
        s["chat_id"] = sent.chat.id


# ── /anime command ────────────────────────────────────────────────────────────
@Client.on_message(filters.command("anime") & filters.private)
async def anime_cmd(client: Client, message: Message):
    query = " ".join(message.command[1:]).strip()
    if not query:
        await message.reply_text(
            "⚠️ **ᴜꜱᴀɢᴇ:**\n`/anime <anime name>`\n\n"
            "**ᴇxᴀᴍᴩʟᴇ:** `/anime One Piece`"
        )
        return

    wait = await message.reply_text(f"🔍 ꜱᴇᴀʀᴄʜɪɴɢ **{query}**...")

    title, subtitle, images = await _fetch_images(query)

    if not images:
        await wait.edit_text("❌ ɴᴏ ɪᴍᴀɢᴇꜱ ꜰᴏᴜɴᴅ ꜰᴏʀ **" + query + "**. ᴛʀʏ ᴀɴᴏᴛʜᴇʀ ɴᴀᴍᴇ.")
        return

    uid = message.from_user.id
    sessions[uid] = {
        "title":    title,
        "subtitle": subtitle,
        "images":   images,
        "img_idx":  0,
        "offset_x": 0,
        "offset_y": 0,
        "scale":    1.0,
        "msg_id":   None,
        "chat_id":  message.chat.id,
    }

    await wait.delete()
    await _render_and_send(client, uid, message=message)


# ── Callback handler ──────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^an\|"))
async def anime_cb(client: Client, cq: CallbackQuery):
    parts = cq.data.split("|")
    action = parts[1]

    if action == "noop":
        await cq.answer()
        return

    uid = int(parts[2])

    if uid not in sessions:
        await cq.answer("ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ. ʀᴜɴ /anime ᴀɢᴀɪɴ.", show_alert=True)
        return

    if cq.from_user.id != uid:
        await cq.answer("ᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ꜱᴇꜱꜱɪᴏɴ! ᴜꜱᴇ /anime ʏᴏᴜʀꜱᴇʟꜰ.", show_alert=True)
        return

    s = sessions[uid]
    redraw = True

    if action == "prev":
        s["img_idx"] = (s["img_idx"] - 1) % len(s["images"])
        s["offset_x"] = s["offset_y"] = 0
        await cq.answer("◀️ ᴩʀᴇᴠ ɪᴍᴀɢᴇ")

    elif action == "next":
        s["img_idx"] = (s["img_idx"] + 1) % len(s["images"])
        s["offset_x"] = s["offset_y"] = 0
        await cq.answer("▶️ ɴᴇxᴛ ɪᴍᴀɢᴇ")

    elif action == "up":
        s["offset_y"] = max(0, s["offset_y"] - STEP_PX)
        await cq.answer("⬆️")

    elif action == "down":
        s["offset_y"] += STEP_PX
        await cq.answer("⬇️")

    elif action == "left":
        s["offset_x"] = max(0, s["offset_x"] - STEP_PX)
        await cq.answer("⬅️")

    elif action == "right":
        s["offset_x"] += STEP_PX
        await cq.answer("➡️")

    elif action == "zin":
        s["scale"] = min(3.0, round(s["scale"] + STEP_SCALE, 2))
        await cq.answer(f"➕ {int(s['scale']*100)}%")

    elif action == "zout":
        s["scale"] = max(1.0, round(s["scale"] - STEP_SCALE, 2))
        await cq.answer(f"➖ {int(s['scale']*100)}%")

    elif action == "done":
        await client.db.set_thumbnail(uid, s["images"][s["img_idx"]])
        await cq.message.edit_caption(
            caption=(
                f"✅ **ᴛʜᴜᴍʙɴᴀɪʟ ꜱᴀᴠᴇᴅ!**\n\n"
                f"**{s['title']}** — {s['subtitle']}\n\n"
                "ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ ɪꜱ ɴᴏᴡ ꜱᴇᴛ. ꜱᴇɴᴅ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴀᴩᴩʟʏ ɪᴛ!"
            ),
        )
        sessions.pop(uid, None)
        redraw = False
        await cq.answer("✅ ᴛʜᴜᴍʙɴᴀɪʟ ꜱᴀᴠᴇᴅ!", show_alert=True)

    if redraw:
        await _render_and_send(client, uid, edit_msg=cq.message)
