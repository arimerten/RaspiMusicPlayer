"""
Screen drawing code shared by the laptop simulator (desktop.py) and the Pi (pi.py).

Every function here returns a PIL image sized for the 320x240 (landscape) screen.
Keep Pi-only imports (board, digitalio, gpiozero, adafruit_*) out of this file
so it runs the same on both machines.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from library import load_album_art

WIDTH = 320
HEIGHT = 240

ASSETS = Path(__file__).parent / "assets"
FONT_REGULAR = ASSETS / "fonts" / "DejaVuSans.ttf"
FONT_BOLD = ASSETS / "fonts" / "DejaVuSans-Bold.ttf"

# Colours
BACKGROUND = (0, 0, 0)
TEXT = (255, 255, 255)
TEXT_DIM = (150, 150, 150)
STATUS_BG = (30, 30, 30)
DIVIDER = (80, 80, 80)
MISSING_BG = (35, 35, 35)
MISSING_TEXT = (220, 60, 60)
HIGHLIGHT = (40, 90, 160)
SCROLLBAR = (110, 110, 110)

# Layout
STATUS_HEIGHT = 24
MARGIN = 12
ART_SIZE = 150
ART_LEFT = MARGIN
ART_TOP = STATUS_HEIGHT + (HEIGHT - STATUS_HEIGHT - ART_SIZE) // 2
INFO_LEFT = ART_LEFT + ART_SIZE + MARGIN
INFO_WIDTH = WIDTH - INFO_LEFT - MARGIN
VISIBLE_ROWS = 6
ROW_HEIGHT = (HEIGHT - STATUS_HEIGHT) // VISIBLE_ROWS
SCROLLBAR_WIDTH = 4


@dataclass
class Track:
    title: str
    artist: str
    album: str = ""
    genre: str = ""
    path: str | None = None      # path to the song file; album art is found from this
    position: int = 0            # seconds into the song
    duration: int = 0            # song length in seconds
    playing: bool = True


_font_cache = {}


def load_font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)
    return _font_cache[key]


def fit_text(text, font, max_width):
    """Shorten text with '...' so it fits within max_width pixels."""
    if font.getlength(text) <= max_width:
        return text
    while text and font.getlength(text + "...") > max_width:
        text = text[:-1]
    return text.rstrip() + "..."


def wrap_text(text, font, max_width, max_lines):
    """Split text into lines that fit max_width, shortening the last line with '...' if needed."""
    lines = []
    words = text.split()
    while words and len(lines) < max_lines:
        line = words.pop(0)
        while words and font.getlength(line + " " + words[0]) <= max_width:
            line += " " + words.pop(0)
        lines.append(line)
    if words:  # ran out of lines with words left over
        lines[-1] = lines[-1] + " " + " ".join(words)
    return [fit_text(line, font, max_width) for line in lines]


def format_time(seconds):
    return f"{seconds // 60}:{seconds % 60:02d}"


def format_clock(now):
    hour = now.hour % 12 or 12
    return f"{hour}:{now.minute:02d} {'am' if now.hour < 12 else 'pm'}"


def format_date(now):
    return f"{now:%a} {now.day} {now:%b}"


def draw_status_bar(draw, volume, now):
    """Top bar: volume | time | date, in three equal sections."""
    draw.rectangle((0, 0, WIDTH - 1, STATUS_HEIGHT - 1), fill=STATUS_BG)
    font = load_font(12, bold=True)
    section = WIDTH // 3
    middle_y = STATUS_HEIGHT // 2
    texts = [f"VOL {volume}%", format_clock(now), format_date(now)]
    for i, text in enumerate(texts):
        draw.text((section * i + section // 2, middle_y), text, font=font, fill=TEXT, anchor="mm")
    for i in (1, 2):
        draw.line((section * i, 5, section * i, STATUS_HEIGHT - 6), fill=DIVIDER, width=1)


def draw_missing_art(draw, left, top, size):
    draw.rectangle((left, top, left + size - 1, top + size - 1), fill=MISSING_BG, outline=MISSING_TEXT, width=2)
    font = load_font(16, bold=True)
    centre_x = left + size // 2
    middle = top + size // 2
    draw.text((centre_x, middle - 2), "MISSING", font=font, fill=MISSING_TEXT, anchor="mb")
    draw.text((centre_x, middle + 2), "ALBUM ART", font=font, fill=MISSING_TEXT, anchor="mt")


def render_now_playing(track, volume, now=None):
    now = now or datetime.now()
    frame = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(frame)

    draw_status_bar(draw, volume, now)

    # Album art (or placeholder) on the left
    art = load_album_art(track.path, ART_SIZE)
    if art:
        frame.paste(art, (ART_LEFT, ART_TOP))
    else:
        draw_missing_art(draw, ART_LEFT, ART_TOP, ART_SIZE)

    # Name (up to 2 lines), album and genre on the right, lined up with the top of the art
    name_font = load_font(17, bold=True)
    detail_font = load_font(13)
    y = ART_TOP
    for line in wrap_text(track.title, name_font, INFO_WIDTH, max_lines=2):
        draw.text((INFO_LEFT, y), line, font=name_font, fill=TEXT)
        y += 22
    y += 6
    for detail in (track.album, track.genre):
        draw.text((INFO_LEFT, y), fit_text(detail, detail_font, INFO_WIDTH), font=detail_font, fill=TEXT_DIM)
        y += 19

    # Position / length, lined up with the bottom of the art
    time_text = f"{format_time(track.position)}/{format_time(track.duration)}"
    draw.text((INFO_LEFT, ART_TOP + ART_SIZE), time_text, font=load_font(16, bold=True), fill=TEXT, anchor="ld")

    return frame


def render_list(title, rows, selected, top, now=None, empty_text="Nothing here"):
    """
    A scrollable menu. rows is a list of (label, detail) pairs; detail may be "".
    selected is the highlighted row and top is the first row on screen.
    """
    now = now or datetime.now()
    frame = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(frame)

    # Header: page title on the left, clock on the right
    draw.rectangle((0, 0, WIDTH - 1, STATUS_HEIGHT - 1), fill=STATUS_BG)
    header_font = load_font(12, bold=True)
    clock = format_clock(now)
    middle_y = STATUS_HEIGHT // 2
    draw.text((WIDTH - MARGIN, middle_y), clock, font=header_font, fill=TEXT, anchor="rm")
    title_width = WIDTH - 3 * MARGIN - header_font.getlength(clock)
    draw.text((MARGIN, middle_y), fit_text(title, header_font, title_width), font=header_font, fill=TEXT, anchor="lm")

    if not rows:
        draw.text((WIDTH // 2, (HEIGHT + STATUS_HEIGHT) // 2), empty_text,
                  font=load_font(14), fill=TEXT_DIM, anchor="mm")
        return frame

    scrolling = len(rows) > VISIBLE_ROWS
    text_width = WIDTH - 2 * MARGIN - (SCROLLBAR_WIDTH + 4 if scrolling else 0)
    label_font = load_font(14, bold=True)
    detail_font = load_font(11)
    for i, (label, detail) in enumerate(rows[top:top + VISIBLE_ROWS]):
        y = STATUS_HEIGHT + i * ROW_HEIGHT
        if top + i == selected:
            draw.rectangle((0, y, WIDTH - 1, y + ROW_HEIGHT - 1), fill=HIGHLIGHT)
        else:
            draw.line((MARGIN, y + ROW_HEIGHT - 1, WIDTH - MARGIN, y + ROW_HEIGHT - 1), fill=STATUS_BG)
        if detail:
            draw.text((MARGIN, y + 4), fit_text(label, label_font, text_width), font=label_font, fill=TEXT)
            draw.text((MARGIN, y + 21), fit_text(detail, detail_font, text_width), font=detail_font,
                      fill=TEXT if top + i == selected else TEXT_DIM)
        else:
            draw.text((MARGIN, y + ROW_HEIGHT // 2), fit_text(label, label_font, text_width),
                      font=label_font, fill=TEXT, anchor="lm")

    # Scrollbar: the thumb's size and position show which part of the list is on screen
    if scrolling:
        track_top = STATUS_HEIGHT + 2
        track_height = HEIGHT - track_top - 2
        thumb_height = max(12, track_height * VISIBLE_ROWS // len(rows))
        thumb_top = track_top + (track_height - thumb_height) * top // (len(rows) - VISIBLE_ROWS)
        x = WIDTH - SCROLLBAR_WIDTH - 2
        draw.rectangle((x, thumb_top, x + SCROLLBAR_WIDTH - 1, thumb_top + thumb_height - 1), fill=SCROLLBAR)

    return frame
