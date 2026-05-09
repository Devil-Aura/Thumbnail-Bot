import re
import aiohttp

ANILIST_URL = "https://graphql.anilist.co"

QUERY = """
query ($search: String) {
  Media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
    title { romaji english }
    genres
    format
    averageScore
    status
    startDate { year month day }
    endDate   { year month day }
    duration
    episodes
    description(asHtml: false)
    coverImage { extraLarge large }
    bannerImage
  }
}
"""


def _date(d: dict) -> str:
    if not d or not d.get("year"):
        return ""
    parts = [str(d["year"])]
    if d.get("month"):
        parts.append(str(d["month"]))
        if d.get("day"):
            parts.append(str(d["day"]))
    return "-".join(parts)


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


async def fetch_anilist(name: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                ANILIST_URL,
                json={"query": QUERY, "variables": {"search": name}},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r:
                data = await r.json()
        media = data.get("data", {}).get("Media")
        if not media:
            return None

        title_en = media["title"].get("english") or ""
        title_ro = media["title"].get("romaji")  or ""
        if title_en and title_ro:
            display = f"{title_en.upper()} | {title_ro}"
        else:
            display = (title_en or title_ro).upper()

        fmt    = (media.get("format") or "TV").replace("_", " ")
        score  = media.get("averageScore") or 0
        status = (media.get("status") or "").replace("_", " ")
        eps    = media.get("episodes") or 0
        dur    = media.get("duration") or 0
        genres = media.get("genres") or []
        start  = _date(media.get("startDate") or {})
        end    = _date(media.get("endDate")   or {})
        synopsis = _strip_html(media.get("description") or "")
        banner   = media.get("bannerImage") or ""
        cover_img = media.get("coverImage") or {}
        cover    = cover_img.get("extraLarge") or cover_img.get("large") or ""

        return {
            "display":  display,
            "title_en": title_en,
            "title_ro": title_ro,
            "genres":   genres,
            "format":   fmt,
            "score":    score,
            "status":   status,
            "start":    start,
            "end":      end,
            "duration": dur,
            "episodes": eps,
            "synopsis": synopsis,
            "banner":   banner,
            "cover":    cover,
        }
    except Exception:
        return None
