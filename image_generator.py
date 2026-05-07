import io
import os
import asyncio
from aiohttp import ClientSession
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from bot import Var, LOGS
from bot.core.tmdb_api import TmdbClient
from bot.core.puter_client import PuterAIClient

# ─── Font paths ───
_FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")
_FONT_BOLD = os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")
_FONT_REG = os.path.join(_FONT_DIR, "DejaVuSans.ttf")
_FONT_CAL = os.path.join(_FONT_DIR, "CalSans-SemiBold.otf")
_FONT_MONO = os.path.join(_FONT_DIR, "LTSuperiorMono-Regular.otf")


def _load_font(bold=True, size=40, font=None):
    """Load font with fallback to default.

    Args:
        bold: Use bold variant (ignored when *font* is given).
        size: Font size in pixels.
        font: Explicit font key – 'cal', 'mono', 'bold', or 'regular'.
    """
    _MAP = {"cal": _FONT_CAL, "mono": _FONT_MONO,
            "bold": _FONT_BOLD, "regular": _FONT_REG}
    if font:
        path = _MAP.get(font, _FONT_BOLD if bold else _FONT_REG)
    else:
        path = _FONT_BOLD if bold else _FONT_REG
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype(_FONT_BOLD if bold else _FONT_REG, size)
        except Exception:
            return ImageFont.load_default()


