import io
import os
import textwrap
import urllib.request
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

OUTPUT_W, OUTPUT_H = 1280, 720
NAV_H   = 52
DARK_BG = (10, 10, 24)
ACCENT  = (229, 9, 20)   # crunchyroll red

# ── Font paths ─────────────────────────────────────────────────────────────────
_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
]
_REG_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]

_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_BEBAS    = os.path.join(_FONT_DIR, "BebasNeue.ttf")
_BEBAS_URL = (
    "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf"
)


def _ensure_bebas() -> Optional[str]:
    os.makedirs(_FONT_DIR, exist_ok=True)
    if os.path.exists(_BEBAS):
        return _BEBAS
    try:
        urllib.request.urlretrieve(_BEBAS_URL, _BEBAS)
        return _BEBAS
    except Exception:
        return None


def _font(paths: list[str], size: int, bold_fallback: bool = False) -> ImageFont.FreeTypeFont:
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _draw_gradient_rect(draw: ImageDraw.Draw, x0, y0, x1, y1, color_rgb, alpha_start, alpha_end, vertical=True):
    steps = (y1 - y0) if vertical else (x1 - x0)
    for i in range(steps):
        t = i / max(steps, 1)
        alpha = int(alpha_start + (alpha_end - alpha_start) * (t ** 1.4))
        alpha = max(0, min(255, alpha))
        if vertical:
            draw.line([(x0, y0 + i), (x1, y0 + i)], fill=(*color_rgb, alpha))
        else:
            draw.line([(x0 + i, y0), (x0 + i, y1)], fill=(*color_rgb, alpha))


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

    # ── Canvas ─────────────────────────────────────────────────────────────────
    canvas = Image.new("RGBA", (OUTPUT_W, OUTPUT_H), (*DARK_BG, 255))

    # ── Art (right panel) ──────────────────────────────────────────────────────
    if art_bytes:
        art = Image.open(io.BytesIO(art_bytes)).convert("RGBA")
        art_w, art_h = art.size

        # Scale so art fills right panel (≈ 820 × 720); honour user scale
        panel_w, panel_h = 860, OUTPUT_H
        fit = max(panel_w / art_w, panel_h / art_h)
        sw = int(art_w * fit * scale)
        sh = int(art_h * fit * scale)
        art = art.resize((sw, sh), Image.LANCZOS)

        ox = max(0, min(offset_x, max(0, sw - panel_w)))
        oy = max(0, min(offset_y, max(0, sh - panel_h)))
        art = art.crop((ox, oy, ox + panel_w, oy + panel_h))

        # Slight colour pop
        art_rgb = art.convert("RGB")
        art_rgb = ImageEnhance.Color(art_rgb).enhance(1.15)
        art_rgb = ImageEnhance.Contrast(art_rgb).enhance(1.05)
        art = art_rgb.convert("RGBA")

        canvas.paste(art, (OUTPUT_W - panel_w, 0), art)

    draw = ImageDraw.Draw(canvas)

    # ── Left gradient overlay ──────────────────────────────────────────────────
    grad = Image.new("RGBA", (OUTPUT_W, OUTPUT_H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(grad)
    for x in range(OUTPUT_W):
        if x <= 480:
            alpha = 248
        elif x <= 780:
            t = (x - 480) / 300
            alpha = int(248 * (1 - t ** 0.55))
        else:
            alpha = 0
        if alpha > 0:
            gd.line([(x, 0), (x, OUTPUT_H)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas, grad)
    draw   = ImageDraw.Draw(canvas)

    # ── Top nav bar ────────────────────────────────────────────────────────────
    draw.rectangle([(0, 0), (OUTPUT_W, NAV_H)], fill=(0, 0, 0, 210))
    draw.line([(0, NAV_H), (OUTPUT_W, NAV_H)], fill=(60, 60, 60, 200), width=1)

    # ── Fonts ──────────────────────────────────────────────────────────────────
    bebas_path = _ensure_bebas()
    if bebas_path:
        f_title_big = ImageFont.truetype(bebas_path, 88)
        f_title_med = ImageFont.truetype(bebas_path, 72)
    else:
        f_title_big = _font(_BOLD_PATHS, 80)
        f_title_med = _font(_BOLD_PATHS, 66)

    f_logo  = _font(_BOLD_PATHS, 21)
    f_nav   = _font(_REG_PATHS,  15)
    f_meta  = _font(_REG_PATHS,  25)
    f_desc  = _font(_REG_PATHS,  19)
    f_genre = _font(_BOLD_PATHS, 27)
    f_btn   = _font(_BOLD_PATHS, 22)
    f_pill  = _font(_BOLD_PATHS, 18)
    f_brand = _font(_BOLD_PATHS, 17)

    # ── Channel logo (top-left) ────────────────────────────────────────────────
    # Orange circle icon
    draw.ellipse([(18, 12), (44, 38)], fill=(255, 140, 0, 255))
    draw.text((20, 13), channel_name[:14], font=f_logo, fill=(255, 140, 0, 255))

    # Nav items
    nav_items  = ["Home", "Movies", "Animes", "TV Shows", "My List"]
    active_nav = "Animes"
    nx = 300
    for item in nav_items:
        color = (255, 140, 0, 255) if item == active_nav else (200, 200, 200, 210)
        draw.text((nx, 18), item, font=f_nav, fill=color)
        bb = draw.textbbox((nx, 18), item, font=f_nav)
        if item == active_nav:
            draw.line([(nx, NAV_H - 3), (bb[2], NAV_H - 3)], fill=(255, 140, 0, 255), width=2)
        nx += (bb[2] - bb[0]) + 32

    # Search / bell icons (simplified)
    for ix, icon in enumerate(["⌕", "🔔", "👤"]):
        draw.text((OUTPUT_W - 100 + ix * 30, 16), icon, font=f_nav, fill=(200, 200, 200, 200))

    # ── Title ──────────────────────────────────────────────────────────────────
    tx = 40
    ty = NAV_H + 22

    title_upper = title.upper()
    # Choose font size based on title length
    f_title = f_title_big if len(title_upper) <= 20 else f_title_med
    line_h  = 96 if f_title == f_title_big else 80
    lines   = textwrap.wrap(title_upper, width=18)[:3]

    for i, line in enumerate(lines):
        ly = ty + i * line_h
        # Subtle shadow
        draw.text((tx + 3, ly + 3), line, font=f_title, fill=(0, 0, 0, 130))
        draw.text((tx,     ly),     line, font=f_title, fill=(255, 255, 255, 255))

    cy = ty + len(lines) * line_h + 14

    # ── Metadata row ───────────────────────────────────────────────────────────
    meta = f"{year}  •  {episodes} Episodes  •  {audio}"
    draw.text((tx, cy), meta, font=f_meta, fill=(170, 170, 170, 230))
    cy += 38

    # ── Description ────────────────────────────────────────────────────────────
    if description:
        desc_wrapped = textwrap.wrap(description, width=50)[:4]
        for dl in desc_wrapped:
            draw.text((tx, cy), dl, font=f_desc, fill=(150, 150, 150, 215))
            cy += 26
        cy += 6

    # ── Genres ─────────────────────────────────────────────────────────────────
    genre_str = "  |  ".join(g for g in genres[:4]) if genres else ""
    if genre_str:
        draw.text((tx, cy), genre_str, font=f_genre, fill=(255, 255, 255, 255))
        cy += 44

    cy += 10

    # ── Language pills ─────────────────────────────────────────────────────────
    hindi_text = "✓ Hindi"
    hbb = draw.textbbox((0, 0), hindi_text, font=f_pill)
    hw, hh = hbb[2] - hbb[0] + 24, hbb[3] - hbb[1] + 14
    draw.rounded_rectangle([(tx, cy), (tx + hw, cy + hh)], radius=hh // 2, fill=(50, 50, 50, 230))
    draw.text((tx + 12, cy + 7), hindi_text, font=f_pill, fill=(255, 255, 255, 255))

    draw.text((tx + hw + 20, cy + 7), "Japanese Original", font=f_pill, fill=(130, 130, 130, 200))
    cy += hh + 20

    # ── Watch Now button ───────────────────────────────────────────────────────
    btn_txt = f"▶  Watch Now S{season:02d}"
    bbb     = draw.textbbox((0, 0), btn_txt, font=f_btn)
    bw, bh  = bbb[2] - bbb[0] + 40, bbb[3] - bbb[1] + 22

    draw.rounded_rectangle([(tx, cy), (tx + bw, cy + bh)], radius=7, fill=(*ACCENT, 255))
    draw.text((tx + 20, cy + 11), btn_txt, font=f_btn, fill=(255, 255, 255, 255))

    # "+" circle
    cx_plus = tx + bw + 18 + bh // 2
    draw.ellipse([(cx_plus - bh//2, cy), (cx_plus + bh//2, cy + bh)],
                 outline=(140, 140, 140, 200), width=2)
    draw.text((cx_plus - 9, cy + 8), "+", font=f_btn, fill=(190, 190, 190, 220))

    # ── Bottom-right branding ──────────────────────────────────────────────────
    brand_txt = f"t.me/{channel_name}"
    brtb = draw.textbbox((0, 0), brand_txt, font=f_brand)
    brw  = brtb[2] - brtb[0]

    # Telegram blue circle
    tcx, tcy = OUTPUT_W - brw - 50, OUTPUT_H - 22
    draw.ellipse([(tcx - 15, tcy - 15), (tcx + 15, tcy + 15)], fill=(41, 182, 246, 255))
    draw.text((tcx - 5, tcy - 9), "✈", font=_font(_BOLD_PATHS, 14), fill=(255, 255, 255, 255))

    draw.text((tcx + 20, tcy - 9), brand_txt, font=f_brand, fill=(220, 220, 220, 210))

    # ── Encode ─────────────────────────────────────────────────────────────────
    final = canvas.convert("RGB")
    buf   = io.BytesIO()
    final.save(buf, format="JPEG", quality=95, optimize=True)
    buf.seek(0)
    return buf.read()
