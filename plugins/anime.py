"""
/anime <name> [S01]

Flow:
  1. Preview thumbnail  → pan/zoom/image-swap + logo-toggle controls
  2. ✅ Done  → spoiler 4K BG + AniList expandable info
             → thumbnail + Powered By + [📢 Main Post] [🎬 Anime GFX] [🖼 Cover]
  3. [📢 Main Post]  → ask for Watch & Download link → final post
  4. [🎬 Anime GFX]  → send thumbnail to all GFX channels (turns green, one-time)
  5. [🖼 Cover]       → send thumbnail to Cover channels, reply with /cmd Title
"""
import io
import logging
import random
import re
from typing import Optional

import aiohttp
from pyrogram import Client, enums, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from config import TMDB_API_KEY, FANART_TV_KEY
from utils.anilist import fetch_anilist
from utils.extra_images import fetch_all_extra
from utils.image_generator import make_anime_thumbnail, make_spoiler_bg

logger = logging.getLogger(__name__)

TMDB_BASE   = "https://api.themoviedb.org/3"
TMDB_POST   = "https://image.tmdb.org/t/p/w780"
TMDB_BACK   = "https://image.tmdb.org/t/p/original"   # 4K originals
FANART_BASE = "https://webservice.fanart.tv/v3"
CHANNEL     = "CrunchyRollChannel"

# ── Safe caption sender — falls back if blockquote not supported ─────────────
def _strip_bq(text: str) -> str:
    """Strip blockquote tags for Pyrogram versions that don't support them."""
    return (text
        .replace("<blockquote expandable>", "")
        .replace("<blockquote>", "")
        .replace("</blockquote>", ""))


async def _send_photo_caption(target, photo, caption, *, reply_markup=None,
                               has_spoiler=False, **kw):
    """Send photo with HTML caption; retry without blockquote on parse error."""
    from pyrogram import enums
    kwargs = dict(parse_mode=enums.ParseMode.HTML)
    if reply_markup:
        kwargs["reply_markup"] = reply_markup
    if has_spoiler:
        kwargs["has_spoiler"] = True
    try:
        return await target.reply_photo(photo=photo, caption=caption, **kwargs)
    except Exception:
        return await target.reply_photo(photo=photo,
                                        caption=_strip_bq(caption), **kwargs)


async def _reply_caption(target, caption, *, reply_markup=None, **kw):
    """Send text caption; retry without blockquote on parse error."""
    from pyrogram import enums
    kwargs = dict(parse_mode=enums.ParseMode.HTML)
    if reply_markup:
        kwargs["reply_markup"] = reply_markup
    try:
        return await target.reply_text(caption, **kwargs)
    except Exception:
        return await target.reply_text(_strip_bq(caption), **kwargs)


# ── State ─────────────────────────────────────────────────────────────────────
sessions:      dict[int, dict] = {}   # uid → preview session
post_sessions: dict[int, dict] = {}   # uid → post data after Done
pending_link:  set[int]        = set()

STEP_PX    = 60
STEP_SCALE = 0.15

GFX_CAPTION = (
    "<b>Thumbnail designed by @Anime_Gfx</b>\n"
    "⚠️ Take permission before using my content on any platform.\n"
    "Unauthorized use is strictly prohibited!\n\n"
    "© @Anime_Gfx – All Rights Reserved."
)


