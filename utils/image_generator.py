"""
CrunchyRoll-style 1280x720 anime thumbnail generator.

Layout:
- Dark navy canvas (#0a0a18)
- Art panel: right side ~870px wide, portrait/landscape poster with color boost
- Left-to-right gradient: fully dark left side fading to transparent ~x=680
- Top nav bar (48px): logo + nav items + icons
- Left content zone (x=28..600): title (Bebas Neue), metadata, description,
  genres, language pill, Watch Now button, plus circle
- Season badge (top-left corner of art panel)
- Rating badge (bottom-right)
- Bottom-right Telegram branding
"""
import io
import os
import textwrap
import urllib.request
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

W, H    = 1280, 720
NAV_H   = 48
DARK    = (10, 10, 24)
RED     = (229, 9, 20)
ORANGE  = (255, 140, 0)
BLUE_TG = (41, 182, 246)
GOLD    = (255, 200, 50)

# ── System font search paths ──────────────────────────────────────────────────
_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
]
_REG = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
]

_FDIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_BEBAS  = os.path.join(_FDIR, "BebasNeue.ttf")
_BEBAS_URL = "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf"

_POPPINS_BOLD = os.path.join(_FDIR, "Poppins-Bold.ttf")
_POPPINS_REG  = os.path.join(_FDIR, "Poppins-Regular.ttf")
_POPPINS_BOLD_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf"
_POPPINS_REG_URL  = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf"


def _ensure_font(local_path: str, url: str) -> Optional[str]:
    os.makedirs(_FDIR, exist_ok=True)
    if os.path.exists(local_path):
        return local_path
    try:
        urllib.request.urlretrieve(url, local_path)
        return local_path
    except Exception:
        return None


def _f(paths: list, size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if p and os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _round_corners(img: Image.Image, radius: int) -> Image.Image:
    """Apply rounded corners mask to an RGBA image."""
    circle = Image.new("L", (radius * 2, radius * 2), 0)
    ImageDraw.Draw(circle).ellipse((0, 0, radius * 2 - 1, radius * 2 - 1), fill=255)
    alpha = Image.new("L", img.size, 255)
    w2, h2 = img.size
    alpha.paste(circle.crop((0, 0, radius, radius)), (0, 0))
    alpha.paste(circle.crop((0, radius, radius, radius * 2)), (0, h2 - radius))
    alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (w2 - radius, 0))
    alpha.paste(circle.crop((radius, radius, radius * 2, radius * 2)), (w2 - radius, h2 - radius))
    out = img.copy()
    out.putalpha(alpha)
    return out


def _draw_crunchyroll_logo(draw: ImageDraw.Draw, x: int, y: int, text: str, fbold) -> int:
    """Draw orange circle logo + channel name. Returns right-edge x."""
    r  = 14
    cx = x + r
    cy = y + r
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(*ORANGE, 255))
    fc = _f(_BOLD, 13)
    draw.text((cx - 5, cy - 8), "C", font=fc, fill=(255, 255, 255, 255))
    name_x = cx + r + 8
    draw.text((name_x, y + 2), text, font=fbold, fill=(255, 255, 255, 245))
    bb = draw.textbbox((name_x, y + 2), text, font=fbold)
    return bb[2]


