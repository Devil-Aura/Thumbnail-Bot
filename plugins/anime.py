import io
import logging
import re
from typing import Optional

import aiohttp
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from config import TMDB_API_KEY, FANART_TV_KEY
from utils.image_generator import make_anime_thumbnail

logger = logging.getLogger(__name__)

TMDB_BASE  = "https://api.themoviedb.org/3"
TMDB_POST  = "https://image.tmdb.org/t/p/w780"    # portrait posters
TMDB_BACK  = "https://image.tmdb.org/t/p/w1280"   # landscape backdrops
FANART_BASE = "https://webservice.fanart.tv/v3"

# ── In-memory sessions ────────────────────────────────────────────────────────
sessions: dict[int, dict] = {}
STEP_PX    = 60
STEP_SCALE = 0.15


# ── Post message formatter ────────────────────────────────────────────────────
def build_post(s: dict) -> str:
    genres_str = ", ".join(s["genres"][:5]) if s["genres"] else "N/A"
    return (
        f"⛩ {s['title']} [S{s['season']:02d}]\n"
        f"╭───────────────────\n"
        f"├ ✨ Ratings - {s['rating']} IMDB\n"
        f"├ ❄️ Season - {s['season']:02d}\n"
        f"├ 🎬 Episodes - {s['episodes']}\n"
        f"├ 🔈 Audio - {s['audio']}\n"
        f"├ 📸 Quality - {s['quality']}\n"
        f"├ 🎭 Genres - {genres_str}\n"
        f"├───────────────────\n"
        f"├ ⭕️ Watch & Download ⭕️\n"
        f"╰──────────────────\n"
        f"New Anime In Official Hindi Dub 🔥"
    )


# ── Keyboard builder ──────────────────────────────────────────────────────────
def _kb(uid: int) -> InlineKeyboardMarkup:
    s   = sessions[uid]
    idx = s["img_idx"]
    tot = len(s["images"])
    pct = int(s["scale"] * 100)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ ᴩʀᴇᴠ", callback_data=f"an|prev|{uid}"),
            InlineKeyboardButton(f"🖼 {idx+1}/{tot}", callback_data="an|noop"),
            InlineKeyboardButton("ɴᴇxᴛ ▶️",  callback_data=f"an|next|{uid}"),
        ],
        [
            InlineKeyboardButton("　", callback_data="an|noop"),
            InlineKeyboardButton("⬆️",  callback_data=f"an|up|{uid}"),
            InlineKeyboardButton("　", callback_data="an|noop"),
        ],
        [
            InlineKeyboardButton("⬅️",   callback_data=f"an|left|{uid}"),
            InlineKeyboardButton("⬇️",   callback_data=f"an|down|{uid}"),
            InlineKeyboardButton("➡️",   callback_data=f"an|right|{uid}"),
        ],
        [
            InlineKeyboardButton("➖",              callback_data=f"an|zout|{uid}"),
            InlineKeyboardButton(f"🔍 {pct}%",      callback_data="an|noop"),
            InlineKeyboardButton("➕",              callback_data=f"an|zin|{uid}"),
        ],
        [
            InlineKeyboardButton("📋 ᴄᴏᴩʏ ᴩᴏꜱᴛ", callback_data=f"an|post|{uid}"),
            InlineKeyboardButton("✅ ꜱᴀᴠᴇ ᴛʜᴜᴍʙ", callback_data=f"an|done|{uid}"),
        ],
    ])


# ── TMDB / FANART helpers ─────────────────────────────────────────────────────
async def _tmdb(sess: aiohttp.ClientSession, path: str, **params) -> dict:
    params["api_key"] = TMDB_API_KEY
    async with sess.get(f"{TMDB_BASE}{path}", params=params, timeout=aiohttp.ClientTimeout(total=12)) as r:
        return await r.json()


