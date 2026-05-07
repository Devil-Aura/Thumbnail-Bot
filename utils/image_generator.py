import io
import os
import textwrap
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

OUTPUT_W, OUTPUT_H = 1280, 720

# Try multiple font paths common on Debian/Ubuntu VPS
_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
]
_REG_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
]


def _find_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _gradient_image(w: int, h: int, start_alpha: int, end_alpha: int, vertical=True) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    steps = h if vertical else w
    for i in range(steps):
        t = i / steps
        alpha = int(start_alpha + (end_alpha - start_alpha) * (t ** 1.6))
        if vertical:
            draw.line([(0, i), (w, i)], fill=(0, 0, 0, alpha))
        else:
            draw.line([(i, 0), (i, h)], fill=(0, 0, 0, alpha))
    return img


def make_thumbnail(
    bg_bytes: bytes,
    title: str,
    subtitle: str = "",
    offset_x: int = 0,
    offset_y: int = 0,
    scale: float = 1.0,
    accent_color: tuple = (255, 80, 0),
) -> bytes:
    """
    Generate a 1280×720 styled thumbnail.

    Args:
        bg_bytes:    Raw bytes of the background image (any PIL-readable format).
        title:       Main title text (anime name).
        subtitle:    Secondary text (year, genres, etc.).
        offset_x:    Horizontal pan offset in pixels (after scaling).
        offset_y:    Vertical pan offset in pixels (after scaling).
        scale:       Background scale factor (1.0 = fit, >1 = zoom in).
        accent_color: RGB tuple for the accent bar.

    Returns:
        JPEG bytes of the finished 1280×720 thumbnail.
    """
    scale = max(1.0, min(scale, 3.0))

    # ── Load & scale background ──────────────────────────────────────────
    bg_src = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
    src_w, src_h = bg_src.size

    # Fit to canvas first (so scale=1.0 fills the frame), then apply user scale
    fit_ratio = max(OUTPUT_W / src_w, OUTPUT_H / src_h)
    base_w = int(src_w * fit_ratio * scale)
    base_h = int(src_h * fit_ratio * scale)
    bg_scaled = bg_src.resize((base_w, base_h), Image.LANCZOS)

    # Clamp pan offsets
    max_ox = max(0, base_w - OUTPUT_W)
    max_oy = max(0, base_h - OUTPUT_H)
    ox = max(0, min(offset_x, max_ox))
    oy = max(0, min(offset_y, max_oy))

    bg_crop = bg_scaled.crop((ox, oy, ox + OUTPUT_W, oy + OUTPUT_H))

    # ── Canvas ───────────────────────────────────────────────────────────
    canvas = Image.new("RGBA", (OUTPUT_W, OUTPUT_H), (0, 0, 0, 255))
    canvas.paste(bg_crop, (0, 0))

    # Slight desaturation for text legibility
    canvas_rgb = canvas.convert("RGB")
    enhancer = ImageEnhance.Color(canvas_rgb)
    canvas_rgb = enhancer.enhance(0.85)
    canvas = canvas_rgb.convert("RGBA")

    # ── Gradient overlays ────────────────────────────────────────────────
    # Bottom dark gradient (text area)
    bottom_grad = _gradient_image(OUTPUT_W, OUTPUT_H, 0, 230, vertical=True)
    canvas = Image.alpha_composite(canvas, bottom_grad)

    # Left dark gradient (accent area)
    left_grad = _gradient_image(OUTPUT_W, OUTPUT_H, 160, 0, vertical=False)
    canvas = Image.alpha_composite(canvas, left_grad)

    # ── Fonts ─────────────────────────────────────────────────────────────
    font_title    = _find_font(_BOLD_CANDIDATES, 72)
    font_subtitle = _find_font(_REG_CANDIDATES, 34)
    font_badge    = _find_font(_BOLD_CANDIDATES, 22)

    draw = ImageDraw.Draw(canvas)

    # ── Accent vertical bar ───────────────────────────────────────────────
    bar_x = 52
    bar_top = OUTPUT_H - 260
    bar_bot = OUTPUT_H - 40
    draw.rounded_rectangle(
        [(bar_x, bar_top), (bar_x + 7, bar_bot)],
        radius=4,
        fill=(*accent_color, 255),
    )

    # ── ANIME badge ───────────────────────────────────────────────────────
    badge_text = "ᴀɴɪᴍᴇ"
    badge_x = bar_x + 20
    badge_y = bar_top
    badge_bbox = draw.textbbox((badge_x, badge_y), badge_text, font=font_badge)
    pad = 6
    draw.rounded_rectangle(
        [
            (badge_bbox[0] - pad, badge_bbox[1] - pad),
            (badge_bbox[2] + pad, badge_bbox[3] + pad),
        ],
        radius=5,
        fill=(*accent_color, 200),
    )
    draw.text((badge_x, badge_y), badge_text, font=font_badge, fill=(255, 255, 255, 255))

    # ── Title ─────────────────────────────────────────────────────────────
    title_x = bar_x + 20
    title_y = bar_top + 46

    # Wrap long titles
    max_chars = 22
    lines = textwrap.wrap(title, width=max_chars)[:2]

    for i, line in enumerate(lines):
        ty = title_y + i * 80
        # Drop shadow
        draw.text((title_x + 3, ty + 3), line, font=font_title, fill=(0, 0, 0, 160))
        # Main text
        draw.text((title_x, ty), line, font=font_title, fill=(255, 255, 255, 255))

    # ── Subtitle ──────────────────────────────────────────────────────────
    if subtitle:
        sub_y = title_y + len(lines) * 80 + 10
        draw.text(
            (title_x, sub_y),
            subtitle,
            font=font_subtitle,
            fill=(210, 210, 210, 230),
        )

    # ── Bottom horizontal accent line ─────────────────────────────────────
    draw.rectangle(
        [(bar_x, OUTPUT_H - 36), (OUTPUT_W - bar_x, OUTPUT_H - 32)],
        fill=(*accent_color, 100),
    )

    # ── Encode to JPEG ────────────────────────────────────────────────────
    final = canvas.convert("RGB")
    buf = io.BytesIO()
    final.save(buf, format="JPEG", quality=95, optimize=True)
    buf.seek(0)
    return buf.read()
