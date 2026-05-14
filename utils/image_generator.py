"""
CrunchyRoll-style 1280x720 anime thumbnail — cinematic composition.

Layout (exact):
  Left text zone : 0–563 px  (44% of 1280)
  Right art zone : 563–1280 px (56%)

  Title    : x=40, y=100, max_width=500, Bebas Neue 88/76 px, stroke=4
  Metadata : y = title_bottom + 20
  Desc     : 22px, rgb(220,220,220), line_spacing=34, max_width=520
  Genres   : y = desc_bottom + 20
  Language : y = genres_bottom + 40
  Watch btn: y = lang_bottom + 50, height=72px, radius=18, orange-red gradient

  Art      : fit to 650x720 (narrower), placed at x = WIDTH - art_w + 80
  Gradient : 720px wide, left=255 → right=0, GaussianBlur(25)
  Shadow   : center strip x=500, width=120, peak opacity=110
  Glow     : amber ellipse (800,100,1200,650), GaussianBlur(100), alpha=45
  Grading  : Contrast=1.18, Color=1.12, Sharpness=1.25
  Export   : quality=95, optimize=True
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
ORANGE  = (255, 140, 0)
AMBER   = (255, 120, 20)
BLUE_TG = (41, 182, 246)

TEXT_ZONE = 563   # left 44% boundary

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
_BEBAS_URLS = [
    "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf",
    "https://github.com/dharmatype/Bebas-Neue/raw/master/Fonts/BNInstallFonts/BebasNeue-Regular.ttf",
]


def _ensure_bebas() -> Optional[str]:
    os.makedirs(_FDIR, exist_ok=True)
    if os.path.exists(_BEBAS) and os.path.getsize(_BEBAS) > 10_000:
        return _BEBAS
    for url in _BEBAS_URLS:
        try:
            urllib.request.urlretrieve(url, _BEBAS)
            if os.path.getsize(_BEBAS) > 10_000:
                return _BEBAS
        except Exception:
            continue
    return None


def _f(paths: list, size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _draw_logo(draw: ImageDraw.Draw, x: int, y: int, text: str, fbold) -> int:
    r = 14
    cx, cy = x + r, y + r
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(*ORANGE, 255))
    fc = _f(_BOLD, 13)
    draw.text((cx - 5, cy - 8), "C", font=fc, fill=(255, 255, 255, 255))
    nx = cx + r + 8
    draw.text((nx, y + 2), text, font=fbold, fill=(255, 255, 255, 245))
    bb = draw.textbbox((nx, y + 2), text, font=fbold)
    return bb[2]


def _wrap_to_width(draw: ImageDraw.Draw, text: str, font, max_px: int) -> list:
    """Word-wrap text to fit within max_px pixels wide. Returns lines (max 3)."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_px:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]


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

    # ── Art panel: narrower render (650×720), placed on RIGHT with overflow ───
    if art_bytes:
        art = Image.open(io.BytesIO(art_bytes)).convert("RGBA")
        aw, ah = art.size
        # Fit to 650 wide × 720 tall (narrower, cleaner silhouette)
        fit = max(650 / aw, H / ah) * scale
        sw, sh = int(aw * fit), int(ah * fit)
        art = art.resize((sw, sh), Image.LANCZOS)
        # Overflow from right edge: char_x = W - sw + 80
        char_x = W - sw + 80 + offset_x
        char_x = min(char_x, W - 80)   # keep at least 80px visible
        oy = max(0, min(offset_y, max(0, sh - H)))
        art_crop = art.crop((0, oy, sw, oy + H))
        canvas.paste(art_crop, (char_x, 0), art_crop)

    # ── Atmospheric amber/orange glow behind character ────────────────────────
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([(800, 100), (1200, 650)], fill=(*AMBER, 45))
    glow = glow.filter(ImageFilter.GaussianBlur(100))
    canvas = Image.alpha_composite(canvas, glow)

    # ── Cinematic heavy gradient: left=black/255 → center fades → transparent ─
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(grad)
    for x in range(W):
        if x < 720:
            t     = x / 720
            alpha = int(255 * (1.0 - t ** 1.4))   # steep dark left side
        else:
            alpha = 0
        if alpha > 0:
            gd.line([(x, 0), (x, H)], fill=(0, 0, 0, alpha))
    # Soften the transition edge
    grad = grad.filter(ImageFilter.GaussianBlur(25))
    canvas = Image.alpha_composite(canvas, grad)

    # ── Center vertical shadow strip — separates text from art ───────────────
    strip = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd    = ImageDraw.Draw(strip)
    SX, SW = 500, 120
    for i in range(SW):
        t     = abs(i - SW / 2) / (SW / 2)
        alpha = int(110 * max(0.0, 1.0 - t ** 2))
        if alpha > 0:
            sd.line([(SX + i, 0), (SX + i, H)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas, strip)

    # ── Color grading (Contrast, Color, Sharpness) — premium anime look ───────
    base = canvas.convert("RGB")
    base = ImageEnhance.Contrast(base).enhance(1.18)
    base = ImageEnhance.Color(base).enhance(1.12)
    base = ImageEnhance.Sharpness(base).enhance(1.25)
    canvas = base.convert("RGBA")

    # ── Nav bar ───────────────────────────────────────────────────────────────
    canvas.alpha_composite(Image.new("RGBA", (W, NAV_H), (0, 0, 0, 200)), (0, 0))
    draw = ImageDraw.Draw(canvas)

    # ── Fonts ─────────────────────────────────────────────────────────────────
    bebas     = _ensure_bebas()
    f_titl_lg = ImageFont.truetype(bebas, 88) if bebas else _f(_BOLD, 80)
    f_titl_md = ImageFont.truetype(bebas, 76) if bebas else _f(_BOLD, 68)
    f_logo    = _f(_BOLD, 19)
    f_nav     = _f(_REG,  18)
    f_meta    = _f(_BOLD, 26)
    f_desc    = _f(_REG,  22)
    f_genre   = _f(_BOLD, 28)
    f_btn     = _f(_BOLD, 22)
    f_pill    = _f(_BOLD, 18)
    f_brand   = _f(_BOLD, 17)

    # ── Logo ──────────────────────────────────────────────────────────────────
    _draw_logo(draw, 16, 10, channel_name, f_logo)

    # ── Nav items — 18px, 55px between items ──────────────────────────────────
    nav_items = ["Home", "Movies", "Animes", "TV Shows", "My List"]
    nx = 290
    for item in nav_items:
        active = item == "Animes"
        col = (*ORANGE, 255) if active else (210, 210, 210, 210)
        draw.text((nx, 15), item, font=f_nav, fill=col)
        bb  = draw.textbbox((nx, 15), item, font=f_nav)
        iw  = bb[2] - bb[0]
        if active:
            draw.line([(nx, NAV_H - 4), (nx + iw, NAV_H - 4)],
                      fill=(*ORANGE, 255), width=2)
        nx += iw + 55
    draw.text((W - 90, 15), "⌕  🔔  👤", font=f_nav, fill=(200, 200, 200, 200))

    # ── Title  x=40, y=100, max 500px wide ───────────────────────────────────
    TX, TY = 40, 100
    title_up = title.upper()
    if len(title_up) <= 18:
        f_title, line_h = f_titl_lg, 98    # 88px + 10 spacing
    else:
        f_title, line_h = f_titl_md, 86    # 76px + 10 spacing

    lines = _wrap_to_width(draw, title_up, f_title, 500)
    for i, line in enumerate(lines):
        ly = TY + i * line_h
        # Thick stroke — 4px weight feel
        for dx, dy in [(-3,0),(3,0),(0,-3),(0,3),(-2,-2),(2,-2),(-2,2),(2,2)]:
            draw.text((TX + dx, ly + dy), line, font=f_title,
                      fill=(0, 0, 0, 120))
        draw.text((TX, ly), line, font=f_title, fill=(255, 255, 255, 255))
    cy = TY + len(lines) * line_h + 20     # subtitle: title_bottom + 20

    # ── Metadata ──────────────────────────────────────────────────────────────
    meta = f"{year}  •  {episodes} Episodes  •  {audio}"
    draw.text((TX, cy), meta, font=f_meta, fill=(235, 235, 235, 240))
    cy += 42

    # ── Description — 22px, rgb(220,220,220), line_spacing=34 ────────────────
    if description:
        for dl in textwrap.wrap(description, width=46)[:4]:
            draw.text((TX, cy), dl, font=f_desc, fill=(220, 220, 220, 215))
            cy += 34
        cy += 8

    # ── Genres — y = desc_bottom + 20 ────────────────────────────────────────
    genre_str = " | ".join(genres[:4])
    if genre_str:
        draw.text((TX, cy), genre_str, font=f_genre, fill=(255, 255, 255, 255))
        cy += 44
    cy += 40    # language: genres_bottom + 40

    # ── Language pills ────────────────────────────────────────────────────────
    hindi = "✓ Hindi"
    hbb   = draw.textbbox((0, 0), hindi, font=f_pill)
    hw    = hbb[2] - hbb[0] + 26
    hh    = hbb[3] - hbb[1] + 14
    draw.rounded_rectangle([(TX, cy), (TX + hw, cy + hh)],
                           radius=hh // 2, fill=(50, 50, 50, 235))
    draw.text((TX + 13, cy + 7), hindi, font=f_pill, fill=(255, 255, 255, 255))
    draw.text((TX + hw + 16, cy + 7), "Japanese Original",
              font=f_pill, fill=(120, 120, 120, 210))
    cy += hh + 50   # watch button: language_bottom + 50

    # ── Watch button — orange→red gradient, radius=18, height=72 ─────────────
    btn_txt = f"▶   Watch Now S{season:02d}"
    bbb     = draw.textbbox((0, 0), btn_txt, font=f_btn)
    bw      = bbb[2] - bbb[0] + 56
    BTN_H   = 72

    # Build gradient strip, then mask to rounded rect
    btn_strip = Image.new("RGBA", (bw, BTN_H), (0, 0, 0, 0))
    bs        = ImageDraw.Draw(btn_strip)
    for xi in range(bw):
        t = xi / max(bw - 1, 1)
        rr = int(230 - 30 * t)   # 230 → 200
        gg = int(60  - 30 * t)   # 60  → 30
        bs.line([(xi, 0), (xi, BTN_H)], fill=(rr, gg, 10, 255))
    mask = Image.new("L", (bw, BTN_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (bw - 1, BTN_H - 1)],
                                           radius=18, fill=255)
    btn_rgba = Image.new("RGBA", (bw, BTN_H), (0, 0, 0, 0))
    btn_rgba.paste(btn_strip, mask=mask)
    # Subtle shadow under button
    shadow_btn = Image.new("RGBA", (bw + 8, BTN_H + 8), (0, 0, 0, 0))
    shadow_btn.paste(Image.new("RGBA", (bw, BTN_H), (0, 0, 0, 100)),
                     (4, 4), mask)
    shadow_btn = shadow_btn.filter(ImageFilter.GaussianBlur(6))
    canvas.alpha_composite(shadow_btn, (TX - 4, cy - 4))
    canvas.alpha_composite(btn_rgba, (TX, cy))

    draw = ImageDraw.Draw(canvas)   # refresh after compositing
    ty_btn = cy + (BTN_H - (bbb[3] - bbb[1])) // 2
    draw.text((TX + 28, ty_btn), btn_txt, font=f_btn, fill=(255, 255, 255, 255))

    # ── Plus circle ───────────────────────────────────────────────────────────
    pcx = TX + bw + 20 + BTN_H // 2
    draw.ellipse([(pcx - BTN_H // 2, cy), (pcx + BTN_H // 2, cy + BTN_H)],
                 outline=(160, 160, 160, 200), width=2)
    draw.text((pcx - 10, cy + BTN_H // 2 - 16), "+", font=f_btn,
              fill=(200, 200, 200, 230))

    # ── Bottom-right branding ─────────────────────────────────────────────────
    brbb = draw.textbbox((0, 0), channel_name, font=f_brand)
    brw, brh = brbb[2] - brbb[0], brbb[3] - brbb[1]
    tg_r = 16
    bx   = W - (tg_r * 2 + 10 + brw) - 18
    by   = H - tg_r * 2 - 16
    draw.ellipse([(bx, by), (bx + tg_r * 2, by + tg_r * 2)],
                 fill=(*BLUE_TG, 255))
    draw.text((bx + 4, by + 3), "✈", font=_f(_BOLD, 15), fill=(255, 255, 255, 255))
    draw.text((bx + tg_r * 2 + 10, by + tg_r - brh // 2),
              channel_name, font=f_brand, fill=(230, 230, 230, 220))

    # ── Export quality=95, optimize=True ─────────────────────────────────────
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

    # Bottom gradient overlay
    ov  = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    ovd = ImageDraw.Draw(ov)
    for y in range(720):
        if y > 540:
            t = (y - 540) / 180
            ovd.line([(0, y), (1280, y)], fill=(0, 0, 0, int(200 * t)))
    img = Image.alpha_composite(img, ov)

    # Small channel name (20px)
    draw = ImageDraw.Draw(img)
    f    = _f(_BOLD, 20)
    text = f"@{channel}"
    tbb  = draw.textbbox((0, 0), text, font=f)
    tw   = tbb[2] - tbb[0]
    th   = tbb[3] - tbb[1]
    tx   = (1280 - tw) // 2
    ty   = 720 - th - 22
    pad  = 12
    draw.rounded_rectangle(
        [(tx - pad, ty - pad // 2), (tx + tw + pad, ty + th + pad // 2)],
        radius=6, fill=(0, 0, 0, 180),
    )
    draw.text((tx, ty), text, font=f, fill=(255, 255, 255, 255))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf.read()
