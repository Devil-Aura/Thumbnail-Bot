import re
import aiohttp

ANILIST_URL = "https://graphql.anilist.co"

_QUERY = """
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


async def _query_anilist(search: str) -> dict | None:
    """Run a single AniList search and return structured dict or None."""
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                ANILIST_URL,
                json={"query": _QUERY, "variables": {"search": search}},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r:
                data = await r.json()
        media = (data.get("data") or {}).get("Media")
        if not media:
            return None

        title_en  = media["title"].get("english") or ""
        title_ro  = media["title"].get("romaji")  or ""
        display   = (
            f"{title_en.upper()} | {title_ro}" if title_en and title_ro
            else (title_en or title_ro).upper()
        )
        start_d   = media.get("startDate") or {}
        year      = str(start_d["year"]) if start_d.get("year") else ""
        episodes  = media.get("episodes") or 0
        genres    = media.get("genres") or []
        synopsis  = _strip_html(media.get("description") or "")
        cover_img = media.get("coverImage") or {}
        cover     = cover_img.get("extraLarge") or cover_img.get("large") or ""

        return {
            "display":  display,
            "title_en": title_en,
            "title_ro": title_ro,
            "year":     year,
            "genres":   genres,
            "format":   (media.get("format") or "TV").replace("_", " "),
            "score":    media.get("averageScore") or 0,
            "status":   (media.get("status") or "").replace("_", " "),
            "start":    _date(start_d),
            "end":      _date(media.get("endDate") or {}),
            "duration": media.get("duration") or 0,
            "episodes": episodes,
            "synopsis": synopsis,
            "banner":   media.get("bannerImage") or "",
            "cover":    cover,
        }
    except Exception:
        return None


async def fetch_anilist(name: str, season: int = 1) -> dict | None:
    """
    Fetch anime metadata from AniList with season-aware searching.
    Season > 1: tries multiple query variants so the correct season entry is matched.
    AniList stores each season as a separate Media entry.
    """
    _ORDINALS = {2: "2nd", 3: "3rd", 4: "4th", 5: "5th",
                 6: "6th", 7: "7th", 8: "8th", 9: "9th", 10: "10th"}

    if season > 1:
        ord_str = _ORDINALS.get(season, f"{season}th")
        queries = [
            f"{name} Season {season}",
            f"{name} {ord_str} Season",
            f"{name} {season}",
            name,               # last-resort: base title only
        ]
    else:
        queries = [name]

    for q in queries:
        result = await _query_anilist(q)
        if result:
            return result
    return None
