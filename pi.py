"""
Runs the player on the real ST7789 display, controlled by a rotary knob. Pi only.

Run from the project folder:
  ~/.venv/bin/python3 pi.py

Turn the knob to scroll or change volume, press to select or play/pause,
hold to go back (see app.py). Ctrl+C to stop.

Wiring (BCM numbering):
  Screen: VCC -> 3.3V          GND -> GND
          CS  -> GPIO8 (CE0)   RESET -> GPIO25
          DC  -> GPIO24        SDI -> GPIO10 (MOSI)
          SCK -> GPIO11        LED -> 3.3V
  Knob (KY-040 style): CLK -> GPIO5, DT -> GPIO6, SW -> GPIO13, + -> 3.3V, GND -> GND
"""

import queue
import time

import board
import digitalio
from adafruit_rgb_display import st7789
from gpiozero import Button, RotaryEncoder

from app import App

BAUDRATE = 24_000_000  # lower to 4_000_000 if the image is unstable

KNOB_A = 5        # CLK
KNOB_B = 6        # DT
KNOB_BUTTON = 13  # SW
HOLD_SECONDS = 0.6  # holding the knob this long counts as "back"

# The panel is 240x320 in portrait; rotating it 90 degrees gives the 320x240 landscape screen
PANEL_WIDTH = 240
PANEL_HEIGHT = 320
ROTATION = 90  # use 270 if the picture is upside down


def setup_display():
    disp = st7789.ST7789(
        board.SPI(),
        cs=digitalio.DigitalInOut(board.CE0),
        dc=digitalio.DigitalInOut(board.D24),
        rst=digitalio.DigitalInOut(board.D25),
        baudrate=BAUDRATE,
        width=PANEL_WIDTH,
        height=PANEL_HEIGHT,
        rotation=ROTATION,
        x_offset=0,
        y_offset=0,
    )
    disp.write(0x20)  # Display Inversion OFF -- fixes white background / wrong colours on this panel
    return disp


def setup_knob(events):
    """Put "turn+1", "turn-1", "press" and "back" on the events queue from the knob's callbacks."""
    knob = RotaryEncoder(KNOB_A, KNOB_B, max_steps=0)
    knob.when_rotated_clockwise = lambda: events.put("turn+1")
    knob.when_rotated_counter_clockwise = lambda: events.put("turn-1")

    button = Button(KNOB_BUTTON, hold_time=HOLD_SECONDS)
    held = False

    def on_held():
        nonlocal held
        held = True
        events.put("back")

    def on_released():
        nonlocal held
        if not held:
            events.put("press")  # a short press; a long one already sent "back"
        held = False

    button.when_held = on_held
    button.when_released = on_released
    return knob, button  # keep references, or gpiozero closes the pins


def handle(app, event):
    if event == "turn+1":
        app.turn(1)
    elif event == "turn-1":
        app.turn(-1)
    elif event == "press":
        app.press()
    elif event == "back":
        app.back()


def main():
    disp = setup_display()
    events = queue.Queue()
    knob = setup_knob(events)
    app = App()
    next_tick = time.monotonic() + 1

    while True:
        start = time.monotonic()
        disp.image(app.render())
        print(f"drew in {time.monotonic() - start:.3f}s")

        # Wait for the knob or the next second, whichever comes first
        try:
            handle(app, events.get(timeout=max(0, next_tick - time.monotonic())))
            while not events.empty():  # handle every click from a fast turn before redrawing
                handle(app, events.get_nowait())
        except queue.Empty:
            pass
        if time.monotonic() >= next_tick:
            app.tick()
            next_tick += 1


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
