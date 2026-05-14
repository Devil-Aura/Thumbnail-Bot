"""
CrunchyRoll-style 1280x720 anime streaming banner.

Composition:
  LEFT  (45% = 0-576px)  : SOLID DEEP BLACK — UI text zone
  RIGHT (55% = 576-1280) : Anime key visual, character on far-right edge

Gradient : 0-576 solid black | 576-960 smooth cinematic fade | 960+ transparent
Character: positioned at far-right edge with heavy overflow (partially cropped)
Glow     : amber ellipse behind character, GaussianBlur(120)
Grading  : Contrast=1.20, Color=1.15, Sharpness=1.30

Layout (y positions):
  NAV  : 0-52
  Title: x=40, y=70
  Meta : title_bottom + 18
  Desc : meta_bottom + 14
  Genre: desc_bottom + 16
  Lang : genre_bottom + 36
  Watch: lang_bottom  + 48
"""
import io
import os
import textwrap
import urllib.request
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

W, H    = 1280, 720
NAV_H   = 52
DARK    = (4, 4, 12)
ORANGE  = (255, 140, 0)
AMBER   = (255, 115, 15)
RED_ORG = (220, 55, 10)
BLUE_TG = (41, 182, 246)

# Left zone ends at 45% = 576px
LEFT_END = 576

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


def _shadow_text(draw, xy, text, font, fill=(255,255,255,255), shadow=(0,0,0,200), offset=3):
    """Draw text with drop-shadow."""
    sx, sy = xy[0] + offset, xy[1] + offset
    draw.text((sx, sy), text, font=font, fill=shadow)
    draw.text(xy, text, font=font, fill=fill)


def _wrap_to_px(draw, text, font, max_px):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_px:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]


def _draw_logo(draw, x, y, text, font):
    r = 15
    cx, cy = x + r, y + r
    draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(*ORANGE, 255))
    draw.text((cx-6, cy-9), "C", font=_f(_BOLD, 14), fill=(255,255,255,255))
    nx = cx + r + 9
    draw.text((nx, y+3), text, font=font, fill=(255,255,255,240))


