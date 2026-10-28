"""
Screen drawing code shared by the laptop simulator (desktop.py) and the Pi (pi.py).

Every function here returns a PIL image sized for the 320x240 (landscape) screen.
Keep Pi-only imports (board, digitalio, gpiozero, adafruit_*) out of this file
so it runs the same on both machines.
"""

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

# Radio colours: an old-school set with a cream dial, brass trim and amber display
BRASS = (200, 164, 90)
DIAL_FACE = (238, 224, 188)
DIAL_INK = (70, 45, 25)
NEEDLE = (205, 40, 30)
AMBER = (255, 170, 40)
DISPLAY_BG = (28, 16, 8)
KEY_FACE = (232, 222, 196)
KEY_SIDE = (140, 122, 95)

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
FREQ_BOX = (MARGIN, 120, WIDTH - MARGIN - 1, 180)
KEY_BOX = (MARGIN, 190, WIDTH - MARGIN - 1, 224)
FAVOURITES_BOX = (50, 34, WIDTH - 51, HEIGHT - 11)  # the pop-up list
FAVOURITE_ROWS = 5
FAVOURITE_ROW_HEIGHT = 32


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
    """The parts of the radio screen that never change, drawn once: header, dial scale, display, key."""
    frame = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(frame)
    draw.line((0, 22, WIDTH - 1, 22), fill=BRASS)
    draw.text((MARGIN, 11), "FM RADIO", font=load_font(12, bold=True), fill=BRASS, anchor="lm")

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

    draw.rounded_rectangle(FREQ_BOX, radius=5, fill=DISPLAY_BG, outline=BRASS, width=2)

    # Push-button key: pressing the knob opens the favourites
    left, top, right, bottom = KEY_BOX
    draw.rounded_rectangle((left, top + 4, right, bottom + 4), radius=4, fill=KEY_SIDE)
    draw.rounded_rectangle(KEY_BOX, radius=4, fill=KEY_FACE)
    draw.text(((left + right) // 2, (top + bottom) // 2), "★ FAVOURITES", font=load_font(14, bold=True),
              fill=DIAL_INK, anchor="mm")
    return frame


def draw_favourites(draw, frequency, favourites, selected):
    """Pop-up list of favourite stations over the radio screen."""
    left, top, right, bottom = FAVOURITES_BOX
    draw.rounded_rectangle(FAVOURITES_BOX, radius=6, fill=BACKGROUND, outline=BRASS, width=2)
    draw.text(((left + right) // 2, top + 13), "★ FAVOURITES", font=load_font(12, bold=True),
              fill=BRASS, anchor="mm")
    draw.line((left + 8, top + 26, right - 8, top + 26), fill=BRASS)

    # If there are more favourites than fit, the selected one stays in view
    first = max(0, min(selected - FAVOURITE_ROWS + 1, len(favourites) - FAVOURITE_ROWS))
    font = load_font(18, bold=True)
    for i, favourite in enumerate(favourites[first:first + FAVOURITE_ROWS]):
        y = top + 30 + i * FAVOURITE_ROW_HEIGHT
        row = (left + 6, y, right - 6, y + FAVOURITE_ROW_HEIGHT - 4)
        middle_y = (row[1] + row[3]) // 2
        chosen = first + i == selected
        if chosen:
            draw.rounded_rectangle(row, radius=4, fill=AMBER)
        colour = BACKGROUND if chosen else AMBER
        draw.text(((left + right) // 2, middle_y), f"{format_mhz(favourite)} MHz", font=font, fill=colour, anchor="mm")
        if favourite == frequency:  # dot next to the station that's tuned in now
            draw.ellipse((row[0] + 8, middle_y - 3, row[0] + 14, middle_y + 3), fill=colour)


def render_radio(frequency, favourites, favourites_open, selected, now=None):
    """
    Old-school FM radio. frequency and favourites are in tenths of a MHz.
    When favourites_open, the favourites list pops up with row `selected` highlighted.
    """
    now = now or datetime.now()
    frame = radio_background().copy()
    draw = ImageDraw.Draw(frame)
    draw.text((WIDTH - MARGIN, 11), format_clock(now), font=load_font(12, bold=True), fill=BRASS, anchor="rm")

    # Favourites marked above the scale, then the red needle
    for favourite in favourites:
        x = dial_x(favourite)
        draw.polygon(((x - 4, 44), (x + 4, 44), (x, 50)), fill=BRASS)
    x = dial_x(frequency)
    draw.rectangle((x - 1, DIAL[1] + 4, x + 1, DIAL[3] - 4), fill=NEEDLE)

    # Frequency readout
    centre_x = (FREQ_BOX[0] + FREQ_BOX[2]) // 2
    baseline = FREQ_BOX[3] - 12
    draw.text((centre_x + 24, baseline), format_mhz(frequency), font=load_font(40, bold=True), fill=AMBER, anchor="rs")
    draw.text((centre_x + 30, baseline), "MHz", font=load_font(14, bold=True), fill=AMBER, anchor="ls")

    if favourites_open:
        draw_favourites(draw, frequency, favourites, selected)
    return frame
