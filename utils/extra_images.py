"""
Extra image sources — all FREE, no API key required.
Sources (20 total including existing):
  1.  Safebooru      — anime fan art board
  2.  Konachan       — HD anime wallpapers
  3.  DuckDuckGo     — web-wide image search
  4.  Gelbooru       — large anime art board
  5.  Danbooru       — quality anime art
  6.  Yande.re       — HD anime scans
  7.  Jikan/MAL      — MyAnimeList official images
  8.  Kitsu          — anime database covers
  9.  Waifu.im       — character art
  10. AniList        — anime/character images
  11. Tbib           — booru board
  12. Lolibooru      — safe anime art board
  13. Zerochan       — largest anime art collection
  14. Anime-pictures — clean HD wallpapers
  15. Behoimi        — booru board
  16. Nekos.best     — anime images
  17. Hybooru        — booru board
  18. Aniwatch       — anime streaming art
  19. Pollinations   — AI-generated anime images (free)
  20. Brave Search   — web image fallback
"""
import asyncio
import logging
import re
import urllib.parse
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tag(query: str) -> str:
    return re.sub(r"\s+", "_", query.strip().lower())


async def _get_json(url: str, params: dict | None = None,
                    headers: dict | None = None, timeout: int = 12) -> object:
    try:
        async with aiohttp.ClientSession(headers=headers or _BROWSER_HEADERS) as sess:
            async with sess.get(
                url, params=params,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
    except Exception as e:
        logger.debug("GET %s error: %s", url, e)
    return None


# ── 1. Safebooru ──────────────────────────────────────────────────────────────
async def fetch_safebooru(query: str, max_results: int = 6) -> list[str]:
    data = await _get_json(
        "https://safebooru.org/index.php",
        params={"page": "dapi", "s": "post", "q": "index",
                "tags": _tag(query), "limit": max_results, "json": "1"},
    )
    if not isinstance(data, list):
        return []
    return [
        u for p in data
        if (u := p.get("file_url") or p.get("sample_url", ""))
        and u.startswith("http")
    ][:max_results]


# ── 2. Konachan ───────────────────────────────────────────────────────────────
async def fetch_konachan(query: str, max_results: int = 4) -> list[str]:
    data = await _get_json(
        "https://konachan.net/post.json",
        params={"tags": _tag(query), "limit": max_results},
    )
    if not isinstance(data, list):
        return []
    return [
        u for p in data
        if (u := p.get("sample_url") or p.get("file_url", ""))
        and u.startswith("http")
    ][:max_results]


# ── 3. DuckDuckGo ─────────────────────────────────────────────────────────────
async def fetch_ddg_images(query: str, max_results: int = 8) -> list[str]:
    urls: list[str] = []
    try:
        async with aiohttp.ClientSession(headers=_BROWSER_HEADERS) as sess:
            async with sess.get(
                "https://duckduckgo.com/",
                params={"q": query, "iax": "images", "ia": "images"},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r:
                text = await r.text()
            vqd: Optional[str] = None
            for pat in [r'vqd=(["\'])(.+?)\1', r'"vqd"\s*:\s*"([^"]+)"', r"vqd=([\d-]+)"]:
                m = re.search(pat, text)
                if m:
                    vqd = m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1)
                    break
            if not vqd:
                return []
            async with sess.get(
                "https://duckduckgo.com/i.js",
                params={"q": query, "vqd": vqd, "o": "json", "f": ",,,,,", "p": "-1"},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    for item in data.get("results", []):
                        img = item.get("image", "")
                        w, h = item.get("width", 0), item.get("height", 0)
                        if img and img.startswith("http") and not img.endswith(".svg") \
                                and w >= 400 and h >= 300:
                            urls.append(img)
                            if len(urls) >= max_results:
                                break
    except Exception as e:
        logger.warning("DDG error (%s): %s", query, e)
    return urls


# ── 4. Gelbooru ───────────────────────────────────────────────────────────────
async def fetch_gelbooru(query: str, max_results: int = 6) -> list[str]:
    data = await _get_json(
        "https://gelbooru.com/index.php",
        params={"page": "dapi", "s": "post", "q": "index", "json": "1",
                "tags": _tag(query) + " rating:general", "limit": max_results},
    )
    if not isinstance(data, dict):
        return []
    posts = data.get("post", [])
    return [
        u for p in posts
        if (u := p.get("file_url") or p.get("sample_url", ""))
        and u.startswith("http") and not u.endswith(".webm")
    ][:max_results]


# ── 5. Danbooru ───────────────────────────────────────────────────────────────
async def fetch_danbooru(query: str, max_results: int = 5) -> list[str]:
    data = await _get_json(
        "https://danbooru.donmai.us/posts.json",
        params={"tags": _tag(query) + " rating:g", "limit": max_results},
    )
    if not isinstance(data, list):
        return []
    return [
        u for p in data
        if (u := p.get("large_file_url") or p.get("file_url", ""))
        and u.startswith("http") and not u.endswith(".webm") and not u.endswith(".mp4")
    ][:max_results]


# ── 6. Yande.re ───────────────────────────────────────────────────────────────
async def fetch_yandere(query: str, max_results: int = 5) -> list[str]:
    data = await _get_json(
        "https://yande.re/post.json",
        params={"tags": _tag(query), "limit": max_results},
    )
    if not isinstance(data, list):
        return []
    return [
        u for p in data
        if (u := p.get("sample_url") or p.get("file_url", ""))
        and u.startswith("http") and not u.endswith(".webm")
    ][:max_results]


# ── 7. Jikan (MyAnimeList) ────────────────────────────────────────────────────
async def fetch_jikan(query: str, max_results: int = 6) -> list[str]:
    search = await _get_json(
        "https://api.jikan.moe/v4/anime",
        params={"q": query, "limit": 1},
        headers={"User-Agent": "ThumbnailBot/1.0"},
    )
    if not isinstance(search, dict):
        return []
    data = search.get("data", [])
    if not data:
        return []
    mal_id = data[0].get("mal_id")
    if not mal_id:
        return []
    await asyncio.sleep(0.4)  # Jikan rate-limit: max 3 req/sec
    pics = await _get_json(
        f"https://api.jikan.moe/v4/anime/{mal_id}/pictures",
        headers={"User-Agent": "ThumbnailBot/1.0"},
    )
    if not isinstance(pics, dict):
        return []
    urls: list[str] = []
    for p in pics.get("data", []):
        u = p.get("jpg", {}).get("large_image_url") or p.get("jpg", {}).get("image_url", "")
        if u and u.startswith("http"):
            urls.append(u)
    return urls[:max_results]


# ── 8. Kitsu ──────────────────────────────────────────────────────────────────
async def fetch_kitsu(query: str, max_results: int = 5) -> list[str]:
    data = await _get_json(
        "https://kitsu.io/api/edge/anime",
        params={"filter[text]": query, "page[limit]": 5},
        headers={"Accept": "application/vnd.api+json"},
    )
    if not isinstance(data, dict):
        return []
    urls: list[str] = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        for key in ("coverImage", "posterImage"):
            img = attrs.get(key) or {}
            for size in ("large", "medium", "original"):
                u = img.get(size, "")
                if u and u.startswith("http"):
                    urls.append(u)
                    break
    return list(dict.fromkeys(urls))[:max_results]


# ── 9. Waifu.im ───────────────────────────────────────────────────────────────
async def fetch_waifu_im(query: str, max_results: int = 4) -> list[str]:
    """Waifu.im — anime character art. Uses general waifu tag."""
    data = await _get_json(
        "https://api.waifu.im/search",
        params={"many": "true", "included_tags": "waifu"},
    )
    if not isinstance(data, dict):
        return []
    return [
        img["url"] for img in data.get("images", [])
        if img.get("url", "").startswith("http")
    ][:max_results]


# ── 10. AniList character images ──────────────────────────────────────────────
async def fetch_anilist_images(query: str, max_results: int = 5) -> list[str]:
    gql = """
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        bannerImage
        coverImage { extraLarge large }
        characters(sort: FAVOURITES_DESC, perPage: 6) {
          nodes { image { large medium } }
        }
      }
    }
    """
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                "https://graphql.anilist.co",
                json={"query": gql, "variables": {"search": query}},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r:
                if r.status != 200:
                    return []
                resp = await r.json()
    except Exception as e:
        logger.debug("AniList images error: %s", e)
        return []
    media = resp.get("data", {}).get("Media") or {}
    urls: list[str] = []
    if media.get("bannerImage"):
        urls.append(media["bannerImage"])
    cov = media.get("coverImage", {})
    for k in ("extraLarge", "large"):
        if cov.get(k):
            urls.append(cov[k])
    for ch in (media.get("characters") or {}).get("nodes", []):
        u = ch.get("image", {}).get("large") or ch.get("image", {}).get("medium", "")
        if u:
            urls.append(u)
    return list(dict.fromkeys(urls))[:max_results]


# ── 11. Tbib ──────────────────────────────────────────────────────────────────
async def fetch_tbib(query: str, max_results: int = 5) -> list[str]:
    data = await _get_json(
        "https://tbib.org/index.php",
        params={"page": "dapi", "s": "post", "q": "index", "json": "1",
                "tags": _tag(query), "limit": max_results},
    )
    if not isinstance(data, list):
        return []
    return [
        u for p in data
        if (u := p.get("file_url") or p.get("sample_url", ""))
        and u.startswith("http") and not u.endswith(".webm")
    ][:max_results]


# ── 12. Lolibooru (safe) ──────────────────────────────────────────────────────
async def fetch_lolibooru(query: str, max_results: int = 4) -> list[str]:
    data = await _get_json(
        "https://lolibooru.moe/post.json",
        params={"tags": _tag(query) + " rating:safe", "limit": max_results},
    )
    if not isinstance(data, list):
        return []
    return [
        u for p in data
        if (u := p.get("sample_url") or p.get("file_url", ""))
        and u.startswith("http")
    ][:max_results]


# ── 13. Zerochan ──────────────────────────────────────────────────────────────
async def fetch_zerochan(query: str, max_results: int = 5) -> list[str]:
    slug = urllib.parse.quote_plus(query)
    data = await _get_json(
        f"https://www.zerochan.net/{slug}",
        params={"json": "1", "l": max_results, "s": "fav"},
    )
    if not isinstance(data, dict):
        return []
    urls: list[str] = []
    for item in data.get("items", []):
        u = item.get("large") or item.get("full") or item.get("src", "")
        if u and u.startswith("http"):
            urls.append(u)
    return urls[:max_results]


# ── 14. Anime-pictures.net ────────────────────────────────────────────────────
async def fetch_anime_pictures(query: str, max_results: int = 4) -> list[str]:
    slug = urllib.parse.quote_plus(query)
    data = await _get_json(
        f"https://anime-pictures.net/api/v3/posts",
        params={"search_tag": slug, "lang": "en", "page": 0, "posts_per_page": max_results},
    )
    if not isinstance(data, dict):
        return []
    urls: list[str] = []
    for p in data.get("posts", []):
        u = p.get("large_preview_url") or p.get("preview_url", "")
        if u:
            if u.startswith("/"):
                u = "https://anime-pictures.net" + u
            urls.append(u)
    return urls[:max_results]


# ── 15. Behoimi ───────────────────────────────────────────────────────────────
async def fetch_behoimi(query: str, max_results: int = 4) -> list[str]:
    data = await _get_json(
        "http://behoimi.org/post/index.json",
        params={"tags": _tag(query), "limit": max_results},
    )
    if not isinstance(data, list):
        return []
    return [
        u for p in data
        if (u := p.get("sample_url") or p.get("file_url", ""))
        and u.startswith("http")
    ][:max_results]


# ── 16. Nekos.best ────────────────────────────────────────────────────────────
async def fetch_nekos_best(query: str, max_results: int = 4) -> list[str]:
    """Nekos.best — anime images (uses general waifu category)."""
    data = await _get_json(
        "https://nekos.best/api/v2/neko",
        params={"amount": max_results},
    )
    if not isinstance(data, dict):
        return []
    return [
        r["url"] for r in data.get("results", [])
        if r.get("url", "").startswith("http")
    ][:max_results]


# ── 17. Hybooru ───────────────────────────────────────────────────────────────
async def fetch_hybooru(query: str, max_results: int = 4) -> list[str]:
    data = await _get_json(
        "https://hybooru.com/api/v1/posts/search",
        params={"query": query, "limit": max_results},
    )
    if not isinstance(data, dict):
        return []
    return [
        "https://hybooru.com" + p["hash_path"]
        for p in data.get("posts", [])
        if p.get("hash_path", "").startswith("/")
    ][:max_results]


# ── 18. Aniwatch poster scrape ────────────────────────────────────────────────
async def fetch_aniwatch(query: str, max_results: int = 3) -> list[str]:
    slug = urllib.parse.quote_plus(query)
    data = await _get_json(
        f"https://api.aniwatchtv.to/api/v2/hianime/search",
        params={"q": slug, "page": 1},
    )
    if not isinstance(data, dict):
        return []
    urls: list[str] = []
    for item in (data.get("data") or {}).get("animes", []):
        u = item.get("poster", "")
        if u and u.startswith("http"):
            urls.append(u)
    return urls[:max_results]


# ── 19. Pollinations.ai (AI-generated) ───────────────────────────────────────
async def fetch_pollinations(query: str, max_results: int = 2) -> list[str]:
    """
    Pollinations.ai — completely free AI image generation, no API key.
    Generates anime-style art from the anime title.
    """
    prompts = [
        f"{query} anime key visual, cinematic, CrunchyRoll style",
        f"{query} anime character official art, high quality",
    ]
    urls: list[str] = []
    for prompt in prompts[:max_results]:
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&seed={abs(hash(prompt)) % 9999}&nologo=true&model=flux"
        urls.append(url)
    return urls


# ── 20. Brave Search images ───────────────────────────────────────────────────
async def fetch_brave_search(query: str, max_results: int = 5) -> list[str]:
    """Brave Search image search (no key needed for basic HTML scrape)."""
    urls: list[str] = []
    try:
        async with aiohttp.ClientSession(headers=_BROWSER_HEADERS) as sess:
            async with sess.get(
                "https://search.brave.com/images",
                params={"q": f"{query} anime art", "source": "web"},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r:
                if r.status != 200:
                    return []
                text = await r.text()
        for m in re.finditer(r'"url"\s*:\s*"(https://[^"]+\.(?:jpg|jpeg|png|webp))"', text):
            u = m.group(1)
            if u not in urls:
                urls.append(u)
                if len(urls) >= max_results:
                    break
    except Exception as e:
        logger.debug("Brave search error: %s", e)
    return urls


# ── Main aggregator ───────────────────────────────────────────────────────────

_ALL_SOURCES = [
    fetch_safebooru,    # 1
    fetch_gelbooru,     # 4
    fetch_jikan,        # 7
    fetch_konachan,     # 2
    fetch_danbooru,     # 5
    fetch_kitsu,        # 8
    fetch_ddg_images,   # 3
    fetch_yandere,      # 6
    fetch_waifu_im,     # 9
    fetch_anilist_images, # 10
    fetch_tbib,         # 11
    fetch_lolibooru,    # 12
    fetch_zerochan,     # 13
    fetch_anime_pictures, # 14
    fetch_behoimi,      # 15
    fetch_nekos_best,   # 16
    fetch_hybooru,      # 17
    fetch_aniwatch,     # 18
    fetch_pollinations, # 19
    fetch_brave_search, # 20
]


async def fetch_all_extra(anime_title: str) -> list[str]:
    """
    Gather images from all 20 sources in parallel.
    Round-robin interleaves results so no source dominates
    and visually similar images from the same source aren't consecutive.
    """
    # Run all sources in parallel
    raw = await asyncio.gather(
        *[fn(anime_title) for fn in _ALL_SOURCES],
        return_exceptions=True,
    )

    batches: list[list[str]] = [
        b if isinstance(b, list) else []
        for b in raw
    ]

    counts = {fn.__name__: len(b) for fn, b in zip(_ALL_SOURCES, batches)}
    logger.info("Extra image counts for '%s': %s", anime_title, counts)

    # Round-robin interleave — 1 from each source in turn
    # so no block of similar images appears
    seen: set[str] = set()
    combined: list[str] = []
    max_len = max((len(b) for b in batches), default=0)
    for i in range(max_len):
        for batch in batches:
            if i < len(batch):
                url = batch[i]
                # Skip exact URL duplicates
                if url and url not in seen:
                    seen.add(url)
                    combined.append(url)

    logger.info("Total extra images for '%s': %d", anime_title, len(combined))
    return combined
