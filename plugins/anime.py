"""
/anime <name> [S01]

Flow:
  1. Preview thumbnail  →  pan/zoom/image-swap controls
  2. ✅ Done            →  spoiler 4K BG + AniList expandable info
                        →  thumbnail + Powered-By + [📢 Main Post] button
  3. [📢 Main Post]     →  ask for Watch & Download link
  4. User sends link    →  final post thumbnail with button
"""
import io
import logging
import random
import re
from typing import Optional

import aiohttp
from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from config import TMDB_API_KEY, FANART_TV_KEY
from utils.anilist import fetch_anilist
from utils.image_generator import make_anime_thumbnail, make_spoiler_bg

logger = logging.getLogger(__name__)

TMDB_BASE   = "https://api.themoviedb.org/3"
TMDB_POST   = "https://image.tmdb.org/t/p/w780"
TMDB_BACK   = "https://image.tmdb.org/t/p/w1280"
FANART_BASE = "https://webservice.fanart.tv/v3"
CHANNEL     = "CrunchyRollChannel"

# ── State ─────────────────────────────────────────────────────────────────────
sessions:      dict[int, dict] = {}   # uid → thumbnail preview session
post_sessions: dict[int, dict] = {}   # uid → post data (after Done)
pending_link:  set[int]        = set()  # uids awaiting Watch link

STEP_PX    = 60
STEP_SCALE = 0.15


# ── Caption builders ──────────────────────────────────────────────────────────
def _powered_caption(ps: dict) -> str:
    genres = ", ".join(ps["genres"][:5]) or "N/A"
    return (
        f"⛩ <b>{ps['title']} [S{ps['season']:02d}]</b>\n"
        "<blockquote>"
        "╭───────────────────\n"
        f"├ ✨ Ratings - {ps['rating']} IMDB\n"
        f"├ ❄️ Season - {ps['season']:02d}\n"
        f"├ 🎬 Episodes - {ps['episodes']}\n"
        f"├ 🔈 Audio - {ps['audio']}\n"
        f"├ 📸 Quality - {ps['quality']}\n"
        f"├ 🎭 Genres - {genres}\n"
        "╰───────────────────"
        "</blockquote>\n"
        f"• <b>𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗕𝘆:</b> @{CHANNEL}."
    )


def _final_caption(ps: dict) -> str:
    genres = ", ".join(ps["genres"][:5]) or "N/A"
    return (
        f"⛩ <b>{ps['title']} [S{ps['season']:02d}]</b>\n"
        "<blockquote>"
        "╭───────────────────\n"
        f"├ ✨ Ratings - {ps['rating']} IMDB\n"
        f"├ ❄️ Season - {ps['season']:02d}\n"
        f"├ 🎬 Episodes - {ps['episodes']}\n"
        f"├ 🔈 Audio - {ps['audio']}\n"
        f"├ 📸 Quality - {ps['quality']}\n"
        f"├ 🎭 Genres - {genres}\n"
        "├───────────────────\n"
        "├ ⭕️ Watch &amp; Download ⭕️\n"
        "╰──────────────────"
        "</blockquote>\n"
        "<b>New Anime In Official Hindi Dub 🔥</b>"
    )


def _anilist_caption(al: dict, anime_title: str) -> str:
    genres  = ", ".join(al["genres"][:6]) if al["genres"] else "N/A"
    syn     = al["synopsis"]
    if len(syn) > 850:
        syn = syn[:850] + "…"
    end = al["end"] or ""
    inner = (
        f"<b>{al['display']}</b>\n\n"
        f"‣ Genres : {genres}\n"
        f"‣ Type : {al['format']}\n"
        f"‣ Average Rating : {al['score']}\n"
        f"‣ Status : {al['status']}\n"
        f"‣ First aired : {al['start']}\n"
        f"‣ Last aired : {end}\n"
        f"‣ Runtime : {al['duration']} minutes\n"
        f"‣ No of episodes : {al['episodes']}\n\n"
        f'‣ Synopsis : "{syn}"'
    )
    return (
        f"<b>{anime_title} In Hindi Dub Available On @{CHANNEL}...!!</b>\n"
        f"<blockquote expandable>{inner}</blockquote>"
    )