# ── Short title helper ────────────────────────────────────────────────────────
def _short_title(title: str) -> str:
    """Return roughly the first half of the title (word-boundary)."""
    words = title.split()
    half  = max(1, len(words) // 2)
    return " ".join(words[:half])


# ── Caption builders ──────────────────────────────────────────────────────────
def _powered_caption(ps: dict) -> str:
    genres = ", ".join(ps["genres"][:5]) or "N/A"
    return (
        f"<b>⛩ {ps['title']} [S{ps['season']:02d}]</b>\n"
        f"<blockquote><b>"
        f"╭───────────────────\n"
        f"├ ✨ Ratings - {ps['rating']} IMDB\n"
        f"├ ❄️ Season - {ps['season']:02d}\n"
        f"├ 🎬 Episodes - {ps['episodes']}\n"
        f"├ 🔈 Audio - {ps['audio']}\n"
        f"├ 📸 Quality - {ps['quality']}\n"
        f"├ 🎭 Genres - {genres}\n"
        f"╰───────────────────"
        f"</b></blockquote>\n"
        f"<b>• 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗕𝘆:\n"
        f"@{CHANNEL}.</b>"
    )


def _final_caption(ps: dict, link: str) -> str:
    genres = ", ".join(ps["genres"][:5]) or "N/A"
    return (
        f"<b>⛩ {ps['title']} [S{ps['season']:02d}]</b>\n"
        f"<blockquote><b>"
        f"╭───────────────────\n"
        f"├ ✨ Ratings - {ps['rating']} IMDB\n"
        f"├ ❄️ Season - {ps['season']:02d}\n"
        f"├ 🎬 Episodes - {ps['episodes']}\n"
        f"├ 🔈 Audio - {ps['audio']}\n"
        f"├ 📸 Quality - {ps['quality']}\n"
        f"├ 🎭 Genres - {genres}\n"
        f"├───────────────────\n"
        f"├ ⭕️ <a href='{link}'>Watch &amp; Download</a> ⭕️\n"
        f"╰──────────────────"
        f"</b></blockquote>\n"
        f"<b>New Anime In Official Hindi Dub 🔥</b>"
    )


def _anilist_caption(al: dict, anime_title: str) -> str:
    genres = ", ".join(al["genres"][:6]) if al["genres"] else "N/A"
    syn    = al["synopsis"]
    if len(syn) > 850:
        syn = syn[:850] + "…"
    inner = (
        f"<b>{al['display']}</b>\n\n"
        f"‣ <b>Genres</b> : {genres}\n"
        f"‣ <b>Type</b> : {al['format']}\n"
        f"‣ <b>Average Rating</b> : {al['score']}\n"
        f"‣ <b>Status</b> : {al['status']}\n"
        f"‣ <b>First aired</b> : {al['start']}\n"
        f"‣ <b>Last aired</b> : {al['end'] or ''}\n"
        f"‣ <b>Runtime</b> : {al['duration']} minutes\n"
        f"‣ <b>No of episodes</b> : {al['episodes']}\n\n"
        f"‣ <b>Synopsis</b> : \"{syn}\""
    )
    return (
        f"<b>{anime_title} In Hindi Dub Available On @{CHANNEL}...!!</b>\n\n"
        f"<blockquote expandable>{inner}</blockquote>"
    )


# ── Keyboards ─────────────────────────────────────────────────────────────────
def _preview_kb(uid: int) -> InlineKeyboardMarkup:
    s        = sessions[uid]
    idx      = s["img_idx"]
    tot      = len(s["images"])
    pct      = int(s["scale"] * 100)
    has_logo = bool(s.get("logo_urls"))
    use_logo = s.get("use_logo", False)

    logo_label = "✅ 🔤 Logo ON" if use_logo else ("🔤 Logo" if has_logo else "🔤 No Logo")

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ ᴩʀᴇᴠ",         callback_data=f"an|prev|{uid}"),
            InlineKeyboardButton(f"🖼 {idx+1}/{tot}", callback_data="an|noop"),
            InlineKeyboardButton("ɴᴇxᴛ ▶️",          callback_data=f"an|next|{uid}"),
        ],
        [
            InlineKeyboardButton("​",  callback_data="an|noop"),
            InlineKeyboardButton("⬆️", callback_data=f"an|up|{uid}"),
            InlineKeyboardButton("​",  callback_data="an|noop"),
        ],
        [
            InlineKeyboardButton("⬅️", callback_data=f"an|left|{uid}"),
            InlineKeyboardButton("⬇️", callback_data=f"an|down|{uid}"),
            InlineKeyboardButton("➡️", callback_data=f"an|right|{uid}"),
        ],
        [
            InlineKeyboardButton("➖",          callback_data=f"an|zout|{uid}"),
            InlineKeyboardButton(f"🔍 {pct}%",  callback_data="an|noop"),
            InlineKeyboardButton("➕",          callback_data=f"an|zin|{uid}"),
        ],
        [
            InlineKeyboardButton(logo_label, callback_data=f"an|logo|{uid}"),
        ],
        [InlineKeyboardButton("✅  ᴅᴏɴᴇ", callback_data=f"an|done|{uid}")],
    ])