def _draw_star_rating(draw: ImageDraw.Draw, x: int, y: int, rating: float, f_small):
    """Draw star rating indicator (out of 10)."""
    stars = round(rating / 2)
    star_str = "★" * stars + "☆" * (5 - stars)
    draw.text((x, y), star_str, font=f_small, fill=(*GOLD, 230))
    bb = draw.textbbox((x, y), star_str, font=f_small)
    score_x = bb[2] + 6
    draw.text((score_x, y), f"{rating:.1f}", font=f_small, fill=(200, 200, 200, 200))


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
    rating: float = 0.0,
) -> bytes:
    scale = max(1.0, min(scale, 3.0))

    # ── Ensure fonts are downloaded ───────────────────────────────────────────
    bebas        = _ensure_font(_BEBAS, _BEBAS_URL)
    poppins_bold = _ensure_font(_POPPINS_BOLD, _POPPINS_BOLD_URL)
    poppins_reg  = _ensure_font(_POPPINS_REG, _POPPINS_REG_URL)

    bold_paths = ([poppins_bold] if poppins_bold else []) + _BOLD
    reg_paths  = ([poppins_reg]  if poppins_reg  else []) + _REG

    # ── Canvas ────────────────────────────────────────────────────────────────
    canvas = Image.new("RGBA", (W, H), (*DARK, 255))

    # ── Art panel (right side, ~870px wide) ───────────────────────────────────
    PANEL_W, PANEL_H = 870, H
    ART_X = W - PANEL_W

    if art_bytes:
        try:
            art = Image.open(io.BytesIO(art_bytes)).convert("RGBA")
            aw, ah = art.size
            fit = max(PANEL_W / aw, PANEL_H / ah)
            sw  = int(aw * fit * scale)
            sh  = int(ah * fit * scale)
            art = art.resize((sw, sh), Image.LANCZOS)

            ox = max(0, min(offset_x, max(0, sw - PANEL_W)))
            oy = max(0, min(offset_y, max(0, sh - PANEL_H)))
            art = art.crop((ox, oy, ox + PANEL_W, oy + PANEL_H))

            # Slight saturation / contrast boost
            rgb = ImageEnhance.Color(art.convert("RGB")).enhance(1.25)
            rgb = ImageEnhance.Contrast(rgb).enhance(1.08)
            rgb = ImageEnhance.Brightness(rgb).enhance(1.02)
            canvas.paste(rgb.convert("RGBA"), (ART_X, 0), rgb.convert("RGBA"))
        except Exception:
            pass

    # ── Left-to-right dark gradient ───────────────────────────────────────────
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(grad)
    FADE_START = 380
    FADE_END   = 700
    for x in range(W):
        if x <= FADE_START:
            alpha = 255
        elif x <= FADE_END:
            t     = (x - FADE_START) / (FADE_END - FADE_START)
            alpha = int(255 * (1 - t ** 1.6))
        else:
            alpha = 0
        if alpha > 0:
            gd.line([(x, 0), (x, H)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas, grad)

    # ── Subtle top vignette (makes nav readable over bright art) ─────────────
    top_vig = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
    tvd = ImageDraw.Draw(top_vig)
    for y in range(120):
        a = int(160 * (1 - y / 120) ** 1.5)
        tvd.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    canvas.alpha_composite(top_vig, (0, 0))

    # ── Bottom vignette (grounds the content) ────────────────────────────────
    bot_vig = Image.new("RGBA", (W, 160), (0, 0, 0, 0))
    bvd = ImageDraw.Draw(bot_vig)
    for y in range(160):
        a = int(120 * (y / 160) ** 2)
        bvd.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    canvas.alpha_composite(bot_vig, (0, H - 160))

    draw = ImageDraw.Draw(canvas)

    # ── Nav bar (subtle dark strip) ───────────────────────────────────────────
    nav_bar = Image.new("RGBA", (W, NAV_H), (0, 0, 0, 160))
    canvas.alpha_composite(nav_bar, (0, 0))
    draw = ImageDraw.Draw(canvas)

    # ── Load fonts ────────────────────────────────────────────────────────────
    TITLE_SIZE_LG = 92
    TITLE_SIZE_MD = 76
    TITLE_SIZE_SM = 62

    if bebas:
        try:
            f_titl_lg = ImageFont.truetype(bebas, TITLE_SIZE_LG)
            f_titl_md = ImageFont.truetype(bebas, TITLE_SIZE_MD)
            f_titl_sm = ImageFont.truetype(bebas, TITLE_SIZE_SM)
        except Exception:
            f_titl_lg = _f(bold_paths, TITLE_SIZE_LG)
            f_titl_md = _f(bold_paths, TITLE_SIZE_MD)
            f_titl_sm = _f(bold_paths, TITLE_SIZE_SM)
    else:
        f_titl_lg = _f(bold_paths, TITLE_SIZE_LG)
        f_titl_md = _f(bold_paths, TITLE_SIZE_MD)
        f_titl_sm = _f(bold_paths, TITLE_SIZE_SM)

    LINE_H_LG = 96
    LINE_H_MD = 80
    LINE_H_SM = 66

    f_logo  = _f(bold_paths, 18)
    f_nav   = _f(reg_paths,  13)
    f_meta  = _f(bold_paths, 22)
    f_desc  = _f(reg_paths,  17)
    f_genre = _f(bold_paths, 24)
    f_btn   = _f(bold_paths, 21)
    f_pill  = _f(bold_paths, 17)
    f_brand = _f(bold_paths, 16)
    f_small = _f(reg_paths,  15)
    f_badge = _f(bold_paths, 18)

    # ── Logo + Channel name (nav left) ────────────────────────────────────────
    _draw_crunchyroll_logo(draw, 16, 10, channel_name, f_logo)

    # ── Nav items ─────────────────────────────────────────────────────────────
    nav_items = ["Home", "Movies", "Animes", "TV Shows", "My List"]
    nx = 300
    for item in nav_items:
        is_active = (item == "Animes")
        col = (*ORANGE, 255) if is_active else (210, 210, 210, 200)
        draw.text((nx, 17), item, font=f_nav, fill=col)
        bb = draw.textbbox((nx, 17), item, font=f_nav)
        iw = bb[2] - bb[0]
        if is_active:
            draw.line([(nx, NAV_H - 3), (nx + iw, NAV_H - 3)],
                      fill=(*ORANGE, 255), width=2)
        nx += iw + 32

    # Search / notification icons
    draw.text((W - 80, 17), "⌕  🔔  👤", font=f_nav, fill=(200, 200, 200, 190))

    # ── Title ─────────────────────────────────────────────────────────────────
    TX, TY = 28, NAV_H + 12
    title_up = title.upper()
    char_count = len(title_up)

    if char_count <= 14:
        f_title, wrap_w, line_h = f_titl_lg, 14, LINE_H_LG
    elif char_count <= 22:
        f_title, wrap_w, line_h = f_titl_md, 18, LINE_H_MD
    else:
        f_title, wrap_w, line_h = f_titl_sm, 22, LINE_H_SM

    lines = textwrap.wrap(title_up, width=wrap_w)[:3]
    for i, line in enumerate(lines):
        draw.text((TX, TY + i * line_h), line, font=f_title,
                  fill=(255, 255, 255, 255))

    cy = TY + len(lines) * line_h + 12

    # ── Thin orange accent line under title ───────────────────────────────────
    accent_w = min(300, len(title_up) * 8)
    draw.rectangle([(TX, cy), (TX + accent_w, cy + 3)], fill=(*ORANGE, 200))
    cy += 14

    # ── Metadata row ──────────────────────────────────────────────────────────
    meta_parts = []
    if year:
        meta_parts.append(year)
    meta_parts.append(f"{episodes} Eps")
    meta_parts.append(audio)
    meta = "  ·  ".join(meta_parts)
    draw.text((TX, cy), meta, font=f_meta, fill=(220, 220, 220, 230))
    cy += 34

    # ── Star rating (if available) ────────────────────────────────────────────
    if rating and rating > 0:
        _draw_star_rating(draw, TX, cy, rating, f_small)
        cy += 24

    cy += 4

    # ── Description (up to 4 lines, 50 chars wide) ────────────────────────────
    if description:
        desc_clean = description.replace("\n", " ").strip()
        for dl in textwrap.wrap(desc_clean, width=50)[:4]:
            draw.text((TX, cy), dl, font=f_desc, fill=(160, 160, 165, 210))
            cy += 24
        cy += 8

    # ── Genres ────────────────────────────────────────────────────────────────
    if genres:
        genre_str = "  ·  ".join(g.upper() for g in genres[:4])
        draw.text((TX, cy), genre_str, font=f_genre, fill=(255, 255, 255, 240))
        cy += 38

    cy += 6

    # ── Language pills ────────────────────────────────────────────────────────
    hindi_lbl = "✓ Hindi"
    hbb = draw.textbbox((0, 0), hindi_lbl, font=f_pill)
    hw  = hbb[2] - hbb[0] + 28
    hh  = hbb[3] - hbb[1] + 16
    pill_r = hh // 2

    # Dark filled pill for "Hindi"
    draw.rounded_rectangle(
        [(TX, cy), (TX + hw, cy + hh)],
        radius=pill_r, fill=(55, 55, 60, 240),
    )
    draw.text((TX + 14, cy + 8), hindi_lbl, font=f_pill,
              fill=(255, 255, 255, 255))

    # Outline-only pill for "Japanese"
    ja_lbl = "Japanese Original"
    jbb = draw.textbbox((0, 0), ja_lbl, font=f_pill)
    jw  = jbb[2] - jbb[0] + 24
    ja_x = TX + hw + 10
    draw.rounded_rectangle(
        [(ja_x, cy), (ja_x + jw, cy + hh)],
        radius=pill_r, outline=(90, 90, 95, 220), width=1,
    )
    draw.text((ja_x + 12, cy + 8), ja_lbl, font=f_pill,
              fill=(140, 140, 145, 220))

    cy += hh + 20

    # ── Watch Now button ──────────────────────────────────────────────────────
    s_label = f"S{season}"
    btn_txt = f"▶   Watch Now {s_label}"
    bbb = draw.textbbox((0, 0), btn_txt, font=f_btn)
    bw  = bbb[2] - bbb[0] + 48
    bh  = bbb[3] - bbb[1] + 22

    # Button shadow
    shadow = Image.new("RGBA", (bw + 6, bh + 6), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [(3, 3), (bw + 3, bh + 3)], radius=9, fill=(229, 9, 20, 100)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    canvas.alpha_composite(shadow, (TX - 1, cy - 1))
    draw = ImageDraw.Draw(canvas)

    draw.rounded_rectangle(
        [(TX, cy), (TX + bw, cy + bh)],
        radius=9, fill=(*RED, 255),
    )
    draw.text((TX + 22, cy + 11), btn_txt, font=f_btn,
              fill=(255, 255, 255, 255))

    # ── Plus / add circle ─────────────────────────────────────────────────────
    pcx = TX + bw + 16 + bh // 2
    pcy_top = cy
    draw.ellipse(
        [(pcx - bh // 2, pcy_top), (pcx + bh // 2, pcy_top + bh)],
        outline=(140, 140, 145, 200), width=2,
    )
    draw.text((pcx - 8, pcy_top + bh // 2 - 13), "+", font=f_btn,
              fill=(180, 180, 185, 220))

    # ── Season badge (top corner of art panel) ────────────────────────────────
    badge_txt = f"SEASON {season:02d}"
    bgt_bb    = draw.textbbox((0, 0), badge_txt, font=f_badge)
    bgw       = bgt_bb[2] - bgt_bb[0] + 24
    bgh       = bgt_bb[3] - bgt_bb[1] + 14

    badge_x = ART_X + 16
    badge_y = NAV_H + 16
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + bgw, badge_y + bgh)],
        radius=5, fill=(*ORANGE, 230),
    )
    draw.text((badge_x + 12, badge_y + 7), badge_txt, font=f_badge,
              fill=(255, 255, 255, 255))

    # ── Bottom-right Telegram branding ────────────────────────────────────────
    brand = channel_name
    brbb  = draw.textbbox((0, 0), brand, font=f_brand)
    brw   = brbb[2] - brbb[0]
    brh   = brbb[3] - brbb[1]
    tg_r  = 15

    total_brand_w = tg_r * 2 + 10 + brw
    bx = W - total_brand_w - 20
    by = H - tg_r * 2 - 18

    # Pill background behind branding
    pad_x, pad_y = 10, 6
    draw.rounded_rectangle(
        [(bx - pad_x, by - pad_y), (bx + total_brand_w + pad_x, by + tg_r * 2 + pad_y)],
        radius=tg_r, fill=(0, 0, 0, 140),
    )

    # Telegram circle
    draw.ellipse(
        [(bx, by), (bx + tg_r * 2, by + tg_r * 2)],
        fill=(*BLUE_TG, 255),
    )
    fp = _f(bold_paths, 14)
    draw.text((bx + 4, by + 2), "✈", font=fp, fill=(255, 255, 255, 255))

    # Channel name text
    draw.text(
        (bx + tg_r * 2 + 10, by + tg_r - brh // 2),
        brand, font=f_brand, fill=(230, 230, 230, 230),
    )

    # ── JPEG encode ───────────────────────────────────────────────────────────
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="JPEG", quality=96, optimize=True)
    buf.seek(0)
    return buf.read()


# ── Spoiler background ────────────────────────────────────────────────────────
def make_spoiler_bg(bg_bytes: bytes, channel: str) -> bytes:
    img   = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
    w, h  = img.size
    ratio = max(1280 / w, 720 / h)
    img   = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    img   = img.crop((0, 0, 1280, 720))

    # Blur + darken for spoiler effect
    img = img.filter(ImageFilter.GaussianBlur(radius=18))
    ov  = Image.new("RGBA", (1280, 720), (0, 0, 0, 100))
    img = Image.alpha_composite(img, ov)

    # Bottom gradient
    ov2  = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    ovd2 = ImageDraw.Draw(ov2)
    for y in range(720):
        if y > 500:
            t = (y - 500) / 220
            ovd2.line([(0, y), (1280, y)], fill=(0, 0, 0, int(210 * t)))
    img = Image.alpha_composite(img, ov2)

    draw = ImageDraw.Draw(img)
    _FDIR2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    _PB    = os.path.join(_FDIR2, "Poppins-Bold.ttf")
    f      = _f([_PB] + _BOLD, 30)

    text = f"@{channel}"
    tbb  = draw.textbbox((0, 0), text, font=f)
    tw   = tbb[2] - tbb[0]
    th   = tbb[3] - tbb[1]
    tx   = (1280 - tw) // 2
    ty   = 720 - th - 28

    pad = 16
    draw.rounded_rectangle(
        [(tx - pad, ty - pad // 2), (tx + tw + pad, ty + th + pad // 2)],
        radius=8, fill=(0, 0, 0, 185),
    )
    draw.text((tx, ty), text, font=f, fill=(255, 255, 255, 255))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf.read()
