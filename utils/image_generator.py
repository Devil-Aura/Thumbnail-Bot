"""
CrunchyRoll-style 1280×720 anime thumbnail generator.

Reference image analysis:
- Canvas: 1280 × 720, dark navy bg (#0a0a18)
- Nav bar: y=0..48, nearly transparent dark overlay
- Logo: orange filled circle (28px) + "CrunchyRollChannel" white 20px bold
- Nav items: white 14px, "Animes" orange with 2px orange underline
- Title: Bebas Neue ~90px, pure white, NO shadow, tight 94px line-height
- Metadata: "{year} • {n} Episodes • {audio}"  white 26px
- Description: gray ~19px, 4 lines max, 48-char wrap
- Genres: "Drama | Fantasy | Romance"  white 28px slightly heavier
- Language pill: dark #333 rounded, "✓ Hindi" white 18px bold
             + "Japanese Original" gray 18px
- Watch button: red #e50914 rounded-8, "▶  Watch Now S{n}" white 22px bold
- Plus circle: 48px, gray outline 2px, "+" white 22px
- Branding BR: Telegram blue circle 28px + "CrunchyRollChannel" white 17px
- Art panel: right side, portrait poster scaled to fill ~860×720,
             blended with hard-dark gradient from x=0 (alpha=252) fading
             to transparent at x≈680
"""
import io
import os
import textwrap
import urllib.request
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

W, H = 1280, 720
NAV_H  = 48
DARK   = (10, 10, 24)
RED    = (229, 9, 20)
ORANGE = (255, 140, 0)
BLUE_TG = (41, 182, 246)

_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
_REG = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

_FDIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_BEBAS = os.path.join(_FDIR, "BebasNeue.ttf")
_BEBAS_URL = "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf"


def _ensure_bebas() -> Optional[str]:
    os.makedirs(_FDIR, exist_ok=True)
    if os.path.exists(_BEBAS):
        return _BEBAS
    try:
        urllib.request.urlretrieve(_BEBAS_URL, _BEBAS)
        return _BEBAS
    except Exception:
        return None


def _f(paths: list, size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _draw_crunchyroll_logo(draw: ImageDraw.Draw, x: int, y: int, text: str, fbold) -> int:
    """Draw orange circle logo + channel name. Returns right-edge x."""
    r = 14
    cx, cy = x + r, y + r
    # Filled orange circle
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(*ORANGE, 255))
    # White "C" text inside
    fc = _f(_BOLD, 13)
    draw.text((cx - 5, cy - 8), "C", font=fc, fill=(255, 255, 255, 255))
    # Channel name
    name_x = cx + r + 8
    draw.text((name_x, y + 2), text, font=fbold, fill=(255, 255, 255, 245))
    bb = draw.textbbox((name_x, y + 2), text, font=fbold)
    return bb[2]