async def _fetch_anime_data(name: str, season: int) -> dict:
    """
    Returns a dict with: title, year, rating, episodes, genres, description,
    images (list of URLs: posters first, then backdrops, then fanart).
    """
    async with aiohttp.ClientSession() as sess:
        # 1. Search TV
        search = await _tmdb(sess, "/search/tv", query=name, language="en-US")
        results = search.get("results", [])
        is_movie = False

        if not results:
            # Fallback to movie
            search = await _tmdb(sess, "/search/movie", query=name, language="en-US")
            results = search.get("results", [])
            is_movie = True

        if not results:
            return {}

        item    = results[0]
        tmdb_id = item["id"]
        media   = "movie" if is_movie else "tv"
        title   = item.get("name") or item.get("title", name)
        year    = (item.get("first_air_date") or item.get("release_date") or "")[:4]
        rating  = round(item.get("vote_average", 0), 1)

        # 2. Details (genres + description)
        details  = await _tmdb(sess, f"/{media}/{tmdb_id}", language="en-US")
        genres   = [g["name"] for g in details.get("genres", [])]
        overview = details.get("overview", "")

        # 3. Season episode count (TV only)
        episodes = 0
        if not is_movie:
            try:
                season_data = await _tmdb(sess, f"/tv/{tmdb_id}/season/{season}", language="en-US")
                eps_list = season_data.get("episodes", [])
                episodes = len(eps_list) if eps_list else season_data.get("episode_count", 0)
            except Exception:
                episodes = details.get("number_of_episodes", 0)
        else:
            episodes = 1
            season   = 1

        # 4. Images — posters first (portrait, best for right panel), then backdrops
        img_data   = await _tmdb(sess, f"/{media}/{tmdb_id}/images")
        posters    = img_data.get("posters", [])
        backdrops  = img_data.get("backdrops", [])

        poster_urls   = [f"{TMDB_POST}{p['file_path']}" for p in
                         sorted(posters,   key=lambda x: x.get("vote_average", 0), reverse=True)[:8]]
        backdrop_urls = [f"{TMDB_BACK}{b['file_path']}" for b in
                         sorted(backdrops, key=lambda x: x.get("vote_average", 0), reverse=True)[:6]]

        all_images = poster_urls + backdrop_urls

        # 5. FANART.TV (TV only)
        if not is_movie:
            try:
                ext = await _tmdb(sess, f"/tv/{tmdb_id}/external_ids")
                tvdb_id = ext.get("tvdb_id")
                if tvdb_id:
                    async with sess.get(
                        f"{FANART_BASE}/tv/{tvdb_id}",
                        params={"api_key": FANART_TV_KEY},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as fr:
                        fd = await fr.json()
                    for key in ("tvposter", "characterart", "showbackground", "tvthumb"):
                        for art in fd.get(key, [])[:3]:
                            url = art.get("url", "")
                            if url and url not in all_images:
                                all_images.append(url)
            except Exception as e:
                logger.warning("FANART.TV: %s", e)

        return {
            "title":       title,
            "year":        year,
            "rating":      rating,
            "episodes":    episodes,
            "genres":      genres,
            "description": overview,
            "images":      all_images,
            "season":      season,
        }


async def _download(url: str) -> Optional[bytes]:
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    return await r.read()
    except Exception as e:
        logger.warning("Download failed %s: %s", url, e)
    return None


async def _render(s: dict) -> Optional[bytes]:
    bg = await _download(s["images"][s["img_idx"]])
    if not bg:
        return None
    return make_anime_thumbnail(
        art_bytes=bg,
        title=s["title"],
        year=s["year"],
        episodes=s["episodes"],
        audio=s["audio"],
        description=s["description"],
        genres=s["genres"],
        season=s["season"],
        channel_name=s["channel"],
        offset_x=s["offset_x"],
        offset_y=s["offset_y"],
        scale=s["scale"],
    )


async def _send_new(client: Client, uid: int, message: Message):
    thumb = await _render(sessions[uid])
    if not thumb:
        await message.reply_text("❌ ɪᴍᴀɢᴇ ʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ, ᴛʀʏ /anime ᴀɢᴀɪɴ.")
        return
    s = sessions[uid]
    sent = await message.reply_photo(
        photo=io.BytesIO(thumb),
        caption=(
            f"🎨 **{s['title']}** — S{s['season']:02d}\n"
            f"`{', '.join(s['genres'][:3])}`\n\n"
            "⬆️⬇️⬅️➡️ ᴩᴀɴ  •  ➕➖ ᴢᴏᴏᴍ  •  ◀️▶️ ᴄʜᴀɴɢᴇ ɪᴍᴀɢᴇ"
        ),
        reply_markup=_kb(uid),
    )
    s["msg_id"]  = sent.id
    s["chat_id"] = sent.chat.id


async def _edit(client: Client, uid: int, cq_msg):
    thumb = await _render(sessions[uid])
    if not thumb:
        await cq_msg.edit_caption("❌ ɪᴍᴀɢᴇ ꜰᴀɪʟᴇᴅ. ᴛʀʏ ɴᴇxᴛ ▶️")
        return
    s = sessions[uid]
    await cq_msg.edit_media(
        InputMediaPhoto(
            media=io.BytesIO(thumb),
            caption=(
                f"🎨 **{s['title']}** — S{s['season']:02d}\n"
                f"`{', '.join(s['genres'][:3])}`\n\n"
                "⬆️⬇️⬅️➡️ ᴩᴀɴ  •  ➕➖ ᴢᴏᴏᴍ  •  ◀️▶️ ᴄʜᴀɴɢᴇ ɪᴍᴀɢᴇ"
            ),
        ),
        reply_markup=_kb(uid),
    )


# ── /anime command ────────────────────────────────────────────────────────────
@Client.on_message(filters.command("anime") & filters.private)
async def anime_cmd(client: Client, message: Message):
    raw = " ".join(message.command[1:]).strip()
    if not raw:
        await message.reply_text(
            "⚠️ **ᴜꜱᴀɢᴇ:**\n"
            "`/anime <name>` — ꜱᴇᴀꜱᴏɴ 1 ʙʏ ᴅᴇꜰᴀᴜʟᴛ\n"
            "`/anime <name> S02` — ꜱᴘᴇᴄɪꜰʏ ꜱᴇᴀꜱᴏɴ\n\n"
            "**ᴇxᴀᴍᴩʟᴇ:** `/anime Shield Hero S02`"
        )
        return

    # Parse optional season: "Shield Hero S02" → ("Shield Hero", 2)
    season = 1
    m = re.search(r"\bS(\d{1,2})\b$", raw, re.IGNORECASE)
    if m:
        season = int(m.group(1))
        query  = raw[:m.start()].strip()
    else:
        query = raw

    wait = await message.reply_text(f"🔍 ꜱᴇᴀʀᴄʜɪɴɢ **{query}** ꜱᴇᴀꜱᴏɴ {season}...")
    data = await _fetch_anime_data(query, season)

    if not data or not data.get("images"):
        await wait.edit_text(f"❌ ɴᴏ ʀᴇꜱᴜʟᴛꜱ ꜰᴏʀ **{query}**. ᴄʜᴇᴄᴋ ꜱᴩᴇʟʟɪɴɢ ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ.")
        return

    uid = message.from_user.id
    sessions[uid] = {
        "title":       data["title"],
        "year":        data["year"],
        "rating":      data["rating"],
        "episodes":    data["episodes"],
        "genres":      data["genres"],
        "description": data["description"],
        "images":      data["images"],
        "season":      data["season"],
        "audio":       "Hindi #Official",
        "quality":     "Multi",
        "channel":     "AnimeChannel",
        "img_idx":     0,
        "offset_x":   0,
        "offset_y":   0,
        "scale":       1.0,
        "msg_id":      None,
        "chat_id":     message.chat.id,
    }

    await wait.delete()
    await _send_new(client, uid, message)


# ── Callback handler ──────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^an\|"))
async def anime_cb(client: Client, cq: CallbackQuery):
    parts  = cq.data.split("|")
    action = parts[1]

    if action == "noop":
        await cq.answer()
        return

    uid = int(parts[2])

    if uid not in sessions:
        await cq.answer("ꜱᴇꜱꜱɪᴏɴ ᴇxᴩɪʀᴇᴅ. ᴜꜱᴇ /anime ᴀɢᴀɪɴ.", show_alert=True)
        return
    if cq.from_user.id != uid:
        await cq.answer("ᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ꜱᴇꜱꜱɪᴏɴ!", show_alert=True)
        return

    s      = sessions[uid]
    redraw = True

    if action == "prev":
        s["img_idx"] = (s["img_idx"] - 1) % len(s["images"])
        s["offset_x"] = s["offset_y"] = 0
        await cq.answer("◀️")

    elif action == "next":
        s["img_idx"] = (s["img_idx"] + 1) % len(s["images"])
        s["offset_x"] = s["offset_y"] = 0
        await cq.answer("▶️")

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

    elif action == "post":
        post_text = build_post(s)
        await cq.message.reply_text(
            f"📋 **ᴄᴏᴩʏ ᴛʜɪꜱ ᴩᴏꜱᴛ:**\n\n{post_text}",
        )
        await cq.answer("📋 ᴩᴏꜱᴛ ꜱᴇɴᴛ!", show_alert=False)
        redraw = False

    elif action == "done":
        thumb_url = s["images"][s["img_idx"]]
        await client.db.set_thumbnail(uid, thumb_url)
        post_text = build_post(s)
        await cq.message.edit_caption(
            caption=(
                f"✅ **ᴛʜᴜᴍʙɴᴀɪʟ ꜱᴀᴠᴇᴅ!**\n\n"
                f"**{s['title']}** S{s['season']:02d} — {s['year']}\n\n"
                f"📋 **ʏᴏᴜʀ ᴩᴏꜱᴛ:**\n{post_text}"
            ),
        )
        sessions.pop(uid, None)
        redraw = False
        await cq.answer("✅ ꜱᴀᴠᴇᴅ!", show_alert=True)

    if redraw:
        await _edit(client, uid, cq.message)
