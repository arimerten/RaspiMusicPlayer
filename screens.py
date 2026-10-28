"""
Screen drawing code shared by the laptop simulator (desktop.py) and the Pi (pi.py).

Every function here returns a PIL image sized for the 320x240 (landscape) screen.
Keep Pi-only imports (board, digitalio, gpiozero, adafruit_*) out of this file
so it runs the same on both machines.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
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

# Radio colours: an old wooden set with a cream dial and amber display
WOOD = (96, 58, 32)
WOOD_DARK = (50, 29, 15)
BRASS = (200, 164, 90)
DIAL_FACE = (238, 224, 188)
DIAL_INK = (70, 45, 25)
NEEDLE = (205, 40, 30)
AMBER = (255, 170, 40)
AMBER_DIM = (75, 45, 15)
DISPLAY_BG = (28, 16, 8)
KEY_FACE = (232, 222, 196)
KEY_SIDE = (140, 122, 95)
KEY_PRESSED = (196, 184, 156)

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

# FM band, in tenths of a MHz so 1057 means 105.7 MHz (whole numbers avoid rounding errors)
FM_MIN = 875
FM_MAX = 1080
DIAL = (MARGIN, 28, WIDTH - MARGIN - 1, 112)
SCALE_LEFT = 30
SCALE_RIGHT = WIDTH - 30
SCALE_Y = 74
FREQ_BOX = (MARGIN, 120, 196, 176)
VOL_BOX = (204, 120, WIDTH - MARGIN - 1, 176)
RADIO_KEYS_SHOWN = 4
KEY_GAP = 8
KEY_WIDTH = (WIDTH - 2 * MARGIN - (RADIO_KEYS_SHOWN - 1) * KEY_GAP) // RADIO_KEYS_SHOWN
KEY_TOP = 186
KEY_BOTTOM = 226
KEY_DEPTH = 5  # how far a raised key sticks up


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


def format_mhz(tenths):
    return f"{tenths // 10}.{tenths % 10}"


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


def dial_x(tenths):
    """x position of a frequency on the tuning scale."""
    return round(SCALE_LEFT + (tenths - FM_MIN) * (SCALE_RIGHT - SCALE_LEFT) / (FM_MAX - FM_MIN))


@lru_cache(maxsize=1)
def radio_background():
    """The parts of the radio screen that never change, drawn once: wood, dial scale, display boxes."""
    frame = Image.new("RGB", (WIDTH, HEIGHT), WOOD)
    draw = ImageDraw.Draw(frame)

    # Wood grain: rows of slightly lighter and darker brown in uneven waves
    for y in range(HEIGHT):
        shade = int(9 * math.sin(y * 0.31 + 3 * math.sin(y * 0.047)) + 4 * math.sin(y * 1.7))
        draw.line((0, y, WIDTH - 1, y), fill=tuple(max(0, c + shade) for c in WOOD))
    draw.rectangle((0, 0, WIDTH - 1, 21), fill=WOOD_DARK)
    draw.line((0, 22, WIDTH - 1, 22), fill=BRASS)

    # Dial: cream face, brass rim, scale ticks every 0.5 MHz with numbers every 4 MHz
    draw.rounded_rectangle(DIAL, radius=6, fill=DIAL_FACE, outline=BRASS, width=2)
    number_font = load_font(12, bold=True)
    for tenths in range(880, FM_MAX + 1, 5):
        x = dial_x(tenths)
        length = 14 if tenths % 40 == 0 else 9 if tenths % 10 == 0 else 5
        draw.line((x, SCALE_Y - length, x, SCALE_Y), fill=DIAL_INK)
        if tenths % 40 == 0:
            draw.text((x, SCALE_Y + 5), str(tenths // 10), font=number_font, fill=DIAL_INK, anchor="mt")
    draw.line((SCALE_LEFT, SCALE_Y, SCALE_RIGHT, SCALE_Y), fill=DIAL_INK)
    small_font = load_font(10, bold=True)
    draw.text((DIAL[0] + 8, DIAL[1] + 6), "FM", font=small_font, fill=DIAL_INK)
    draw.text((DIAL[2] - 8, DIAL[1] + 6), "MHz", font=small_font, fill=DIAL_INK, anchor="ra")

    for box in (FREQ_BOX, VOL_BOX):
        draw.rounded_rectangle(box, radius=5, fill=DISPLAY_BG, outline=BRASS, width=2)
    return frame


def draw_radio_key(draw, left, label, focused, pressed, lit):
    """A push-button key. Raised normally, sunk in when pressed, amber when lit (being adjusted)."""
    right = left + KEY_WIDTH - 1
    draw.rounded_rectangle((left, KEY_TOP + KEY_DEPTH, right, KEY_BOTTOM + KEY_DEPTH), radius=4, fill=KEY_SIDE)
    top = KEY_TOP + (KEY_DEPTH - 1 if pressed or lit else 0)
    face = AMBER if lit else KEY_PRESSED if pressed else KEY_FACE
    box = (left, top, right, top + KEY_BOTTOM - KEY_TOP)
    draw.rounded_rectangle(box, radius=4, fill=face,
                           outline=AMBER if focused and not lit else None, width=3)
    if focused and lit:
        draw.rounded_rectangle(box, radius=4, outline=DISPLAY_BG, width=2)
    draw.text((left + KEY_WIDTH // 2, (box[1] + box[3]) // 2), label,
              font=load_font(14, bold=True), fill=DIAL_INK, anchor="mm")


def render_radio(frequency, favourites, keys, focus, adjusting, volume, now=None):
    """
    Old-school FM radio. frequency and favourites are in tenths of a MHz.
    keys are the labels along the bottom; focus is the selected one, and
    adjusting is True while the knob is turning the focused key's setting.
    """
    now = now or datetime.now()
    frame = radio_background().copy()
    draw = ImageDraw.Draw(frame)

    header_font = load_font(12, bold=True)
    draw.text((MARGIN, 11), f"VOL {volume}%", font=header_font, fill=BRASS, anchor="lm")
    draw.text((WIDTH // 2, 11), "FM RADIO", font=header_font, fill=BRASS, anchor="mm")
    draw.text((WIDTH - MARGIN, 11), format_clock(now), font=header_font, fill=BRASS, anchor="rm")

    # Favourites marked above the scale, then the red needle
    for favourite in favourites:
        x = dial_x(favourite)
        draw.polygon(((x - 4, 44), (x + 4, 44), (x, 50)), fill=BRASS)
    x = dial_x(frequency)
    draw.rectangle((x - 1, DIAL[1] + 4, x + 1, DIAL[3] - 4), fill=NEEDLE)

    # Frequency readout, with unlit "188.8" segments behind it like an old display
    tuning = adjusting and keys[focus] == "TUNE"
    draw.text((FREQ_BOX[0] + 8, FREQ_BOX[1] + 6), "TUNING", font=load_font(9, bold=True),
              fill=AMBER if tuning else AMBER_DIM)
    digit_font = load_font(34, bold=True)
    digits_right = FREQ_BOX[2] - 44
    draw.text((digits_right, FREQ_BOX[3] - 8), "188.8", font=digit_font, fill=AMBER_DIM, anchor="rs")
    draw.text((digits_right, FREQ_BOX[3] - 8), format_mhz(frequency), font=digit_font, fill=AMBER, anchor="rs")
    draw.text((digits_right + 6, FREQ_BOX[3] - 8), "MHz", font=load_font(12, bold=True), fill=AMBER, anchor="ls")

    # Volume: ten bars that light up
    adjusting_volume = adjusting and keys[focus] == "VOL"
    draw.text(((VOL_BOX[0] + VOL_BOX[2]) // 2, VOL_BOX[1] + 6), "VOLUME", font=load_font(9, bold=True),
              fill=AMBER if adjusting_volume else AMBER_DIM, anchor="mt")
    bar_width = 7
    bars_left = (VOL_BOX[0] + VOL_BOX[2]) // 2 - (10 * bar_width + 9 * 2) // 2
    for i in range(10):
        left = bars_left + i * (bar_width + 2)
        height = 8 + i * 2
        lit = volume >= (i + 1) * 10
        draw.rectangle((left, VOL_BOX[3] - 8 - height, left + bar_width - 1, VOL_BOX[3] - 8),
                       fill=AMBER if lit else AMBER_DIM)

    # Keys along the bottom; if there are too many to fit, the focused one stays in view
    first = max(0, min(focus - RADIO_KEYS_SHOWN + 1, len(keys) - RADIO_KEYS_SHOWN))
    for i, label in enumerate(keys[first:first + RADIO_KEYS_SHOWN]):
        index = first + i
        left = MARGIN + i * (KEY_WIDTH + KEY_GAP)
        pressed = label == format_mhz(frequency)  # the favourite that's tuned in stays pushed down
        draw_radio_key(draw, left, label, index == focus, pressed, adjusting and index == focus)
    return frame
