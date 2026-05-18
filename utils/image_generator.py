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
    Logo : x=40, y=70  (if logo_bytes — Fanart ClearLOGO replaces title text)
    Title: x=40, y=70  (if no logo)
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


def _smallcaps(text: str) -> str:
    """Convert lowercase letters to Unicode small capitals for clean thumbnail look."""
    _MAP = str.maketrans(
        "abcdefghijklmnopqrstuvwxyz",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"
    )
    return text.translate(_MAP)


def _shadow_text(draw, xy, text, font, fill=(255,255,255,255), shadow=(0,0,0,200), offset=3):
    """Draw text with drop-shadow."""
    sx, sy = xy[0] + offset, xy[1] + offset
    draw.text((sx, sy), text, font=font, fill=shadow)
    draw.text(xy, text, font=font, fill=fill)


def _wrap_truncate(draw, text, font, max_px, max_lines=2):
    """Wrap text to max_lines. Last line gets '...' if truncated."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_px:
            cur = test
        else:
            if cur:
                lines.append(cur)
                if len(lines) >= max_lines:
                    cur = ""
                    break
            cur = w
    if cur and len(lines) < max_lines:
        lines.append(cur)
    elif cur and len(lines) >= max_lines:
        last = lines[-1]
        while last and draw.textbbox((0, 0), last + "...", font=font)[2] > max_px:
            last = last.rsplit(" ", 1)[0]
        lines[-1] = (last + "...") if last else "..."
    result = []
    for ln in lines:
        if draw.textbbox((0, 0), ln, font=font)[2] > max_px:
            while ln and draw.textbbox((0, 0), ln + "...", font=font)[2] > max_px:
                ln = ln[:-1]
            ln = ln + "..."
        result.append(ln)
    return result


def _draw_logo(draw, x, y, text, font):
    r = 15
    cx, cy = x + r, y + r
    draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(*ORANGE, 255))
    draw.text((cx-6, cy-9), "C", font=_f(_BOLD, 14), fill=(255,255,255,255))
    nx = cx + r + 9
    draw.text((nx, y+3), text, font=font, fill=(255,255,255,240))


def _gradient_button(canvas, x, y, w, h, radius, text, font):
    """Draw orange→red gradient rounded button on canvas."""
    strip = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd    = ImageDraw.Draw(strip)
    for xi in range(w):
        t  = xi / max(w - 1, 1)
        rr = int(235 - 50 * t)
        gg = int(80  - 55 * t)
        sd.line([(xi, 0), (xi, h)], fill=(rr, gg, 10, 255))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0,0),(w-1,h-1)], radius=radius, fill=255)
    btn = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    btn.paste(strip, mask=mask)
    shad = Image.new("RGBA", (w+10, h+10), (0, 0, 0, 0))
    shad.paste(Image.new("RGBA", (w, h), (0, 0, 0, 90)), (5, 5), mask)
    shad = shad.filter(ImageFilter.GaussianBlur(8))
    canvas.alpha_composite(shad, (x-5, y-5))
    canvas.alpha_composite(btn, (x, y))
    draw = ImageDraw.Draw(canvas)
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    tx = x + (w - tw) // 2 - bb[0]
    ty = y + (h - th) // 2 - bb[1]
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))
    return draw


def _composite_clearlogo(canvas: Image.Image, logo_bytes: bytes,
                          x: int, y: int, max_w: int, max_h: int) -> int:
    """
    Composite a Fanart.tv ClearLOGO (PNG with transparency) onto canvas.
    Scales to fit within max_w x max_h preserving aspect ratio.
    Returns the bottom y coordinate of the placed logo.
    """
    try:
        logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
        lw, lh = logo.size
        scale  = min(max_w / lw, max_h / lh, 1.0)
        nw, nh = int(lw * scale), int(lh * scale)
        logo   = logo.resize((nw, nh), Image.LANCZOS)

        # Subtle drop shadow for readability over any background
        shadow = Image.new("RGBA", (nw + 8, nh + 8), (0, 0, 0, 0))
        shadow.paste(Image.new("RGBA", (nw, nh), (0, 0, 0, 120)), (4, 4), logo)
        shadow = shadow.filter(ImageFilter.GaussianBlur(6))
        canvas.alpha_composite(shadow, (x - 4, y - 4))
        canvas.alpha_composite(logo, (x, y))
        return y + nh
    except Exception:
        return y  # logo load failed — caller will fall back to text title


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
    logo_bytes: Optional[bytes] = None,
) -> bytes:
    scale = max(1.0, min(scale, 3.0))

    # ── 1. Pure black canvas ─────────────────────────────────────────────────
    canvas = Image.new("RGBA", (W, H), (*DARK, 255))

    # ── 2. Anime art full background ─────────────────────────────────────────
    if art_bytes:
        art = Image.open(io.BytesIO(art_bytes)).convert("RGBA")
        aw, ah = art.size
        fit = max(W / aw, H / ah) * scale
        sw, sh = int(aw * fit), int(ah * fit)
        art = art.resize((sw, sh), Image.LANCZOS)
        ox = max(0, min(offset_x, max(0, sw - W)))
        oy = max(0, min(offset_y, max(0, sh - H)))
        crop = art.crop((ox, oy, ox + W, oy + H))
        canvas.paste(crop, (0, 0), crop)

    # ── 3. Warm glow ─────────────────────────────────────────────────────────
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([(640, -60), (1380, 760)], fill=(*AMBER, 30))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    canvas = Image.alpha_composite(canvas, glow)

    # ── 4. Left gradient overlay ──────────────────────────────────────────────
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(grad)
    FADE_START = 420
    FADE_END   = 820
    for x in range(W):
        if x <= FADE_START:
            alpha = 195
        elif x <= FADE_END:
            t     = (x - FADE_START) / (FADE_END - FADE_START)
            alpha = int(195 * (1.0 - t ** 1.4))
        else:
            alpha = 0
        if alpha > 0:
            gd.line([(x, 0), (x, H)], fill=(0, 0, 0, alpha))
    grad_edge = grad.crop((FADE_START - 40, 0, FADE_END + 40, H))
    grad_edge = grad_edge.filter(ImageFilter.GaussianBlur(22))
    grad.paste(grad_edge, (FADE_START - 40, 0))
    canvas = Image.alpha_composite(canvas, grad)

    # ── 5. Color grading ──────────────────────────────────────────────────────
    base = canvas.convert("RGB")
    base = ImageEnhance.Contrast(base).enhance(1.20)
    base = ImageEnhance.Color(base).enhance(1.15)
    base = ImageEnhance.Sharpness(base).enhance(1.30)
    canvas = base.convert("RGBA")

    draw = ImageDraw.Draw(canvas)

    # ── 6. Fonts ──────────────────────────────────────────────────────────────
    bebas     = _ensure_bebas()
    f_titl_lg = ImageFont.truetype(bebas, 92) if bebas else _f(_BOLD, 82)
    f_titl_md = ImageFont.truetype(bebas, 78) if bebas else _f(_BOLD, 70)
    f_logo    = _f(_BOLD, 18)
    f_nav     = _f(_BOLD, 17)
    f_meta    = _f(_BOLD, 24)
    f_desc    = _f(_BOLD, 17)
    f_genre   = _f(_BOLD, 26)
    f_btn     = _f(_BOLD, 23)
    f_pill    = _f(_BOLD, 17)
    f_brand   = _f(_BOLD, 16)
    f_plus    = _f(_BOLD, 28)

    # ── 7. Nav logo ───────────────────────────────────────────────────────────
    _draw_logo(draw, 18, 11, channel_name, f_logo)

    # ── 8. Nav bar — evenly spaced items ─────────────────────────────────────
    logo_end_x = 18 + 15*2 + 9
    logo_bb = draw.textbbox((logo_end_x, 11+3), channel_name, font=f_logo)
    logo_right = logo_bb[2] + 28

    nav_items = ["Home", "Movies", "Animes", "TV Shows", "My List"]
    nav_widths = [draw.textbbox((0, 0), it, font=f_nav)[2] - draw.textbbox((0, 0), it, font=f_nav)[0]
                  for it in nav_items]
    total_nav_w = sum(nav_widths)
    right_icons_x = W - 110
    avail = right_icons_x - logo_right
    gap = (avail - total_nav_w) // (len(nav_items) + 1)
    gap = max(28, min(gap, 60))

    nx = logo_right + gap
    for i, item in enumerate(nav_items):
        active = item == "Animes"
        col    = (*ORANGE, 255) if active else (215, 215, 215, 215)
        draw.text((nx, 17), item, font=f_nav, fill=col)
        iw = nav_widths[i]
        if active:
            draw.line([(nx, NAV_H - 4), (nx + iw, NAV_H - 4)],
                      fill=(*ORANGE, 255), width=2)
        nx += iw + gap
    draw.text((W - 96, 17), "⌕  🔔  👤", font=f_nav, fill=(200,200,200,200))

    # ── 9. Title / ClearLOGO ─────────────────────────────────────────────────
    TX, TY   = 40, 70
    MAX_TW   = 540

    if logo_bytes:
        # Fanart HD ClearLOGO — transparent PNG composited instead of text title
        # Max 480×160px — large enough to read, small enough to leave room for metadata
        cy = _composite_clearlogo(canvas, logo_bytes, TX, TY, max_w=480, max_h=160)
        draw = ImageDraw.Draw(canvas)   # refresh draw handle after alpha_composite
        cy += 18
    else:
        # Text title fallback (Bebas Neue, max 2 lines with "..." truncation)
        title_up = title.upper()
        if len(title_up) <= 16:
            f_t, lh = f_titl_lg, 100
        else:
            f_t, lh = f_titl_md, 88

        lines = _wrap_truncate(draw, title_up, f_t, MAX_TW, max_lines=2)
        for i, ln in enumerate(lines):
            _shadow_text(draw, (TX, TY + i * lh), ln, f_t,
                         fill=(255,255,255,255), shadow=(0,0,0,200), offset=4)
        cy = TY + len(lines) * lh + 18

    # ── 10. Subtitle ──────────────────────────────────────────────────────────
    subtitle = f"{year}  •  {episodes} Episodes  •  Hindi #Official"
    _shadow_text(draw, (TX, cy), subtitle, f_meta,
                 fill=(240,240,240,245), shadow=(0,0,0,160), offset=2)
    cy += draw.textbbox((0,0), subtitle, font=f_meta)[3] + 2

    # ── 11. Description — up to 5 lines, smallcaps, centered in left zone ────
    if description:
        _PANEL_W = LEFT_END - TX
        for dl in textwrap.wrap(description, width=55)[:5]:
            sc_line = _smallcaps(dl)
            lw = draw.textbbox((0, 0), sc_line, font=f_desc)[2]
            lx = TX + max(0, (_PANEL_W - lw) // 2)
            draw.text((lx, cy), sc_line, font=f_desc, fill=(210, 210, 210, 218))
            cy += 22
        cy += 4

    # ── 12. Genres ────────────────────────────────────────────────────────────
    genre_str = "  |  ".join(genres[:4])
    if genre_str:
        _shadow_text(draw, (TX, cy), genre_str, f_genre,
                     fill=(255,255,255,255), shadow=(0,0,0,150), offset=2)
        cy += draw.textbbox((0,0), genre_str, font=f_genre)[3] + 38

    # ── 13. Language pills ────────────────────────────────────────────────────
    hindi = "✓  Hindi"
    hbb   = draw.textbbox((0,0), hindi, font=f_pill)
    hw    = hbb[2] - hbb[0] + 28
    hh    = hbb[3] - hbb[1] + 16
    draw.rounded_rectangle([(TX, cy), (TX+hw, cy+hh)],
                           radius=hh//2, fill=(45,45,55,240))
    ty_pill = cy + (hh - (hbb[3] - hbb[1])) // 2 - hbb[1]
    draw.text((TX+14, ty_pill), hindi, font=f_pill, fill=(255,255,255,255))
    draw.text((TX+hw+18, ty_pill), "Japanese Original",
              font=f_pill, fill=(130,130,130,215))
    cy += hh + 48

    # ── 14. Watch Now button — text centred ───────────────────────────────────
    btn_txt = f"▶  Watch Now S{season:02d}"
    bbb     = draw.textbbox((0,0), btn_txt, font=f_btn)
    bw      = (bbb[2]-bbb[0]) + 60
    BTN_H   = 66
    draw = _gradient_button(canvas, TX, cy, bw, BTN_H, 20, btn_txt, f_btn)

    # ── 15. Plus circle — "+" perfectly centred ───────────────────────────────
    pr  = BTN_H // 2
    pcx = TX + bw + 20 + pr
    pcy = cy
    draw.ellipse([(pcx - pr, pcy), (pcx + pr, pcy + BTN_H)],
                 outline=(170, 170, 170, 210), width=2)
    pb  = draw.textbbox((0, 0), "+", font=f_plus)
    pw  = pb[2] - pb[0]
    ph  = pb[3] - pb[1]
    ptx = pcx - pw // 2 - pb[0]
    pty = pcy + (BTN_H - ph) // 2 - pb[1]
    draw.text((ptx, pty), "+", font=f_plus, fill=(200, 200, 200, 230))

    # ── 16. Bottom-right branding ─────────────────────────────────────────────
    brbb = draw.textbbox((0,0), channel_name, font=f_brand)
    brw, brh = brbb[2]-brbb[0], brbb[3]-brbb[1]
    tg_r = 16
    bx   = W - (tg_r*2 + 10 + brw) - 18
    by   = H - tg_r*2 - 16
    draw.ellipse([(bx, by), (bx+tg_r*2, by+tg_r*2)], fill=(*BLUE_TG, 255))
    draw.text((bx+5, by+3), "✈", font=_f(_BOLD,14), fill=(255,255,255,255))
    draw.text((bx+tg_r*2+10, by+tg_r-brh//2),
              channel_name, font=f_brand, fill=(230,230,230,215))

    # ── 17. Export ────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="JPEG", quality=95, optimize=True)
    buf.seek(0)
    return buf.read()


# ── Spoiler background ────────────────────────────────────────────────────────

def make_spoiler_bg(art_bytes: Optional[bytes]) -> bytes:
    """
    Dark blurred spoiler background — 1280x720.
    Used as the spoiler image sent before the AniList info card.
    """
    canvas = Image.new("RGB", (W, H), DARK)
    if art_bytes:
        art = Image.open(io.BytesIO(art_bytes)).convert("RGB")
        aw, ah = art.size
        fit = max(W / aw, H / ah)
        sw, sh = int(aw * fit), int(ah * fit)
        art = art.resize((sw, sh), Image.LANCZOS)
        ox = (sw - W) // 2
        oy = (sh - H) // 2
        canvas.paste(art.crop((ox, oy, ox + W, oy + H)))
    canvas = canvas.filter(ImageFilter.GaussianBlur(18))
    canvas = ImageEnhance.Brightness(canvas).enhance(0.35)
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return buf.read()
