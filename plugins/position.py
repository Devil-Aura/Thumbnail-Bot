"""Position preset selector for anime thumbnails."""
import io
import logging

from pyrogram import Client, enums, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto,
)

from plugins.anime import sessions, _render, _preview_kb

logger = logging.getLogger(__name__)

# ── 9-grid position presets ───────────────────────────────────────────────────
# code format: "{y}{x}"  where  y = t/m/b  ,  x = l/c/r
_GRID = [
    [("↖ ᴛᴏᴘ ʟᴇꜰᴛ", "tl"), ("⬆ ᴛᴏᴘ ᴄᴇɴ", "tc"), ("↗ ᴛᴏᴘ ʀɪɢʜᴛ", "tr")],
    [("⬅ ᴍɪᴅ ʟᴇꜰᴛ", "ml"), ("⊡ ᴄᴇɴᴛᴇʀ",   "mc"), ("➡ ᴍɪᴅ ʀɪɢʜᴛ", "mr")],
    [("↙ ʙᴏᴛ ʟᴇꜰᴛ", "bl"), ("⬇ ʙᴏᴛ ᴄᴇɴ", "bc"), ("↘ ʙᴏᴛ ʀɪɢʜᴛ", "br")],
]

# Offset values — large values get clamped by the image generator automatically
_X = {"l": 0, "c": 700, "r": 99999}
_Y = {"t": 0, "m": 700, "b": 99999}

_LABELS = {
    "tl": "↖ Top Left",  "tc": "⬆ Top Center",  "tr": "↗ Top Right",
    "ml": "⬅ Mid Left",  "mc": "⊡ Center",       "mr": "➡ Mid Right",
    "bl": "↙ Bot Left",  "bc": "⬇ Bot Center",   "br": "↘ Bot Right",
}


def _pos_kb(uid: int) -> InlineKeyboardMarkup:
    rows = []
    for row in _GRID:
        rows.append([
            InlineKeyboardButton(label, callback_data=f"pos|set|{uid}|{code}")
            for label, code in row
        ])
    rows.append([
        InlineKeyboardButton("🔄 ʀᴇꜱᴇᴛ", callback_data=f"pos|reset|{uid}"),
        InlineKeyboardButton("◀️ ʙᴀᴄᴋ",  callback_data=f"pos|back|{uid}"),
    ])
    return InlineKeyboardMarkup(rows)


@Client.on_callback_query(filters.regex(r"^pos\|"))
async def position_cb(client: Client, cq: CallbackQuery):
    parts  = cq.data.split("|")
    action = parts[1]
    uid    = int(parts[2])

    if cq.from_user.id != uid:
        await cq.answer("This is not your session!", show_alert=True)
        return

    if uid not in sessions:
        await cq.answer("⚠️ Session expired. Run /anime again.", show_alert=True)
        return

    s = sessions[uid]

    # ── Open position panel ────────────────────────────────────────────────────
    if action == "open":
        try:
            await cq.message.edit_reply_markup(reply_markup=_pos_kb(uid))
        except MessageNotModified:
            pass
        await cq.answer("📍 Choose a position")
        return

    # ── Back to main preview controls ─────────────────────────────────────────
    if action == "back":
        try:
            await cq.message.edit_reply_markup(reply_markup=_preview_kb(uid))
        except MessageNotModified:
            pass
        await cq.answer()
        return

    # ── Reset to default position ──────────────────────────────────────────────
    if action == "reset":
        s["offset_x"] = 0
        s["offset_y"] = 0
        await cq.answer("🔄 Position reset to default!")
        await _redraw_pos(cq, s, uid)
        return

    # ── Set a position preset ──────────────────────────────────────────────────
    if action == "set" and len(parts) >= 4:
        code  = parts[3]                                   # e.g. "tl", "mc"
        y_key = code[0] if len(code) > 0 else "m"        # t / m / b
        x_key = code[1] if len(code) > 1 else "c"        # l / c / r
        s["offset_x"] = _X.get(x_key, 0)
        s["offset_y"] = _Y.get(y_key, 0)
        await cq.answer(f"📍 {_LABELS.get(code, 'Position set')}")
        await _redraw_pos(cq, s, uid)
        return

    await cq.answer()


async def _redraw_pos(cq: CallbackQuery, s: dict, uid: int):
    """Re-render thumbnail after position change and update message."""
    total = len(s["images"])
    thumb = None

    for _ in range(total):
        thumb = await _render(s)
        if thumb:
            break
        logger.warning("Position redraw: skipping broken image idx %d", s["img_idx"])
        s["img_idx"] = (s["img_idx"] + 1) % total
        s["offset_x"] = s["offset_y"] = 0

    if not thumb:
        await cq.message.edit_caption(
            "❌ No working images found. Try /anime again.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    idx_display = s["img_idx"] + 1
    try:
        th_io      = io.BytesIO(thumb)
        th_io.name = "thumb.jpg"
        await cq.message.edit_media(
            InputMediaPhoto(
                media=th_io,
                caption=(
                    f"🎨 <b>{s['title']}</b> — S{s['season']:02d}  "
                    f"<code>[{idx_display}/{total}]</code>\n"
                    f"<i>{', '.join(s['genres'][:3])}</i>\n\n"
                    "⬆️⬅️➡️ Pan  •  ➕➖ Zoom  •  📍 Pos  •  ◀️▶️ Swap"
                ),
                parse_mode=enums.ParseMode.HTML,
            ),
            reply_markup=_pos_kb(uid),
        )
    except MessageNotModified:
        pass
    except Exception as e:
        logger.warning("Position redraw edit failed: %s", e)