def _post_kb(uid: int, gfx_done: bool = False, cover_done: bool = False) -> InlineKeyboardMarkup:
    gfx_label   = "✅ ᴀɴɪᴍᴇ ɢꜰx ✓" if gfx_done   else "🎬 ᴀɴɪᴍᴇ ɢꜰx"
    cover_label = "✅ ᴄᴏᴠᴇʀ ✓"       if cover_done else "🖼 ᴄᴏᴠᴇʀ"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 ᴍᴀɪɴ ᴘᴏꜱᴛ", callback_data=f"an|mainpost|{uid}")],
        [
            InlineKeyboardButton(gfx_label,   callback_data=f"an|gfx|{uid}"),
            InlineKeyboardButton(cover_label, callback_data=f"an|cover|{uid}"),
        ],
    ])


def _final_kb(link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭕️  ᴡᴀᴛᴄʜ & ᴅᴏᴡɴʟᴏᴀᴅ  ⭕️", url=link)],
    ])


# ── Network helpers ────────────────────────────────────────────────────────────
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
    try:
        return await _fetch_data_inner(name, season)
    except aiohttp.ClientConnectorError:
        raise
    except Exception as e:
        logger.error("_fetch_data error: %s", e)
        raise


async def _fetch_data_inner(name: str, season: int) -> dict:
    async with aiohttp.ClientSession() as sess:
        search   = await _tmdb(sess, "/search/tv", query=name, language="en-US")
        results  = search.get("results", [])
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
                # Season-specific year & description from TMDB
                s_year = (sd.get("air_date") or "")[:4]
                if s_year:
                    year = s_year
                s_overview = (sd.get("overview") or "").strip()
                if s_overview:
                    overview = s_overview
            except Exception:
                episodes = details.get("number_of_episodes", 0)
        else:
            episodes, season = 1, 1

        # AniList: override year / episodes / description / genres
        try:
            from utils.anilist import fetch_anilist as _al
            al = await _al(name, season=season)
            if al:
                if al.get("year"):
                    year = al["year"]
                if al.get("episodes"):
                    episodes = al["episodes"]
                if al.get("synopsis"):
                    overview = al["synopsis"]
                if al.get("genres"):
                    genres = al["genres"]
        except Exception:
            pass

        # Images: request no-language first (clean cinematic shots, no burned-in text)
        img_data = await _tmdb(
            sess, f"/{media}/{tmdb_id}/images",
            include_image_language="null,en",
        )

        # Deduplicate by file_path so same artwork doesn't appear twice
        seen_paths: set[str] = set()

        # Season-specific images (stills/posters) from TMDB — put FIRST
        season_backdrops: list[str] = []
        season_posters:   list[str] = []
        if not is_movie:
            try:
                s_img = await _tmdb(sess, f"/tv/{tmdb_id}/season/{season}/images")
                for still in sorted(s_img.get("stills", []),
                                    key=lambda x: x.get("vote_average", 0), reverse=True)[:12]:
                    fp = still.get("file_path", "")
                    if fp and fp not in seen_paths:
                        seen_paths.add(fp)
                        season_backdrops.append(f"{TMDB_BACK}{fp}")
                for sp in sorted(s_img.get("posters", []),
                                 key=lambda x: x.get("vote_average", 0), reverse=True)[:6]:
                    fp = sp.get("file_path", "")
                    if fp and fp not in seen_paths:
                        seen_paths.add(fp)
                        season_posters.append(f"{TMDB_POST}{fp}")
            except Exception as _sie:
                logger.warning("Season images fetch failed: %s", _sie)

        # Show-level backdrops & posters — no-language first for clean art
        backdrops_raw = img_data.get("backdrops", [])
        backdrops_no_lang = [b for b in backdrops_raw if not b.get("iso_639_1")]
        backdrops_rest    = [b for b in backdrops_raw if b.get("iso_639_1")]
        backdrops_no_lang.sort(key=lambda x: x.get("vote_average", 0), reverse=True)
        backdrops_rest.sort(key=lambda x: x.get("vote_average", 0), reverse=True)

        backdrops: list[str] = []
        for b in (backdrops_no_lang[:8] + backdrops_rest[:4]):
            fp = b.get("file_path", "")
            if fp and fp not in seen_paths:
                seen_paths.add(fp)
                backdrops.append(f"{TMDB_BACK}{fp}")

        posters: list[str] = []
        for p in sorted(img_data.get("posters", []),
                        key=lambda x: x.get("vote_average", 0), reverse=True)[:8]:
            fp = p.get("file_path", "")
            if fp and fp not in seen_paths:
                seen_paths.add(fp)
                posters.append(f"{TMDB_POST}{fp}")

        # Season-specific images come first, then show-level fill the rest
        all_images = season_backdrops + season_posters + backdrops + posters
        fanart_bgs: list[str] = []
        logo_urls:  list[str] = []

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

                    fanart_wide: list[str] = []
                    for art in fd.get("showbackground", [])[:8]:
                        url = art.get("url", "")
                        if url:
                            fanart_bgs.append(url)
                            fanart_wide.append(url)
                    # Fanart wide landscape images at the FRONT
                    if fanart_wide:
                        all_images = fanart_wide + all_images

                    for key in ("tvposter", "characterart", "tvthumb"):
                        for art in fd.get(key, [])[:3]:
                            url = art.get("url", "")
                            if url and url not in all_images:
                                all_images.append(url)

                    # HD ClearLOGO — prefer English, fallback to any language
                    for art in sorted(fd.get("hdtvlogo", []),
                                      key=lambda x: (x.get("lang", "") == "en",
                                                     int(x.get("likes", 0))),
                                      reverse=True)[:5]:
                        url = art.get("url", "")
                        if url:
                            logo_urls.append(url)
                    if not logo_urls:
                        for art in fd.get("clearlogo", [])[:3]:
                            url = art.get("url", "")
                            if url:
                                logo_urls.append(url)
            except Exception as e:
                logger.warning("FANART.TV: %s", e)

        # Extra fan art: 20 free sources — Safebooru, Konachan, DuckDuckGo, etc.
        try:
            extra = await fetch_all_extra(title)
            seen = set(all_images)
            for url in extra:
                if url not in seen:
                    all_images.append(url)
                    seen.add(url)
            logger.info("Total images for '%s': %d (incl. %d extra)",
                        title, len(all_images), len(extra))
        except Exception as e:
            logger.warning("Extra images fetch failed: %s", e)

        return {
            "title":       title,
            "year":        year,
            "rating":      rating,
            "episodes":    episodes,
            "genres":      genres,
            "description": overview,
            "images":      all_images,
            "fanart_bgs":  fanart_bgs or backdrops[:4],
            "logo_urls":   logo_urls,
            "season":      season,
        }