class ImageGenerator:
    """
    Generates professional anime banner images (1280×720) for Telegram.

    Layout matches sample designs:
    ┌─────┬──────────────────────────┬──────────────────┐
    │TEAM │  AI/TMDB Backdrop        │ Nav Tabs         │
    │WAR- │  with gradient overlay   ├──────────────────┤
    │LORDS│                          │ Character Images │
    │     │  Title Text              ├──────────────────┤
    │     │  Season/Episode          │ GENRES pills     │
    │     │             [Watch Now]  ├──────────────────┤
    │     │                          │ Schedule Days    │
    │     │                          │ Rating • Studio  │
    └─────┴──────────────────────────┴──────────────────┘
    """

    WIDTH = 1280
    HEIGHT = 720
    SIDEBAR_W = 100
    RIGHT_PANEL_W = 380

    def __init__(self):
        self.tmdb = TmdbClient(Var.TMDB_API_KEY)
        self.puter = PuterAIClient()

    # ─── AniList fallback for poster ────────────────────────────────────

    @staticmethod
    async def _fetch_anilist_poster(title: str) -> str | None:
        """Query AniList for portrait cover image as fallback."""
        query = '''
        query ($search: String) {
            Media (search: $search, type: ANIME) {
                coverImage { extraLarge large }
            }
        }
        '''
        try:
            async with ClientSession() as session:
                async with session.post(
                    'https://graphql.anilist.co',
                    json={'query': query, 'variables': {'search': title}},
                    timeout=10,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        media = (data.get('data') or {}).get('Media') or {}
                        cover = media.get('coverImage') or {}
                        return cover.get('extraLarge') or cover.get('large')
        except Exception as e:
            LOGS.error(f"AniList poster fallback failed: {e}")
        return None

    # ─── Image downloading ──────────────────────────────────────────────

    async def _download_image(self, url: str) -> Image.Image | None:
        if not url:
            return None
        try:
            async with ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        return Image.open(io.BytesIO(data)).convert("RGBA")
        except Exception as e:
            LOGS.error(f"Image Download Failed: {e}")
        return None

    async def _download_multiple(self, urls: list[str]) -> list[Image.Image]:
        """Download multiple images concurrently."""
        tasks = [self._download_image(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, Image.Image)]

    # ─── PIL helper methods ─────────────────────────────────────────────

    @staticmethod
    def _round_corners(img: Image.Image, radius: int) -> Image.Image:
        """Add rounded corners to an image."""
        circle = Image.new("L", (radius * 2, radius * 2), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, radius * 2 - 1, radius * 2 - 1), fill=255)
        alpha = Image.new("L", img.size, 255)
        w, h = img.size
        alpha.paste(circle.crop((0, 0, radius, radius)), (0, 0))
        alpha.paste(circle.crop((0, radius, radius, radius * 2)), (0, h - radius))
        alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (w - radius, 0))
        alpha.paste(circle.crop((radius, radius, radius * 2, radius * 2)), (w - radius, h - radius))
        img.putalpha(alpha)
        return img

    @staticmethod
    def _draw_text_outlined(draw, pos, text, font, fill="white", outline="black", width=2):
        """Draw text with an outline for readability over images."""
        x, y = pos
        for dx in range(-width, width + 1):
            for dy in range(-width, width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=outline)
        draw.text(pos, text, font=font, fill=fill)

    @staticmethod
    def _fit_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
        """Resize and center-crop image to exact target dimensions."""
        ratio = max(target_w / img.width, target_h / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        left = (img.width - target_w) // 2
        top = (img.height - target_h) // 2
        return img.crop((left, top, left + target_w, top + target_h))

    @staticmethod
    def _make_gradient(width: int, height: int, start_alpha: int = 0) -> Image.Image:
        """Create a bottom-up dark gradient overlay."""
        gradient = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(gradient)
        for y in range(height):
            # Gradient: transparent at top, dark at bottom
            progress = y / height
            if progress > 0.3:
                alpha = int(220 * ((progress - 0.3) / 0.7))
            else:
                alpha = start_alpha
            draw.line((0, y, width, y), fill=alpha)
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay.paste((0, 0, 0), (0, 0, width, height), mask=gradient)
        return overlay

    # ─── Character portrait compositing ─────────────────────────────────

    def _composite_characters(self, canvas: Image.Image, cast_images: list[Image.Image],
                              x_start: int, y_start: int, panel_w: int):
        """Composite character portraits in a row with rounded corners."""
        if not cast_images:
            return

        # Limit to 4 characters max
        cast_images = cast_images[:4]
        count = len(cast_images)

        # Calculate size: fill panel width with small gaps
        gap = 8
        total_gap = gap * (count - 1) if count > 1 else 0
        char_w = min((panel_w - 20 - total_gap) // count, 160)
        char_h = int(char_w * 1.3)  # Portrait aspect ratio

        # Center horizontally in panel
        total_w = (char_w * count) + total_gap
        x = x_start + (panel_w - total_w) // 2

        for img in cast_images:
            portrait = self._fit_crop(img, char_w, char_h)
            portrait = self._round_corners(portrait, 12)
            canvas.paste(portrait, (x, y_start), portrait)
            x += char_w + gap

    # ─── Main generation method ─────────────────────────────────────────

    async def generate(
        self,
        anime_title: str,
        episode: str = "",
        quality: str = "",
        audio: str = "",
        genres_list: list[str] = None,
        airing_day: str = None,
        use_ai_backdrop: bool = True,
    ) -> io.BytesIO:
        """
        Generate a complete banner image.

        Args:
            anime_title: Name of the anime
            episode: Episode string (e.g., "Episode 05")
            quality: Quality label
            audio: Audio type
            genres_list: List of genre strings
            airing_day: Day of the week the anime airs (3-letter, e.g. "Sat")
            use_ai_backdrop: Whether to attempt AI-generated backdrop
        """
        genres_list = genres_list or []

        # Sanitize episode text — ep_no can arrive as list repr or other messy formats
        if episode:
            episode = str(episode)
            # Clean raw list repr like "Episode ['01', '12']" → "Episode 01 - 12"
            if "[" in episode and "]" in episode:
                import re
                nums = re.findall(r"\d+", episode)
                if nums:
                    episode = f"Episode {' - '.join(nums)}"

        # ─── 1. Fetch all TMDB data ────────────────────────────────────
        tmdb_data = await self.tmdb.get_anime_data(anime_title)

        backdrop_img = None
        cast_images = []
        poster_img = None
        studio = "Unknown"
        rating = 0.0

        if tmdb_data:
            # Use TMDB genres if not provided
            if not genres_list:
                genres_list = tmdb_data.get("genres", [])
            if not airing_day:
                airing_day = tmdb_data.get("airing_day")
            studio = tmdb_data.get("studio", "Unknown")
            rating = tmdb_data.get("rating", 0.0)

            # Download backdrop
            backdrop_img = await self._download_image(tmdb_data.get("backdrop_url"))

            # Download poster (for right panel)
            poster_img = await self._download_image(tmdb_data.get("poster_url"))

            # Download character portraits
            if tmdb_data.get("cast"):
                char_urls = [c["profile_url"] for c in tmdb_data["cast"][:4]]
                cast_images = await self._download_multiple(char_urls)

        # ─── AniList fallback when TMDB has no poster/backdrop ─────────
        if not poster_img or not backdrop_img:
            al_url = await self._fetch_anilist_poster(anime_title)
            if al_url:
                al_img = await self._download_image(al_url)
                if al_img:
                    LOGS.info(f"🎨 AniList fallback poster for: {anime_title}")
                    if not poster_img:
                        poster_img = al_img
                    if not backdrop_img:
                        backdrop_img = al_img

        # ─── 2. Attempt AI-generated backdrop ──────────────────────────
        if use_ai_backdrop and not backdrop_img:
            try:
                char_names = []
                if tmdb_data and tmdb_data.get("cast"):
                    char_names = [c["character"] for c in tmdb_data["cast"][:3]]

                prompt = self.puter.craft_anime_prompt(
                    title=anime_title,
                    genres=genres_list,
                    characters=char_names,
                    episode=episode,
                )
                ai_bytes = await self.puter.generate_image(prompt)
                if ai_bytes:
                    backdrop_img = Image.open(io.BytesIO(ai_bytes)).convert("RGBA")
                    LOGS.info(f"✅ AI backdrop generated for: {anime_title}")
            except Exception as e:
                LOGS.error(f"AI backdrop generation failed: {e}")

        # ─── 3. Create Canvas ──────────────────────────────────────────
        canvas = Image.new("RGBA", (self.WIDTH, self.HEIGHT), (25, 25, 25, 255))
        draw = ImageDraw.Draw(canvas)

        # Load fonts
        font_title = _load_font(size=72, font="cal")   # Cal Sans for anime title
        font_subtitle = _load_font(size=36, font="cal")  # Cal Sans for episode/season
        font_body = _load_font(bold=False, size=22)
        font_pill = _load_font(bold=True, size=18)
        font_sidebar = _load_font(size=52, font="cal")
        font_heading = _load_font(bold=True, size=28)
        font_tabs = _load_font(size=20, font="cal")
        font_small = _load_font(bold=False, size=16)

        # ─── 4. LEFT SIDEBAR — "TEAM WARLORDS" ────────────────────────
        draw.rectangle([(0, 0), (self.SIDEBAR_W, self.HEIGHT)], fill="white")

        brand_text = Var.BRAND_UNAME.replace("@", "").upper()
        try:
            # Create text image, rotate 90°
            txt_img = Image.new("RGBA", (self.HEIGHT, self.SIDEBAR_W), (255, 255, 255, 0))
            txt_draw = ImageDraw.Draw(txt_img)

            # Measure text to center
            bbox = txt_draw.textbbox((0, 0), brand_text, font=font_sidebar)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            tx = (self.HEIGHT - tw) // 2
            ty = (self.SIDEBAR_W - th) // 2

            txt_draw.text((tx, ty), brand_text, font=font_sidebar, fill="black")
            rotated = txt_img.rotate(90, expand=True)
            canvas.paste(rotated, (0, 0), rotated)
        except Exception:
            pass

        # ─── 5. MAIN AREA — Backdrop with gradient ────────────────────
        main_x = self.SIDEBAR_W
        main_w = self.WIDTH - self.SIDEBAR_W - self.RIGHT_PANEL_W

        if backdrop_img:
            bg = self._fit_crop(backdrop_img, main_w, self.HEIGHT)
            canvas.paste(bg, (main_x, 0))

        # Dark gradient overlay (bottom-up)
        gradient_overlay = self._make_gradient(main_w, self.HEIGHT)
        canvas.paste(gradient_overlay, (main_x, 0), gradient_overlay)

        # ─── 6. Title Text ─────────────────────────────────────────────
        text_x = main_x + 40
        text_y = self.HEIGHT - 240

        # Word-wrap title if too long
        display_title = anime_title
        if len(display_title) > 22:
            words = display_title.split()
            mid = len(words) // 2
            line1 = " ".join(words[:mid])
            line2 = " ".join(words[mid:])
        else:
            line1 = display_title
            line2 = None

        self._draw_text_outlined(draw, (text_x, text_y), line1, font_title)
        next_y = text_y + 80
        if line2:
            self._draw_text_outlined(draw, (text_x, next_y), line2, font_subtitle)
            next_y += 45

        # Episode/Season subtitle
        if episode:
            self._draw_text_outlined(draw, (text_x, next_y), episode, font_subtitle,
                                     fill=(200, 200, 200))
            next_y += 50

        # "Watch Now" button
        btn_w, btn_h = 180, 50
        btn_x = main_x + main_w - btn_w - 40
        btn_y = self.HEIGHT - 80
        draw.rounded_rectangle(
            [(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)],
            radius=12, outline="white", width=2
        )
        # Center text in button
        btn_bbox = draw.textbbox((0, 0), "Watch Now ▶", font=font_body)
        btn_tw = btn_bbox[2] - btn_bbox[0]
        btn_th = btn_bbox[3] - btn_bbox[1]
        draw.text(
            (btn_x + (btn_w - btn_tw) // 2, btn_y + (btn_h - btn_th) // 2),
            "Watch Now ▶", font=font_body, fill="white"
        )

        # ─── 7. RIGHT PANEL ───────────────────────────────────────────
        right_x = self.WIDTH - self.RIGHT_PANEL_W
        draw.rectangle([(right_x, 0), (self.WIDTH, self.HEIGHT)], fill=(34, 34, 34))

        cur_y = 20

        # --- Navigation Tabs ---
        tabs = ["Main", "Ongoing", "Finished", "Manga"]
        tab_x = right_x + 15
        for tab in tabs:
            bbox = draw.textbbox((0, 0), tab, font=font_tabs)
            tw = bbox[2] - bbox[0]
            draw.text((tab_x, cur_y), tab, font=font_tabs, fill="white")
            tab_x += tw + 22
        cur_y += 50

        # --- Character Portraits / Poster ---
        if cast_images:
            self._composite_characters(canvas, cast_images, right_x, cur_y, self.RIGHT_PANEL_W)
            max_char_h = min(160, int(min((self.RIGHT_PANEL_W - 20) // min(len(cast_images), 4), 160) * 1.3))
            cur_y += max_char_h + 15
        elif poster_img:
            # Use poster as fallback thumbnail
            pw, ph = 350, 180
            poster_crop = self._fit_crop(poster_img, pw, ph)
            poster_crop = self._round_corners(poster_crop, 12)
            canvas.paste(poster_crop, (right_x + (self.RIGHT_PANEL_W - pw) // 2, cur_y), poster_crop)
            cur_y += ph + 15

        # --- GENRES Section ---
        draw.text((right_x + 15, cur_y), "GENRES", font=font_heading, fill="white")
        cur_y += 38

        # Genre pills (2 per row)
        pill_x = right_x + 15
        pill_row_start = pill_x
        pill_w = (self.RIGHT_PANEL_W - 50) // 2
        pill_h = 34
        pill_gap = 10

        for i, genre in enumerate(genres_list[:6]):
            # Draw pill background
            px = pill_row_start + (i % 2) * (pill_w + pill_gap)
            py = cur_y + (i // 2) * (pill_h + pill_gap)

            draw.rounded_rectangle(
                [(px, py), (px + pill_w, py + pill_h)],
                radius=8, fill="white"
            )
            # Center text in pill
            gbbox = draw.textbbox((0, 0), genre, font=font_pill)
            gtw = gbbox[2] - gbbox[0]
            gth = gbbox[3] - gbbox[1]
            draw.text(
                (px + (pill_w - gtw) // 2, py + (pill_h - gth) // 2),
                genre, font=font_pill, fill="black"
            )

        genre_rows = (min(len(genres_list), 6) + 1) // 2
        cur_y += genre_rows * (pill_h + pill_gap) + 15

        # --- Schedule Anime Day ---
        draw.text((right_x + 15, cur_y), "Schedule Anime Day", font=font_heading, fill="white")
        cur_y += 38

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_w = 90
        day_h = 34
        day_gap = 10
        dx = right_x + 15

        for i, day in enumerate(days):
            col = i % 3
            row = i // 3
            bx = dx + col * (day_w + day_gap)
            by = cur_y + row * (day_h + day_gap)

            # Highlight current airing day
            is_active = airing_day and day.lower().startswith(airing_day.lower()[:3])
            if is_active:
                draw.rounded_rectangle(
                    [(bx, by), (bx + day_w, by + day_h)],
                    radius=8, fill=(220, 50, 50)
                )
                text_color = "white"
            else:
                draw.rounded_rectangle(
                    [(bx, by), (bx + day_w, by + day_h)],
                    radius=8, outline="white", width=2
                )
                text_color = "white"

            dbbox = draw.textbbox((0, 0), day, font=font_pill)
            dtw = dbbox[2] - dbbox[0]
            dth = dbbox[3] - dbbox[1]
            draw.text(
                (bx + (day_w - dtw) // 2, by + (day_h - dth) // 2),
                day, font=font_pill, fill=text_color
            )

        day_rows = (len(days) + 2) // 3
        cur_y += day_rows * (day_h + day_gap) + 15

        # --- Rating & Studio Footer ---
        if rating > 0:
            footer = f"Rating: {rating}/10"
            if studio and studio != "Unknown":
                footer += f"  •  Studio: {studio}"
            draw.text((right_x + 15, cur_y), footer, font=font_small, fill=(180, 180, 180))

        # ─── 8. Output ─────────────────────────────────────────────────
        output = io.BytesIO()
        final = canvas.convert("RGB")
        final.save(output, format="PNG", quality=95)
        output.seek(0)
        return output

    async def generate_tmdb(
        self,
        anime_title: str,
        episode: str = "",
    ) -> io.BytesIO:
        """
        Generate a TMDB style poster layout without using AI generation.
        Matches the layout requested: Left=Poster, Right=Title + Synopsis + Metadata.
        """
        # ─── 1. Fetch TMDB data ────────────────────────────────────────
        tmdb_data = await self.tmdb.get_anime_data(anime_title)
        
        poster_img = None
        backdrop_img = None
        rating = 0.0
        synopsis = "No synopsis available."
        genres_list = []
        
        if tmdb_data:
            rating = tmdb_data.get("rating", 0.0)
            genres_list = tmdb_data.get("genres", [])[:4]
            if tmdb_data.get("overview"):
                synopsis = tmdb_data.get("overview")
            
            poster_url = tmdb_data.get("poster_url")
            backdrop_url = tmdb_data.get("backdrop_url")
            
            if poster_url:
                poster_img = await self._download_image(poster_url)

        # ─── AniList fallback when TMDB has no poster ─────────────────
        if not poster_img:
            al_url = await self._fetch_anilist_poster(anime_title)
            if al_url:
                al_img = await self._download_image(al_url)
                if al_img:
                    LOGS.info(f"🎨 AniList fallback poster for TMDB layout: {anime_title}")
                    poster_img = al_img
            
        # Add fallback logic so we always have a backdrop if we have a poster
        if not backdrop_img and poster_img:
            backdrop_img = poster_img

        # ─── 2. Create Canvas (1400x880) ───────────────────────────────
        canvas = Image.new("RGBA", (1400, 880), (28, 28, 28, 255))
        draw = ImageDraw.Draw(canvas)
        
        # Load fonts - Matching elegant bold fonts for mockup
        font_huge = _load_font(size=64, font="cal")    # Cal Sans for anime title
        font_title = _load_font(size=40, font="cal")   # Cal Sans for overflow title
        font_sub = _load_font(size=22, font="cal")     # Cal Sans for "Synopsis :" label
        font_body = _load_font(size=18, font="mono")   # Superior Mono for synopsis body
        font_small = _load_font(bold=True, size=12)
        font_btn = _load_font(bold=True, size=18)
        font_pill = _load_font(bold=True, size=14)
        
        # Fonts for header (Cal Sans)
        font_logo = _load_font(size=40, font="cal")
        font_nav = _load_font(size=20, font="cal")
        
        # ─── Top Header Navbar ─────────────────────────────────────────
        header_h = 80
        draw.rectangle([(0, 0), (1400, header_h)], fill=(34, 34, 34, 255))
        
        # Logo text
        draw.text((40, 20), "TEAM WARLORDS", font=font_logo, fill="white")
        
        # Nav Links — highlight based on anime status from TMDB
        anime_status = (tmdb_data.get("status", "") if tmdb_data else "").lower()
        is_ongoing = "returning" in anime_status  # "Returning Series"
        is_finished = "ended" in anime_status or "canceled" in anime_status
        nav_links = [
            ("Main", not is_ongoing and not is_finished),
            ("Ongoing", is_ongoing),
            ("Finished", is_finished),
            ("Manga", False),
        ]
        nav_x = 800
        for text, active in nav_links:
            nav_bbox = draw.textbbox((0, 0), text, font=font_nav)
            nav_w = nav_bbox[2] - nav_bbox[0]
            color = "white" if active else (200, 200, 200)
            draw.text((nav_x, 30), text, font=font_nav, fill=color)
            if active:
                draw.rectangle([(nav_x, 58), (nav_x + nav_w, 61)], fill="white")
            nav_x += nav_w + 65
            
        # Hamburger menu icon
        ham_x = 1320
        ham_y = 32
        for i in range(2): # The mockup shows two lines for the hamburger menu
            draw.rectangle([(ham_x, ham_y + i*10), (ham_x + 30, ham_y + i*10 + 2)], fill="white")

        # ─── 3. Left Panel (Poster View) ───────────────────────────────
        left_w = 480
        if poster_img:
            # Crop/Resize poster to fit the exact left dimensions
            poster = self._fit_crop(poster_img, left_w, 800)
            canvas.paste(poster, (0, header_h))
        else:
            # Fallback rectangle if no poster
            draw.rectangle([(0, header_h), (left_w, 800 + header_h)], fill=(40, 40, 40))
            draw.text((100, 330 + header_h), "NO IMAGE FOUND", font=font_title, fill=(100, 100, 100))

        # Helper method for exact text wrapping
        def get_wrapped_text(text, font, max_width):
            words = text.split()
            lines = []
            current_line = []
            for word in words:
                current_line.append(word)
                w = draw.textbbox((0, 0), " ".join(current_line), font=font)[2]
                if w > max_width:
                    current_line.pop()
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
            return lines

        # ─── 4. Right Panel (Text & Info) ──────────────────────────────
        right_x = left_w + 40
        right_w = 1400 - right_x - 40
        cur_y = header_h + 60

        # Title Handling (Huge bold wrapper)
        display_title = anime_title
        if "Season " in display_title:
            base, s_num = display_title.split("Season ", 1)
            display_title = f"{base.strip()}\nSeason {s_num}"
            
        lines = display_title.split('\n')
        wrapped_lines = []
        for line in lines:
            wrapped_lines.extend(get_wrapped_text(line, font_huge, right_w))
            
        for line in wrapped_lines[:2]:
            self._draw_text_outlined(draw, (right_x, cur_y), line, font_huge)
            cur_y += 70
            
        if len(wrapped_lines) > 2:
            self._draw_text_outlined(draw, (right_x, cur_y), wrapped_lines[2] + "...", font_title)
            cur_y += 50

        # Subtitle (Episode / Season text)
        cur_y += 15
        clean_ep = str(episode).replace("['", "").replace("']", "")
        sub_text = f"▶  Synopsis : {clean_ep}" if clean_ep else "▶  Synopsis :"
        draw.text((right_x, cur_y), sub_text, font=font_sub, fill="white")
        cur_y += 35

        # Synopsis Body
        syn_lines = get_wrapped_text(synopsis, font_body, right_w)
        max_lines = 5
        for i, line in enumerate(syn_lines[:max_lines]):
            if i == max_lines - 1 and len(syn_lines) > max_lines:
                line = line + "..."
            draw.text((right_x, cur_y), line, font=font_body, fill=(230, 230, 230))
            cur_y += 28

        # "Watch Now" Button (Appears directly below synopsis)
        cur_y += 20
        btn_w, btn_h = 160, 40
        btn_x = right_x
        draw.rounded_rectangle([(btn_x, cur_y), (btn_x+btn_w, cur_y+btn_h)], radius=20, fill="white")
        bbox = draw.textbbox((0, 0), "Watch Now", font=font_btn)
        draw.text(
            (btn_x + (btn_w - (bbox[2]-bbox[0]))//2, cur_y + (btn_h - (bbox[3]-bbox[1]))//2 - 2),
            "Watch Now", font=font_btn, fill="black"
        )
        cur_y += btn_h # Add button height to current Y

        # ─── 5. Bottom Right Graphic Boxes ─────────────────────────────
        # Box 1: Backdrop Image Preview
        box_y = max(header_h + 500, cur_y + 40)
        box_h = 240
        box1_w = 400
        box1_x = right_x
        
        if backdrop_img:
            # Create rounded masking for the backdrop box
            b_bg = self._fit_crop(backdrop_img, box1_w, box_h)
            b_mask = Image.new("L", (box1_w, box_h), 0)
            ImageDraw.Draw(b_mask).rounded_rectangle([(0, 0), (box1_w, box_h)], radius=15, fill=255)
            b_comp = Image.composite(b_bg, Image.new("RGBA", (box1_w, box_h), (0,0,0,0)), b_mask)
            canvas.paste(b_comp, (box1_x, box_y), b_comp)
        else:
            # Fallback darkened box
            draw.rounded_rectangle([(box1_x, box_y), (box1_x+box1_w, box_y+box_h)], radius=15, fill=(45, 45, 45))

        # Box 2: Genre Info Block
        box2_x = box1_x + box1_w + 30
        box2_w = 1400 - box2_x - 40 # Fill remaining spacing (~410px)
        
        # Darkened/blurred backdrop as background for genres
        if backdrop_img:
            g_bg = self._fit_crop(backdrop_img, box2_w, box_h)
            g_bg = g_bg.transpose(Image.FLIP_LEFT_RIGHT) # Mirror it to differentiate from box 1
        else:
            g_bg = Image.new("RGBA", (box2_w, box_h), (45, 45, 45, 255))
            
        g_mask = Image.new("L", (box2_w, box_h), 0)
        ImageDraw.Draw(g_mask).rounded_rectangle([(0, 0), (box2_w, box_h)], radius=15, fill=255)
        
        # Add translucent dark overlay for text readability
        overlay = Image.new("RGBA", (box2_w, box_h), (30, 30, 30, 150))
        g_bg = Image.alpha_composite(g_bg.convert("RGBA"), overlay)
        
        g_comp = Image.composite(g_bg, Image.new("RGBA", (box2_w, box_h), (0,0,0,0)), g_mask)
        canvas.paste(g_comp, (box2_x, box_y), g_comp)
        
        b_draw = ImageDraw.Draw(canvas)
        
        # "GENRES" title
        gtitle = "G E N R E S"
        gtitle_bbox = b_draw.textbbox((0,0), gtitle, font=font_sub)
        b_draw.text((box2_x + (box2_w - gtitle_bbox[2])//2, box_y + 15), gtitle, font=font_sub, fill="white")
        
        # 3x2 Pills Grid Layout
        gx, gy = box2_x + 15, box_y + 55
        gw, gh = (box2_w - 40) // 2, 30
        gap = 10
        
        six_genres = (genres_list + [".................."] * 6)[:6]
        
        for i, genre in enumerate(six_genres):
            row = i // 2
            col = i % 2
            
            px = gx + col * (gw + gap)
            py = gy + row * (gh + gap)
            
            b_draw.rounded_rectangle([(px, py), (px+gw, py+gh)], radius=15, outline=(200, 200, 200), width=1)
            
            genre_text = genre
            gbox = b_draw.textbbox((0, 0), genre_text, font=font_pill)
            # Truncate logic
            if gbox[2] > gw - 15:
                while len(genre_text) > 3 and b_draw.textbbox((0, 0), genre_text + "..", font=font_pill)[2] > gw - 15:
                    genre_text = genre_text[:-1]
                genre_text += ".."
                gbox = b_draw.textbbox((0, 0), genre_text, font=font_pill)
            
            b_draw.text(
                (px + (gw - gbox[2])//2, py + (gh - (gbox[3]-gbox[1]))//2),
                genre_text, font=font_pill, fill="white"
            )
            
        footer_y = box_y + box_h - 25
        studio = tmdb_data.get("studio", "Unknown") if tmdb_data else "Unknown"
        b_draw.text((box2_x + 20, footer_y), f"Rating: {rating}/10 By TMDB", font=font_small, fill=(220,220,220))
        
        # Right aligned studio text
        s_box = b_draw.textbbox((0, 0), f"Studios: {studio}", font=font_small)
        b_draw.text((box2_x + box2_w - s_box[2] - 20, footer_y), f"Studios: {studio}", font=font_small, fill=(220,220,220))
        
        # ─── 5. Return Output ──────────────────────────────────────────
        output = io.BytesIO()
        final = canvas.convert("RGB")
        final.save(output, format="PNG", quality=95)
        output.seek(0)
        return output
