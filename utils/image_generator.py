import io
import os
import textwrap
import urllib.request
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

OUTPUT_W, OUTPUT_H = 1280, 720
NAV_H   = 52
DARK_BG = (10, 10, 24)
ACCENT  = (229, 9, 20)

_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
_REG_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

_FONT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_BEBAS     = os.path.join(_FONT_DIR, "BebasNeue.ttf")
_BEBAS_URL = "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf"


def _ensure_bebas() -> Optional[str]:
    os.makedirs(_FONT_DIR, exist_ok=True)
    if os.path.exists(_BEBAS):
        return _BEBAS
    try:
        urllib.request.urlretrieve(_BEBAS_URL, _BEBAS)
        return _BEBAS
    except Exception:
        return None


def _font(paths: list[str], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


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

    canvas = Image.new("RGBA", (OUTPUT_W, OUTPUT_H), (*DARK_BG, 255))

    if art_bytes:
        art = Image.open(io.BytesIO(art_bytes)).convert("RGBA")
        aw, ah = art.size
        panel_w, panel_h = 860, OUTPUT_H
        fit = max(panel_w / aw, panel_h / ah)
        sw, sh = int(aw * fit * scale), int(ah * fit * scale)
        art = art.resize((sw, sh), Image.LANCZOS)
        ox = max(0, min(offset_x, max(0, sw - panel_w)))
        oy = max(0, min(offset_y, max(0, sh - panel_h)))
        art = art.crop((ox, oy, ox + panel_w, oy + panel_h))
        art_rgb = ImageEnhance.Color(art.convert("RGB")).enhance(1.15)
        art_rgb = ImageEnhance.Contrast(art_rgb).enhance(1.05)
        canvas.paste(art_rgb.convert("RGBA"), (OUTPUT_W - panel_w, 0),
                     art_rgb.convert("RGBA"))

    draw = ImageDraw.Draw(canvas)

    grad = Image.new("RGBA", (OUTPUT_W, OUTPUT_H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(grad)
    for x in range(OUTPUT_W):
        if x <= 480:
            alpha = 248
        elif x <= 800:
            t = (x - 480) / 320
            alpha = int(248 * (1 - t ** 0.5))
        else:
            alpha = 0
        if alpha > 0:
            gd.line([(x, 0), (x, OUTPUT_H)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas, grad)
    draw   = ImageDraw.Draw(canvas)

    draw.rectangle([(0, 0), (OUTPUT_W, NAV_H)], fill=(0, 0, 0, 215))
    draw.line([(0, NAV_H), (OUTPUT_W, NAV_H)], fill=(55, 55, 55, 200), width=1)

    bebas = _ensure_bebas()
    f_title_lg = ImageFont.truetype(bebas, 92) if bebas else _font(_BOLD_PATHS, 82)
    f_title_md = ImageFont.truetype(bebas, 74) if bebas else _font(_BOLD_PATHS, 66)
    f_logo  = _font(_BOLD_PATHS, 21)
    f_nav   = _font(_REG_PATHS,  15)
    f_meta  = _font(_REG_PATHS,  25)
    f_desc  = _font(_REG_PATHS,  19)
    f_genre = _font(_BOLD_PATHS, 27)
    f_btn   = _font(_BOLD_PATHS, 22)
    f_pill  = _font(_BOLD_PATHS, 18)
    f_brand = _font(_BOLD_PATHS, 17)

    draw.ellipse([(16, 11), (44, 40)], fill=(255, 140, 0, 255))
    draw.text((50, 14), channel_name[:18], font=f_logo, fill=(255, 140, 0, 255))

    nav_x = 310
    for item in ["Home", "Movies", "Animes", "TV Shows", "My List"]:
        col = (255, 140, 0, 255) if item == "Animes" else (200, 200, 200, 210)
        draw.text((nav_x, 18), item, font=f_nav, fill=col)
        bb = draw.textbbox((nav_x, 18), item, font=f_nav)
        if item == "Animes":
            draw.line([(nav_x, NAV_H - 3), (bb[2], NAV_H - 3)],
                      fill=(255, 140, 0, 255), width=2)
        nav_x += (bb[2] - bb[0]) + 32

    tx, ty  = 40, NAV_H + 20
    title_up = title.upper()
    f_title  = f_title_lg if len(title_up) <= 20 else f_title_md
    line_h   = 100 if f_title == f_title_lg else 82
    lines    = textwrap.wrap(title_up, width=18)[:3]

    for i, line in enumerate(lines):
        ly = ty + i * line_h
        draw.text((tx + 3, ly + 3), line, font=f_title, fill=(0, 0, 0, 120))
        draw.text((tx,     ly),     line, font=f_title, fill=(255, 255, 255, 255))

    cy = ty + len(lines) * line_h + 12

    meta = f"{year}  •  {episodes} Episodes  •  {audio}"
    draw.text((tx, cy), meta, font=f_meta, fill=(165, 165, 165, 230))
    cy += 38

    if description:
        for dl in textwrap.wrap(description, width=50)[:4]:
            draw.text((tx, cy), dl, font=f_desc, fill=(145, 145, 145, 210))
            cy += 26
        cy += 6

    genre_str = "  |  ".join(genres[:4])
    if genre_str:
        draw.text((tx, cy), genre_str, font=f_genre, fill=(255, 255, 255, 255))
        cy += 44

    cy += 8

    hindi = "✓ Hindi"
    hbb = draw.textbbox((0, 0), hindi, font=f_pill)
    hw, hh = hbb[2] - hbb[0] + 24, hbb[3] - hbb[1] + 14
    draw.rounded_rectangle([(tx, cy), (tx + hw, cy + hh)],
                           radius=hh // 2, fill=(50, 50, 50, 230))
    draw.text((tx + 12, cy + 7), hindi, font=f_pill, fill=(255, 255, 255, 255))
    draw.text((tx + hw + 18, cy + 7), "Japanese Original",
              font=f_pill, fill=(125, 125, 125, 200))
    cy += hh + 18

    btn = f"▶  Watch Now S{season:02d}"
    bbb = draw.textbbox((0, 0), btn, font=f_btn)
    bw, bh = bbb[2] - bbb[0] + 40, bbb[3] - bbb[1] + 22
    draw.rounded_rectangle([(tx, cy), (tx + bw, cy + bh)], radius=7,
                           fill=(*ACCENT, 255))
    draw.text((tx + 20, cy + 11), btn, font=f_btn, fill=(255, 255, 255, 255))

    pcx = tx + bw + 18 + bh // 2
    draw.ellipse([(pcx - bh // 2, cy), (pcx + bh // 2, cy + bh)],
                 outline=(140, 140, 140, 200), width=2)
    draw.text((pcx - 8, cy + 9), "+", font=f_btn, fill=(185, 185, 185, 220))

    brand = f"t.me/{channel_name}"
    brbb  = draw.textbbox((0, 0), brand, font=f_brand)
    brw   = brbb[2] - brbb[0]
    tcx, tcy = OUTPUT_W - brw - 52, OUTPUT_H - 22
    draw.ellipse([(tcx - 15, tcy - 15), (tcx + 15, tcy + 15)],
                 fill=(41, 182, 246, 255))
    draw.text((tcx - 5, tcy - 9), "✈", font=_font(_BOLD_PATHS, 14),
              fill=(255, 255, 255, 255))
    draw.text((tcx + 20, tcy - 9), brand, font=f_brand,
              fill=(215, 215, 215, 210))

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="JPEG", quality=95, optimize=True)
    buf.seek(0)
    return buf.read()


def make_spoiler_bg(bg_bytes: bytes, channel: str) -> bytes:
    img = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
    w, h = img.size
    ratio = max(1280 / w, 720 / h)
    img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    img = img.crop((0, 0, 1280, 720))

    overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    odraw   = ImageDraw.Draw(overlay)
    for y in range(720):
        if y > 560:
            t = (y - 560) / 160
            odraw.line([(0, y), (1280, y)], fill=(0, 0, 0, int(190 * t)))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    f    = _font(_BOLD_PATHS, 30)
    text = f"@{channel}"
    tbb  = draw.textbbox((0, 0), text, font=f)
    tw, th = tbb[2] - tbb[0], tbb[3] - tbb[1]
    tx = (1280 - tw) // 2
    ty = 720 - th - 22
    pad = 14
    draw.rounded_rectangle(
        [(tx - pad, ty - pad // 2), (tx + tw + pad, ty + th + pad // 2)],
        radius=6, fill=(0, 0, 0, 175),
    )
    draw.text((tx, ty), text, font=f, fill=(255, 255, 255, 255))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf.read()