async def _render(s: dict) -> Optional[bytes]:
    bg = await _download(s["images"][s["img_idx"]])
    if not bg:
        return None

    # Download ClearLogo if use_logo is toggled on
    logo_bytes: Optional[bytes] = None
    if s.get("use_logo") and s.get("logo_urls"):
        logo_bytes = await _download(s["logo_urls"][0])

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
        logo_bytes=logo_bytes,
    )


# ── /anime command ─────────────────────────────────────────────────────────────
@Client.on_message(filters.command("anime") & filters.private)
async def anime_cmd(client: Client, message: Message):
    raw = " ".join(message.command[1:]).strip()
    if not raw:
        await message.reply_text(
            "⚠️ <b>Usage:</b>\n"
            "<code>/anime &lt;name&gt;</code>\n"
            "<code>/anime &lt;name&gt; S02</code> — specify season\n\n"
            "<b>Examples:</b>\n"
            "<code>/anime Fairy Tail</code>\n"
            "<code>/anime Shield Hero S02</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    season = 1
    m = re.search(r"\bS(?:eason\s*)?(\d{1,2})\b$", raw, re.IGNORECASE)
    if m:
        season = int(m.group(1))
        query  = raw[:m.start()].strip()
    else:
        query = raw

    wait = await message.reply_text(
        f"🔍 Searching <b>{query}</b> — Season {season}...",
        parse_mode=enums.ParseMode.HTML,
    )

    try:
        data = await _fetch_data(query, season)
    except aiohttp.ClientConnectorError:
        await wait.edit_text(
            "❌ <b>Network Error</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Cannot reach <b>TMDB</b> — the server has no internet access.\n\n"
            "<blockquote>"
            "This usually means your hosting platform blocks outbound\n"
            "connections. Make sure your server allows HTTPS requests\n"
            "to <code>api.themoviedb.org</code>."
            "</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return
    except Exception as e:
        await wait.edit_text(
            f"❌ <b>Unexpected error while fetching data.</b>\n"
            f"<blockquote><code>{type(e).__name__}: {e}</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    if not data or not data.get("images"):
        await wait.edit_text(
            f"❌ No results for <b>{query}</b>. Check the spelling and try again.",
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
        "use_logo": False,
        "chat_id":  message.chat.id,
    }

    has_logo  = bool(data.get("logo_urls"))
    logo_note = "  •  🔤 Logo available" if has_logo else ""

    thumb = await _render(sessions[uid])
    await wait.delete()
    if not thumb:
        await message.reply_text("❌ Image load failed. Try again.")
        sessions.pop(uid, None)
        return

    ph      = io.BytesIO(thumb)
    ph.name = "thumb.jpg"
    await message.reply_photo(
        photo=ph,
        caption=(
            f"🎨 <b>{data['title']}</b> — S{data['season']:02d}\n"
            f"<i>{', '.join(data['genres'][:3])}</i>\n\n"
            f"⬆️⬇️⬅️➡️ Pan  •  ➕➖ Zoom  •  ◀️▶️ Swap image{logo_note}"
        ),
        reply_markup=_preview_kb(uid),
        parse_mode=enums.ParseMode.HTML,
    )


# ── Callback handler ───────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^an\|"))
async def anime_cb(client: Client, cq: CallbackQuery):
    parts  = cq.data.split("|")
    action = parts[1]

    if action == "noop":
        await cq.answer()
        return

    uid = int(parts[2])

    # ── Main Post ──────────────────────────────────────────────────────────────
    if action == "mainpost":
        if uid not in post_sessions:
            await cq.answer("Session expired.", show_alert=True)
            return
        pending_link.add(uid)
        await cq.message.reply_text(
            "🔗 <b>Send the Watch &amp; Download link now:</b>",
            parse_mode=enums.ParseMode.HTML,
        )
        await cq.answer("📨 Send the link below ↓")
        return

    # ── Anime GFX send ─────────────────────────────────────────────────────────
    if action == "gfx":
        if uid not in post_sessions:
            await cq.answer("Session expired.", show_alert=True)
            return
        ps = post_sessions[uid]
        if ps.get("gfx_done"):
            await cq.answer("✅ Already sent to GFX channels!", show_alert=True)
            return

        gfx_channels = await client.db.get_gfx_channels(uid)
        if not gfx_channels:
            await cq.answer(
                "⚠️ No GFX channels added!\nGo to /settings to add channels.",
                show_alert=True,
            )
            return

        sent_count = 0
        fail_msgs  = []
        for ch in gfx_channels:
            try:
                photo_io      = io.BytesIO(ps["thumb"])
                photo_io.name = "thumb.jpg"
                await client.send_photo(
                    chat_id=ch["id"],
                    photo=photo_io,
                    caption=GFX_CAPTION,
                    parse_mode=enums.ParseMode.HTML,
                )
                sent_count += 1
            except Exception as e:
                err = str(e)
                logger.error("GFX send to %s failed: %s", ch.get("title", ch["id"]), err)
                fail_msgs.append(f"• {ch.get('title', ch['id'])}: {err}")

        ps["gfx_done"] = True

        try:
            await cq.message.edit_reply_markup(
                reply_markup=_post_kb(uid, gfx_done=True, cover_done=ps.get("cover_done", False))
            )
        except MessageNotModified:
            pass

        if sent_count:
            alert = f"✅ Sent to {sent_count} GFX channel(s)!"
            if fail_msgs:
                alert += f"\n⚠️ {len(fail_msgs)} failed — check /logs"
        else:
            alert = "❌ Failed to send to any GFX channel.\nCheck bot admin rights and /logs"
        await cq.answer(alert, show_alert=True)
        return

    # ── Cover send ─────────────────────────────────────────────────────────────
    if action == "cover":
        if uid not in post_sessions:
            await cq.answer("Session expired.", show_alert=True)
            return
        ps = post_sessions[uid]
        if ps.get("cover_done"):
            await cq.answer("✅ Already sent to Cover channels!", show_alert=True)
            return

        cover_channels = await client.db.get_cover_channels(uid)
        if not cover_channels:
            await cq.answer(
                "⚠️ No Cover channels added!\nGo to /settings to add channels.",
                show_alert=True,
            )
            return

        short = _short_title(ps["title"])
        sent_count = 0
        fail_msgs  = []
        for ch in cover_channels:
            try:
                photo_io      = io.BytesIO(ps["thumb"])
                photo_io.name = "thumb.jpg"
                sent_msg = await client.send_photo(
                    chat_id=ch["id"],
                    photo=photo_io,
                )
                cmd = ch.get("command", "/cover")
                await sent_msg.reply_text(f"{cmd} {short}")
                sent_count += 1
            except Exception as e:
                err = str(e)
                logger.error("Cover send to %s failed: %s", ch.get("title", ch["id"]), err)
                fail_msgs.append(f"• {ch.get('title', ch['id'])}: {err}")

        ps["cover_done"] = True

        try:
            await cq.message.edit_reply_markup(
                reply_markup=_post_kb(uid, gfx_done=ps.get("gfx_done", False), cover_done=True)
            )
        except MessageNotModified:
            pass

        if sent_count:
            alert = f"✅ Sent to {sent_count} Cover channel(s)!"
            if fail_msgs:
                alert += f"\n⚠️ {len(fail_msgs)} failed — check /logs"
        else:
            alert = "❌ Failed to send to any Cover channel.\nCheck bot admin rights and /logs"
        await cq.answer(alert, show_alert=True)
        return

    # ── Preview controls ───────────────────────────────────────────────────────
    if uid not in sessions:
        await cq.answer("Session expired. Use /anime again.", show_alert=True)
        return
    if cq.from_user.id != uid:
        await cq.answer("This is not your session!", show_alert=True)
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
        await cq.answer(f"🔍 {int(s['scale']*100)}%")
    elif action == "zout":
        s["scale"] = max(1.0, round(s["scale"] - STEP_SCALE, 2))
        await cq.answer(f"🔍 {int(s['scale']*100)}%")

    elif action == "logo":
        if not s.get("logo_urls"):
            await cq.answer("⚠️ No ClearLogo available for this anime on Fanart.tv",
                            show_alert=True)
            return
        s["use_logo"] = not s.get("use_logo", False)
        state = "ON ✅" if s["use_logo"] else "OFF"
        await cq.answer(f"🔤 Logo {state}")

    elif action == "done":
        redraw = False
        await cq.answer("⏳ Generating...", show_alert=False)

        thumb = await _render(s)
        if not thumb:
            await cq.message.edit_caption(
                "❌ Render failed. Try a different image ▶️",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        await client.db.set_thumbnail(uid, s["images"][s["img_idx"]])

        post_sessions[uid] = {
            k: s[k] for k in
            ("title","year","rating","episodes","genres",
             "season","audio","quality","fanart_bgs")
        }
        post_sessions[uid]["thumb"]      = thumb
        post_sessions[uid]["gfx_done"]   = False
        post_sessions[uid]["cover_done"] = False
        sessions.pop(uid, None)

        try:
            await cq.message.edit_reply_markup(reply_markup=None)
        except MessageNotModified:
            pass

        # Step 1 — Spoiler image + AniList
        ps       = post_sessions[uid]
        al       = await fetch_anilist(ps["title"])
        bg_urls  = ps["fanart_bgs"]
        bg_bytes = await _download(random.choice(bg_urls)) if bg_urls else None
        spoiler  = make_spoiler_bg(bg_bytes) if bg_bytes else None

        al_cap = (
            _anilist_caption(al, ps["title"])
            if al
            else f"<b>{ps['title']} In Hindi Dub Available On @{CHANNEL}...!!</b>"
        )

        if spoiler:
            sp_io      = io.BytesIO(spoiler)
            sp_io.name = "spoiler.jpg"
            await _send_photo_caption(
                cq.message, sp_io, al_cap, has_spoiler=True)
        else:
            await _reply_caption(cq.message, al_cap)

        # Step 2 — Thumbnail + Powered By + action buttons
        th_io      = io.BytesIO(ps["thumb"])
        th_io.name = "thumb.jpg"
        await _send_photo_caption(
            cq.message, th_io,
            _powered_caption(ps), reply_markup=_post_kb(uid))
        return

    # ── Redraw preview ─────────────────────────────────────────────────────────
    if redraw:
        # Auto-skip broken image URLs — try up to len(images) before giving up
        thumb = None
        total = len(s["images"])
        for attempt in range(total):
            thumb = await _render(s)
            if thumb:
                break
            logger.warning("Image load failed, skipping idx %d", s["img_idx"])
            s["img_idx"] = (s["img_idx"] + 1) % total
            s["offset_x"] = s["offset_y"] = 0

        if not thumb:
            try:
                await cq.message.edit_caption(
                    "❌ No working images found. Try /anime again.",
                    parse_mode=enums.ParseMode.HTML,
                )
            except MessageNotModified:
                pass
            return

        idx_display = s["img_idx"] + 1
        try:
            th_io      = io.BytesIO(thumb)
            th_io.name = "thumb.jpg"
            await cq.message.edit_media(
                InputMediaPhoto(
                    media=th_io,
                    caption=(
                        f"🎨 <b>{s['title']}</b> — S{s['season']:02d}  "
                        f"<code>[{idx_display}/{total}]</code>\n"
                        f"<i>{', '.join(s['genres'][:3])}</i>\n\n"
                        "⬆️⬇️⬅️➡️ Pan  •  ➕➖ Zoom  •  ◀️▶️ Swap image"
                    ),
                    parse_mode=enums.ParseMode.HTML,
                ),
                reply_markup=_preview_kb(uid),
            )
        except MessageNotModified:
            pass


# ── Link collection ────────────────────────────────────────────────────────────
@Client.on_message(filters.private & filters.regex(r"https?://\S+"))
async def link_handler(client: Client, message: Message):
    uid = message.from_user.id
    if message.text and message.text.startswith("/"):
        return
    if uid not in pending_link or uid not in post_sessions:
        return

    link = message.text.strip().split()[0]
    ps   = post_sessions.pop(uid)
    pending_link.discard(uid)

    th_io      = io.BytesIO(ps["thumb"])
    th_io.name = "thumb.jpg"
    await _send_photo_caption(
        message, th_io,
        _final_caption(ps, link), reply_markup=_final_kb(link))