# ── Keyboards ─────────────────────────────────────────────────────────────────
def _preview_kb(uid: int) -> InlineKeyboardMarkup:
    s   = sessions[uid]
    idx = s["img_idx"]
    tot = len(s["images"])
    pct = int(s["scale"] * 100)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ ᴩʀᴇᴠ",     callback_data=f"an|prev|{uid}"),
            InlineKeyboardButton(f"🖼 {idx+1}/{tot}", callback_data="an|noop"),
            InlineKeyboardButton("ɴᴇxᴛ ▶️",      callback_data=f"an|next|{uid}"),
        ],
        [
            InlineKeyboardButton("　",  callback_data="an|noop"),
            InlineKeyboardButton("⬆️",  callback_data=f"an|up|{uid}"),
            InlineKeyboardButton("　",  callback_data="an|noop"),
        ],
        [
            InlineKeyboardButton("⬅️",  callback_data=f"an|left|{uid}"),
            InlineKeyboardButton("⬇️",  callback_data=f"an|down|{uid}"),
            InlineKeyboardButton("➡️",  callback_data=f"an|right|{uid}"),
        ],
        [
            InlineKeyboardButton("➖",           callback_data=f"an|zout|{uid}"),
            InlineKeyboardButton(f"🔍 {pct}%",   callback_data="an|noop"),
            InlineKeyboardButton("➕",           callback_data=f"an|zin|{uid}"),
        ],
        [
            InlineKeyboardButton("✅ ᴅᴏɴᴇ", callback_data=f"an|done|{uid}"),
        ],
    ])


def _powered_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 ᴍᴀɪɴ ᴘᴏꜱᴛ", callback_data=f"an|mainpost|{uid}")],
    ])


def _final_kb(link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭕️ ᴡᴀᴛᴄʜ & ᴅᴏᴡɴʟᴏᴀᴅ ⭕️", url=link)],
    ])


# ── Network helpers ───────────────────────────────────────────────────────────
async def _tmdb(sess: aiohttp.ClientSession, path: str, **params) -> dict:
    params["api_key"] = TMDB_API_KEY
    async with sess.get(
        f"{TMDB_BASE}{path}", params=params,
        timeout=aiohttp.ClientTimeout(total=12),
    ) as r:
        return await r.json()


async def _download(url: str) -> Optional[bytes]:
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    return await r.read()
    except Exception as e:
        logger.warning("Download failed %s: %s", url, e)
    return None


async def _fetch_data(name: str, season: int) -> dict:
    async with aiohttp.ClientSession() as sess:
        search  = await _tmdb(sess, "/search/tv", query=name, language="en-US")
        results = search.get("results", [])
        is_movie = False
        if not results:
            search   = await _tmdb(sess, "/search/movie", query=name, language="en-US")
            results  = search.get("results", [])
            is_movie = True
        if not results:
            return {}

        item    = results[0]
        tmdb_id = item["id"]
        media   = "movie" if is_movie else "tv"
        title   = item.get("name") or item.get("title", name)
        year    = (item.get("first_air_date") or item.get("release_date") or "")[:4]
        rating  = round(item.get("vote_average", 0), 1)

        details  = await _tmdb(sess, f"/{media}/{tmdb_id}", language="en-US")
        genres   = [g["name"] for g in details.get("genres", [])]
        overview = details.get("overview", "")

        episodes = 0
        if not is_movie:
            try:
                sd = await _tmdb(sess, f"/tv/{tmdb_id}/season/{season}")
                episodes = len(sd.get("episodes", [])) or sd.get("episode_count", 0)
            except Exception:
                episodes = details.get("number_of_episodes", 0)
        else:
            episodes, season = 1, 1

        img_data = await _tmdb(sess, f"/{media}/{tmdb_id}/images")
        posters  = [
            f"{TMDB_POST}{p['file_path']}"
            for p in sorted(img_data.get("posters", []),
                            key=lambda x: x.get("vote_average", 0), reverse=True)[:8]
        ]
        backdrops = [
            f"{TMDB_BACK}{b['file_path']}"
            for b in sorted(img_data.get("backdrops", []),
                            key=lambda x: x.get("vote_average", 0), reverse=True)[:6]
        ]
        all_images  = posters + backdrops
        fanart_bgs: list[str] = []

        if not is_movie:
            try:
                ext     = await _tmdb(sess, f"/tv/{tmdb_id}/external_ids")
                tvdb_id = ext.get("tvdb_id")
                if tvdb_id:
                    async with sess.get(
                        f"{FANART_BASE}/tv/{tvdb_id}",
                        params={"api_key": FANART_TV_KEY},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as fr:
                        fd = await fr.json()
                    for art in fd.get("showbackground", [])[:8]:
                        url = art.get("url", "")
                        if url:
                            fanart_bgs.append(url)
                    for key in ("tvposter", "characterart", "tvthumb"):
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
            "fanart_bgs":  fanart_bgs or backdrops[:4],
            "season":      season,
        }


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
        channel_name=CHANNEL,
        offset_x=s["offset_x"],
        offset_y=s["offset_y"],
        scale=s["scale"],
    )