def _gradient_button(canvas, x, y, w, h, radius, text, font):
    """Draw orange→red gradient rounded button on canvas. Returns draw object."""
    strip = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd    = ImageDraw.Draw(strip)
    for xi in range(w):
        t  = xi / max(w - 1, 1)
        rr = int(235 - 50 * t)   # 235→185
        gg = int(80  - 55 * t)   # 80→25
        sd.line([(xi, 0), (xi, h)], fill=(rr, gg, 10, 255))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0,0),(w-1,h-1)], radius=radius, fill=255)
    btn = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    btn.paste(strip, mask=mask)
    # Subtle drop shadow
    shad = Image.new("RGBA", (w+10, h+10), (0, 0, 0, 0))
    shad.paste(Image.new("RGBA", (w, h), (0, 0, 0, 90)), (5, 5), mask)
    shad = shad.filter(ImageFilter.GaussianBlur(8))
    canvas.alpha_composite(shad, (x-5, y-5))
    canvas.alpha_composite(btn, (x, y))
    draw = ImageDraw.Draw(canvas)
    bb   = draw.textbbox((0, 0), text, font=font)
    tx   = x + (w - (bb[2]-bb[0])) // 2
    ty   = y + (h - (bb[3]-bb[1])) // 2
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))
    return draw


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

    # ── 1. Pure black canvas ──────────────────────────────────────────────────
    canvas = Image.new("RGBA", (W, H), (*DARK, 255))

    # ── 2. Anime art — placed on RIGHT, character overflows right edge ────────
    if art_bytes:
        art = Image.open(io.BytesIO(art_bytes)).convert("RGBA")
        aw, ah = art.size
        # Scale to fill right zone height
        fit = (H / ah) * scale
        sw, sh = int(aw * fit), int(ah * fit)
        art = art.resize((sw, sh), Image.LANCZOS)
        # Overflow right edge: char starts at ~center, bleeds right
        char_x = W - sw + int(sw * 0.22) + offset_x
        char_x = max(LEFT_END - 80, min(char_x, W - 100))
        oy     = max(0, min(offset_y, max(0, sh - H)))
        crop   = art.crop((0, oy, sw, oy + H))
        canvas.paste(crop, (char_x, 0), crop)

    # ── 3. Warm atmospheric glow in transition zone (behind character) ────────
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([(640, -60), (1380, 760)], fill=(*AMBER, 42))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    canvas = Image.alpha_composite(canvas, glow)

    # ── 4. Cinematic LEFT GRADIENT ────────────────────────────────────────────
    # Zone A: 0 → LEFT_END (576px) — SOLID BLACK
    # Zone B: LEFT_END → 960px    — smooth fade black→transparent
    # Zone C: 960px+ — transparent
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(grad)
    FADE_START = LEFT_END          # 576
    FADE_END   = 960
    for x in range(W):
        if x <= FADE_START:
            alpha = 255
        elif x <= FADE_END:
            t     = (x - FADE_START) / (FADE_END - FADE_START)
            alpha = int(255 * (1.0 - t ** 1.6))
        else:
            alpha = 0
        if alpha > 0:
            gd.line([(x, 0), (x, H)], fill=(0, 0, 0, alpha))
    # Feather only the transition zone (not the solid zone)
    grad_edge = grad.crop((FADE_START - 60, 0, FADE_END + 60, H))
    grad_edge = grad_edge.filter(ImageFilter.GaussianBlur(28))
    grad.paste(grad_edge, (FADE_START - 60, 0))
    canvas = Image.alpha_composite(canvas, grad)

    # ── 5. Color grading ──────────────────────────────────────────────────────
    base = canvas.convert("RGB")
    base = ImageEnhance.Contrast(base).enhance(1.20)
    base = ImageEnhance.Color(base).enhance(1.15)
    base = ImageEnhance.Sharpness(base).enhance(1.30)
    canvas = base.convert("RGBA")

    # ── 6. Nav bar ────────────────────────────────────────────────────────────
    canvas.alpha_composite(Image.new("RGBA", (W, NAV_H), (0, 0, 0, 210)), (0, 0))
    draw = ImageDraw.Draw(canvas)

    # ── 7. Fonts ──────────────────────────────────────────────────────────────
    bebas     = _ensure_bebas()
    f_titl_lg = ImageFont.truetype(bebas, 92) if bebas else _f(_BOLD, 82)
    f_titl_md = ImageFont.truetype(bebas, 78) if bebas else _f(_BOLD, 70)
    f_logo    = _f(_BOLD, 18)
    f_nav     = _f(_REG,  17)
    f_meta    = _f(_BOLD, 24)
    f_desc    = _f(_REG,  21)
    f_genre   = _f(_BOLD, 26)
    f_btn     = _f(_BOLD, 23)
    f_pill    = _f(_BOLD, 17)
    f_brand   = _f(_BOLD, 16)
    f_plus    = _f(_BOLD, 28)

    # ── 8. Logo ───────────────────────────────────────────────────────────────
    _draw_logo(draw, 18, 11, channel_name, f_logo)

    # ── 9. Nav items ──────────────────────────────────────────────────────────
    nav_items = ["Home", "Movies", "Animes", "TV Shows", "My List"]
    nx = 280
    for item in nav_items:
        active = item == "Animes"
        col    = (*ORANGE, 255) if active else (215, 215, 215, 215)
        draw.text((nx, 17), item, font=f_nav, fill=col)
        bb  = draw.textbbox((nx, 17), item, font=f_nav)
        iw  = bb[2] - bb[0]
        if active:
            draw.line([(nx, NAV_H - 4), (nx + iw, NAV_H - 4)],
                      fill=(*ORANGE, 255), width=2)
        nx += iw + 55
    draw.text((W - 96, 17), "⌕  🔔  👤", font=f_nav, fill=(200,200,200,200))

    # ── 10. Title  x=40, y=70 ─────────────────────────────────────────────────
    TX, TY   = 40, 70
    MAX_TW   = 540
    title_up = title.upper()
    if len(title_up) <= 16:
        f_t, lh = f_titl_lg, 100
    else:
        f_t, lh = f_titl_md, 88

    lines = _wrap_to_px(draw, title_up, f_t, MAX_TW)
    for i, ln in enumerate(lines):
        _shadow_text(draw, (TX, TY + i * lh), ln, f_t,
                     fill=(255,255,255,255), shadow=(0,0,0,200), offset=4)
    cy = TY + len(lines) * lh + 18

    # ── 11. Subtitle ──────────────────────────────────────────────────────────
    subtitle = f"{year}  •  {episodes} Episodes  •  Hindi #Official"
    _shadow_text(draw, (TX, cy), subtitle, f_meta,
                 fill=(240,240,240,245), shadow=(0,0,0,160), offset=2)
    cy += draw.textbbox((0,0), subtitle, font=f_meta)[3] + 20

    # ── 12. Description ───────────────────────────────────────────────────────
    if description:
        for dl in textwrap.wrap(description, width=44)[:4]:
            draw.text((TX, cy), dl, font=f_desc, fill=(210,210,210,218))
            cy += 33
        cy += 8

    # ── 13. Genres ────────────────────────────────────────────────────────────
    genre_str = "  |  ".join(genres[:4])
    if genre_str:
        _shadow_text(draw, (TX, cy), genre_str, f_genre,
                     fill=(255,255,255,255), shadow=(0,0,0,150), offset=2)
        cy += draw.textbbox((0,0), genre_str, font=f_genre)[3] + 38

    # ── 14. Language pills ────────────────────────────────────────────────────
    hindi = "✓  Hindi"
    hbb   = draw.textbbox((0,0), hindi, font=f_pill)
    hw, hh = hbb[2]-hbb[0]+28, hbb[3]-hbb[1]+16
    draw.rounded_rectangle([(TX, cy), (TX+hw, cy+hh)],
                           radius=hh//2, fill=(45,45,55,240))
    draw.text((TX+14, cy+8), hindi, font=f_pill, fill=(255,255,255,255))
    draw.text((TX+hw+18, cy+8), "Japanese Original",
              font=f_pill, fill=(130,130,130,215))
    cy += hh + 48

    # ── 15. Watch Now button ──────────────────────────────────────────────────
    btn_txt = f"▶  Watch Now S{season:02d}"
    bbb     = draw.textbbox((0,0), btn_txt, font=f_btn)
    bw      = bbb[2]-bbb[0] + 60
    BTN_H   = 66
    draw = _gradient_button(canvas, TX, cy, bw, BTN_H, 20, btn_txt, f_btn)

    # ── 16. Plus circle ───────────────────────────────────────────────────────
    pr  = BTN_H // 2
    pcx = TX + bw + 20 + pr
    pcy = cy
    draw.ellipse([(pcx-pr, pcy), (pcx+pr, pcy+BTN_H)],
                 outline=(170,170,170,210), width=2)
    pb  = draw.textbbox((0,0), "+", font=f_plus)
    draw.text((pcx-(pb[2]-pb[0])//2, pcy+(BTN_H-(pb[3]-pb[1]))//2),
              "+", font=f_plus, fill=(200,200,200,230))

    # ── 17. Bottom-right branding ─────────────────────────────────────────────
    brbb = draw.textbbox((0,0), channel_name, font=f_brand)
    brw, brh = brbb[2]-brbb[0], brbb[3]-brbb[1]
    tg_r = 16
    bx   = W - (tg_r*2 + 10 + brw) - 18
    by   = H - tg_r*2 - 16
    draw.ellipse([(bx, by), (bx+tg_r*2, by+tg_r*2)], fill=(*BLUE_TG, 255))
    draw.text((bx+5, by+3), "✈", font=_f(_BOLD,14), fill=(255,255,255,255))
    draw.text((bx+tg_r*2+10, by+tg_r-brh//2),
              channel_name, font=f_brand, fill=(230,230,230,215))

    # ── 18. Export ────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="JPEG", quality=95, optimize=True)
    buf.seek(0)
    return buf.read()


# ── Spoiler background ────────────────────────────────────────────────────────
def make_spoiler_bg(bg_bytes: bytes, channel: str) -> bytes:
    img   = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
    w, h  = img.size
    ratio = max(1280 / w, 720 / h)
    img   = img.resize((int(w*ratio), int(h*ratio)), Image.LANCZOS)
    img   = img.crop((0, 0, 1280, 720))

    # Dark vignette bottom
    ov  = Image.new("RGBA", (1280, 720), (0,0,0,0))
    ovd = ImageDraw.Draw(ov)
    for y in range(720):
        if y > 500:
            t = (y-500)/220
            ovd.line([(0,y),(1280,y)], fill=(0,0,0,int(210*t)))
    img = Image.alpha_composite(img, ov)

    draw = ImageDraw.Draw(img)
    f    = _f(_BOLD, 20)
    text = f"@{channel}"
    tbb  = draw.textbbox((0,0), text, font=f)
    tw, th = tbb[2]-tbb[0], tbb[3]-tbb[1]
    tx   = (1280-tw)//2
    ty   = 720-th-24
    pad  = 14
    draw.rounded_rectangle([(tx-pad, ty-6),(tx+tw+pad, ty+th+6)],
                           radius=6, fill=(0,0,0,185))
    draw.text((tx, ty), text, font=f, fill=(255,255,255,255))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf.read()