def make_anime_thumbnail(
    art_bytes: Optional[bytes],
    title: str,
    year: str,
    episodes: int,
    audio: str,
    description: str,
    genres: list[str],
    season: int,
    channel_name: str = "AnimeChannel",
    offset_x: int = 0,
    offset_y: int = 0,
    scale: float = 1.0,
) -> bytes:
    scale = max(1.0, min(scale, 3.0))

    # ── Canvas ────────────────────────────────────────────────────────────────
    canvas = Image.new("RGBA", (W, H), (*DARK, 255))

    # ── Art (right panel) ─────────────────────────────────────────────────────
    if art_bytes:
        art = Image.open(io.BytesIO(art_bytes)).convert("RGBA")
        aw, ah = art.size
        PANEL_W, PANEL_H = 870, H
        fit = max(PANEL_W / aw, PANEL_H / ah)
        sw, sh = int(aw * fit * scale), int(ah * fit * scale)
        art = art.resize((sw, sh), Image.LANCZOS)
        ox = max(0, min(offset_x, max(0, sw - PANEL_W)))
        oy = max(0, min(offset_y, max(0, sh - PANEL_H)))
        art = art.crop((ox, oy, ox + PANEL_W, oy + PANEL_H))

        # Slight saturation / contrast boost to make it pop
        rgb = ImageEnhance.Color(art.convert("RGB")).enhance(1.2)
        rgb = ImageEnhance.Contrast(rgb).enhance(1.05)
        canvas.paste(rgb.convert("RGBA"), (W - PANEL_W, 0), rgb.convert("RGBA"))

    # ── Dark gradient (left → right) ──────────────────────────────────────────
    # Reference: pure black at x=0, fading to 0 around x=680
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(grad)
    FADE_START = 360
    FADE_END   = 680
    for x in range(W):
        if x <= FADE_START:
            alpha = 252
        elif x <= FADE_END:
            t = (x - FADE_START) / (FADE_END - FADE_START)
            # Quadratic ease-out: dark holds longer then drops quickly
            alpha = int(252 * (1 - t ** 1.8))
        else:
            alpha = 0
        if alpha > 0:
            gd.line([(x, 0), (x, H)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas, grad)
    draw   = ImageDraw.Draw(canvas)

    # ── Nav bar (subtle dark strip) ───────────────────────────────────────────
    nav_bar = Image.new("RGBA", (W, NAV_H), (0, 0, 0, 185))
    canvas.alpha_composite(nav_bar, (0, 0))
    draw = ImageDraw.Draw(canvas)

    # ── Load fonts ────────────────────────────────────────────────────────────
    bebas = _ensure_bebas()
    # Title font sizes tuned to reference
    TITLE_SIZE_LG = 90   # ≤ 18 chars per line
    TITLE_SIZE_MD = 74   # longer titles
    f_titl_lg = ImageFont.truetype(bebas, TITLE_SIZE_LG) if bebas else _f(_BOLD, 80)
    f_titl_md = ImageFont.truetype(bebas, TITLE_SIZE_MD) if bebas else _f(_BOLD, 66)
    LINE_H_LG = 94
    LINE_H_MD = 78

    f_logo  = _f(_BOLD, 19)
    f_nav   = _f(_REG,  14)
    f_meta  = _f(_BOLD, 26)   # reference uses slightly heavier for metadata
    f_desc  = _f(_REG,  18)
    f_genre = _f(_BOLD, 28)
    f_btn   = _f(_BOLD, 22)
    f_pill  = _f(_BOLD, 18)
    f_brand = _f(_BOLD, 17)

    # ── Logo + Channel name ───────────────────────────────────────────────────
    _draw_crunchyroll_logo(draw, 16, 10, channel_name, f_logo)

    # ── Nav items ─────────────────────────────────────────────────────────────
    nav_items = ["Home", "Movies", "Animes", "TV Shows", "My List"]
    nx = 290
    for item in nav_items:
        is_active = item == "Animes"
        col = (*ORANGE, 255) if is_active else (210, 210, 210, 210)
        draw.text((nx, 16), item, font=f_nav, fill=col)
        bb = draw.textbbox((nx, 16), item, font=f_nav)
        iw = bb[2] - bb[0]
        if is_active:
            draw.line([(nx, NAV_H - 4), (nx + iw, NAV_H - 4)],
                      fill=(*ORANGE, 255), width=2)
        nx += iw + 30

    # Search/bell icons
    draw.text((W - 72, 16), "⌕  🔔  👤", font=f_nav, fill=(200, 200, 200, 200))

    # ── Title ─────────────────────────────────────────────────────────────────
    TX, TY = 28, NAV_H + 10
    title_up = title.upper()
    # Determine font and wrap width
    if len(title_up) <= 18:
        f_title, wrap_w, line_h = f_titl_lg, 17, LINE_H_LG
    else:
        f_title, wrap_w, line_h = f_titl_md, 20, LINE_H_MD

    lines = textwrap.wrap(title_up, width=wrap_w)[:3]
    for i, line in enumerate(lines):
        draw.text((TX, TY + i * line_h), line, font=f_title,
                  fill=(255, 255, 255, 255))

    cy = TY + len(lines) * line_h + 10

    # ── Metadata ──────────────────────────────────────────────────────────────
    meta = f"{year}  •  {episodes} Episodes  •  {audio}"
    draw.text((TX, cy), meta, font=f_meta, fill=(235, 235, 235, 240))
    cy += 38

    # ── Description ───────────────────────────────────────────────────────────
    if description:
        for dl in textwrap.wrap(description, width=48)[:4]:
            draw.text((TX, cy), dl, font=f_desc, fill=(170, 170, 170, 220))
            cy += 25
        cy += 6

    # ── Genres ────────────────────────────────────────────────────────────────
    genre_str = "  |  ".join(genres[:4])
    if genre_str:
        draw.text((TX, cy), genre_str, font=f_genre, fill=(255, 255, 255, 255))
        cy += 44

    cy += 8

    # ── Language pills ────────────────────────────────────────────────────────
    hindi = "✓ Hindi"
    hbb = draw.textbbox((0, 0), hindi, font=f_pill)
    hw, hh = hbb[2] - hbb[0] + 26, hbb[3] - hbb[1] + 14
    # Dark pill
    draw.rounded_rectangle([(TX, cy), (TX + hw, cy + hh)],
                           radius=hh // 2, fill=(50, 50, 50, 235))
    draw.text((TX + 13, cy + 7), hindi, font=f_pill, fill=(255, 255, 255, 255))
    draw.text((TX + hw + 16, cy + 7), "Japanese Original",
              font=f_pill, fill=(120, 120, 120, 210))
    cy += hh + 18

    # ── Watch Now button ──────────────────────────────────────────────────────
    # Season WITHOUT leading zero for single digits (matches reference "S1" not "S01")
    s_label = f"S{season}"
    btn_txt  = f"▶   Watch Now {s_label}"
    bbb = draw.textbbox((0, 0), btn_txt, font=f_btn)
    bw, bh = bbb[2] - bbb[0] + 44, bbb[3] - bbb[1] + 24
    draw.rounded_rectangle([(TX, cy), (TX + bw, cy + bh)],
                           radius=8, fill=(*RED, 255))
    draw.text((TX + 20, cy + 12), btn_txt, font=f_btn,
              fill=(255, 255, 255, 255))

    # ── Plus circle ───────────────────────────────────────────────────────────
    pcx = TX + bw + 18 + bh // 2
    draw.ellipse([(pcx - bh // 2, cy), (pcx + bh // 2, cy + bh)],
                 outline=(160, 160, 160, 200), width=2)
    draw.text((pcx - 9, cy + bh // 2 - 14), "+", font=f_btn,
              fill=(200, 200, 200, 230))

    # ── Bottom-right branding ─────────────────────────────────────────────────
    brand   = channel_name
    brbb    = draw.textbbox((0, 0), brand, font=f_brand)
    brw     = brbb[2] - brbb[0]
    brh     = brbb[3] - brbb[1]
    tg_r    = 16
    total_w = tg_r * 2 + 10 + brw
    bx      = W - total_w - 18
    by      = H - tg_r * 2 - 16

    # Telegram circle
    draw.ellipse([(bx, by), (bx + tg_r * 2, by + tg_r * 2)],
                 fill=(*BLUE_TG, 255))
    # Paper-plane glyph
    fp = _f(_BOLD, 15)
    draw.text((bx + 4, by + 3), "✈", font=fp, fill=(255, 255, 255, 255))

    # Channel name
    draw.text((bx + tg_r * 2 + 10, by + tg_r - brh // 2),
              brand, font=f_brand, fill=(230, 230, 230, 220))

    # ── Encode ────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="JPEG", quality=95, optimize=True)
    buf.seek(0)
    return buf.read()


# ── Spoiler background ────────────────────────────────────────────────────────
def make_spoiler_bg(bg_bytes: bytes, channel: str) -> bytes:
    img = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
    w, h = img.size
    ratio = max(1280 / w, 720 / h)
    img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    img = img.crop((0, 0, 1280, 720))

    # Dark bottom gradient
    ov  = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    ovd = ImageDraw.Draw(ov)
    for y in range(720):
        if y > 540:
            t = (y - 540) / 180
            ovd.line([(0, y), (1280, y)], fill=(0, 0, 0, int(200 * t)))
    img = Image.alpha_composite(img, ov)

    draw = ImageDraw.Draw(img)
    f    = _f(_BOLD, 30)
    text = f"@{channel}"
    tbb  = draw.textbbox((0, 0), text, font=f)
    tw, th = tbb[2] - tbb[0], tbb[3] - tbb[1]
    tx = (1280 - tw) // 2
    ty = 720 - th - 22

    # Pill behind text
    pad = 14
    draw.rounded_rectangle(
        [(tx - pad, ty - pad // 2), (tx + tw + pad, ty + th + pad // 2)],
        radius=6, fill=(0, 0, 0, 180),
    )
    draw.text((tx, ty), text, font=f, fill=(255, 255, 255, 255))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf.read()
