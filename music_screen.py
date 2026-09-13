"""
Simple sanity-check test: black background with some shapes and text,
just to confirm the screen and wiring are working correctly.

Wiring (BCM numbering):
  VCC  -> 3.3V          GND -> GND
  CS   -> GPIO8 (CE0)   RESET -> GPIO25
  DC   -> GPIO24        SDI -> GPIO10 (MOSI)
  SCK  -> GPIO11        LED -> 3.3V

Install once (on the Pi):
  sudo raspi-config              # Interface Options -> SPI -> Enable, then reboot
  sudo apt update
  sudo apt install -y python3-pip python3-pil
  pip3 install --upgrade adafruit-blinka adafruit-circuitpython-rgb-display

If the screen stays blank or shows garbled colors, try flipping the
USE_ST7789 flag below to switch chips.
"""

import board
import digitalio
from PIL import Image, ImageDraw

# --- Pick the correct chip here ---
USE_ST7789 = True  # set to True for ST7789, False for ILI9341

if USE_ST7789:
    from adafruit_rgb_display import st7789
    DriverClass = st7789.ST7789
else:
    from adafruit_rgb_display import ili9341
    DriverClass = ili9341.ILI9341

WIDTH = 240
HEIGHT = 320
BAUDRATE = 24_000_000  # lower to 4_000_000 if the image is unstable

# --- Set up the display ---
cs_pin = digitalio.DigitalInOut(board.CE0)
dc_pin = digitalio.DigitalInOut(board.D24)
reset_pin = digitalio.DigitalInOut(board.D25)
spi = board.SPI()

display_kwargs = dict(
    cs=cs_pin,
    dc=dc_pin,
    rst=reset_pin,
    baudrate=BAUDRATE,
    width=WIDTH,
    height=HEIGHT,
    rotation=0,  # try 90, 180, or 270 if the image is sideways/upside down
)

# Only ST7789 needs these -- ILI9341 doesn't accept them
if USE_ST7789:
    display_kwargs["x_offset"] = 0
    display_kwargs["y_offset"] = 0

disp = DriverClass(spi, **display_kwargs)

# Many ST7789 panels ship with inversion needing to be toggled from the
# library's default. White background + wrong colors (e.g. green shows as
# purple) is the classic symptom -- this line fixes it.
if USE_ST7789:
    disp.write(0x20)  # Display Inversion ON
    # If this makes colors WORSE instead of better, use 0x20 (Inversion OFF) instead

# --- Draw: black background, a circle, a square, and some text ---
frame = Image.new("RGB", (WIDTH, HEIGHT), "black")
draw = ImageDraw.Draw(frame)

draw.ellipse((40, 40, 160, 160), outline=(0, 255, 0), width=4)       # circle
draw.rectangle((40, 190, 200, 280), outline=(255, 0, 0), width=4)    # square
draw.text((10, 10), "Hello, Pi!", fill=(255, 255, 255))              # text

# --- Send it to the screen ---
disp.image(frame)
print("Done -- shapes and text sent to the display.")