# ── /anime command ────────────────────────────────────────────────────────────
@Client.on_message(filters.command("anime") & filters.private)
async def anime_cmd(client: Client, message: Message):
    raw = " ".join(message.command[1:]).strip()
    if not raw:
        await message.reply_text(
            "⚠️ <b>ᴜꜱᴀɢᴇ:</b>\n"
            "<code>/anime &lt;name&gt;</code>\n"
            "<code>/anime &lt;name&gt; S02</code> — ꜱᴘᴇᴄɪꜰʏ ꜱᴇᴀꜱᴏɴ\n\n"
            "<b>ᴇxᴀᴍᴘʟᴇ:</b> <code>/anime Shield Hero S02</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    season = 1
    m = re.search(r"\bS(\d{1,2})\b$", raw, re.IGNORECASE)
    if m:
        season = int(m.group(1))
        query  = raw[:m.start()].strip()
    else:
        query = raw

    wait = await message.reply_text(
        f"🔍 ꜱᴇᴀʀᴄʜɪɴɢ <b>{query}</b> — ꜱᴇᴀꜱᴏɴ {season}...",
        parse_mode=enums.ParseMode.HTML,
    )

    data = await _fetch_data(query, season)
    if not data or not data.get("images"):
        await wait.edit_text(
            f"❌ ɴᴏ ʀᴇꜱᴜʟᴛꜱ ꜰᴏʀ <b>{query}</b>.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    uid = message.from_user.id
    sessions[uid] = {
        **data,
        "audio":    "Hindi #Official",
        "quality":  "Multi",
        "img_idx":  0,
        "offset_x": 0,
        "offset_y": 0,
        "scale":    1.0,
        "chat_id":  message.chat.id,
    }

    thumb = await _render(sessions[uid])
    await wait.delete()
    if not thumb:
        await message.reply_text("❌ ɪᴍᴀɢᴇ ʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ. ᴛʀʏ ᴀɢᴀɪɴ.")
        sessions.pop(uid, None)
        return

    await message.reply_photo(
        photo=io.BytesIO(thumb),
        caption=(
            f"🎨 <b>{data['title']}</b> — S{data['season']:02d} | "
            f"<i>{', '.join(data['genres'][:3])}</i>\n\n"
            "⬆️⬇️⬅️➡️ ᴘᴀɴ  •  ➕➖ ᴢᴏᴏᴍ  •  ◀️▶️ ꜱᴡᴀᴘ ɪᴍᴀɢᴇ"
        ),
        reply_markup=_preview_kb(uid),
        parse_mode=enums.ParseMode.HTML,
    )


# ── Callback handler ──────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^an\|"))
async def anime_cb(client: Client, cq: CallbackQuery):
    parts  = cq.data.split("|")
    action = parts[1]

    if action == "noop":
        await cq.answer()
        return

    uid = int(parts[2])

    # ── Main Post callback (after Done) ──────────────────────────────────────
    if action == "mainpost":
        if uid not in post_sessions:
            await cq.answer("ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ.", show_alert=True)
            return
        pending_link.add(uid)
        await cq.message.reply_text(
            "🔗 <b>ꜱᴇɴᴅ ᴛʜᴇ ᴡᴀᴛᴄʜ &amp; ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋ:</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer()
        return

    # ── Preview controls ──────────────────────────────────────────────────────
    if uid not in sessions:
        await cq.answer("ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ. ᴜꜱᴇ /anime ᴀɢᴀɪɴ.", show_alert=True)
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

    elif action == "done":
        redraw = False
        await cq.answer("⏳ ɢᴇɴᴇʀᴀᴛɪɴɢ...", show_alert=False)

        thumb = await _render(s)
        if not thumb:
            await cq.message.edit_caption("❌ Render failed. Try a different image ▶️")
            return

        await client.db.set_thumbnail(uid, s["images"][s["img_idx"]])

        post_sessions[uid] = {
            "title":      s["title"],
            "year":       s["year"],
            "rating":     s["rating"],
            "episodes":   s["episodes"],
            "genres":     s["genres"],
            "season":     s["season"],
            "audio":      s["audio"],
            "quality":    s["quality"],
            "fanart_bgs": s["fanart_bgs"],
            "thumb":      thumb,
        }
        sessions.pop(uid, None)
        await cq.message.edit_reply_markup(reply_markup=None)

        # Step 1 — spoiler image + AniList expandable info (run concurrently)
        al, bg_url = None, None
        al = await fetch_anilist(post_sessions[uid]["title"])
        bg_urls = post_sessions[uid]["fanart_bgs"]
        bg_url  = random.choice(bg_urls) if bg_urls else None
        bg_bytes = await _download(bg_url) if bg_url else None

        spoiler_img = make_spoiler_bg(bg_bytes, CHANNEL) if bg_bytes else None
        al_cap = (
            _anilist_caption(al, post_sessions[uid]["title"])
            if al
            else f"<b>{post_sessions[uid]['title']} In Hindi Dub Available On @{CHANNEL}...!!</b>"
        )

        if spoiler_img:
            await cq.message.reply_photo(
                photo=io.BytesIO(spoiler_img),
                caption=al_cap,
                has_spoiler=True,
                parse_mode=enums.ParseMode.HTML,
            )
        else:
            await cq.message.reply_text(al_cap, parse_mode=enums.ParseMode.HTML)

        # Step 2 — thumbnail + Powered By + Main Post button
        ps = post_sessions[uid]
        await cq.message.reply_photo(
            photo=io.BytesIO(ps["thumb"]),
            caption=_powered_caption(ps),
            reply_markup=_powered_kb(uid),
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # Redraw preview
    if redraw:
        thumb = await _render(s)
        if not thumb:
            await cq.message.edit_caption("❌ ɪᴍᴀɢᴇ ꜰᴀɪʟᴇᴅ. ᴛʀʏ ɴᴇxᴛ ▶️")
            return
        await cq.message.edit_media(
            InputMediaPhoto(
                media=io.BytesIO(thumb),
                caption=(
                    f"🎨 <b>{s['title']}</b> — S{s['season']:02d} | "
                    f"<i>{', '.join(s['genres'][:3])}</i>\n\n"
                    "⬆️⬇️⬅️➡️ ᴘᴀɴ  •  ➕➖ ᴢᴏᴏᴍ  •  ◀️▶️ ꜱᴡᴀᴘ ɪᴍᴀɢᴇ"
                ),
            ),
            reply_markup=_preview_kb(uid),
            parse_mode=enums.ParseMode.HTML,
        )


# ── Link collection ───────────────────────────────────────────────────────────
@Client.on_message(filters.private & filters.regex(r"https?://\S+"))
async def link_handler(client: Client, message: Message):
    uid = message.from_user.id
    # Ignore commands and users not awaiting a link
    if message.text and message.text.startswith("/"):
        return
    if uid not in pending_link or uid not in post_sessions:
        return

    link = message.text.strip().split()[0]  # first URL only
    ps   = post_sessions.pop(uid)
    pending_link.discard(uid)

    await message.reply_photo(
        photo=io.BytesIO(ps["thumb"]),
        caption=_final_caption(ps),
        reply_markup=_final_kb(link),
        parse_mode=enums.ParseMode.HTML,
    )
