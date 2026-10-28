# RaspiMusicPlayer

Music player and FM radio (SDR, being added) for a Raspberry Pi 5 with a small SPI colour screen and a rotary knob. Screens are designed on a Windows laptop in a Tkinter simulator, pushed to GitHub, then pulled and tested on the Pi.

## Golden rule

`screens.py`, `library.py`, `app.py`, `sample_data.py` and any new shared module must **never** import Pi-only modules (`board`, `digitalio`, `gpiozero`, `adafruit_*`). Only `pi.py` (and the standalone `music_screen.py` test) may. This is what lets `desktop.py` and `pi.py` run identical drawing code, so nothing needs converting.

## Files

- `screens.py`: draws screens as PIL images at 320×240 (landscape). Holds the `Track` dataclass, fonts and layout constants. Screens: `render_now_playing(track, volume, now=None)` and `render_list(title, rows, selected, top, now, empty_text)` (6 rows of 36 px, label + grey detail, blue highlight, scrollbar) and `render_radio(...)`. Frequencies are whole numbers in tenths of a MHz (`1057` = 105.7); `FM_MIN`/`FM_MAX` = 875/1080.
- `library.py`: MusicBee-style library reading. `load_album_art(song_path, size)` checks for an image in the album folder (cover/folder/front/album/albumart, then any jpg/png), then art embedded in the tags (MP3/FLAC/M4A via mutagen). Results are cached with `lru_cache`. `scan_library()` reads `music/Artist/Album/` folder and file names only (fast); `read_tags()` gets title/genre/length when a song is played. Playlists are `.m3u`/`.m3u8` in `music/Playlists/`, matched on their last three path parts (Artist/Album/file, any case) so MusicBee's Windows paths work on the Pi.
- `app.py`: the `App` class holds what's on screen (`screen` is menu, now playing or radio; menus are a stack of `Page`s), the play queue and the `Radio` state. Driven by four actions: `turn(step)`, `press()`, `back()`, `tick()`; `render()` returns the frame. Home → Music Library or Radio. Library: Artists → albums → songs, Albums → songs, Playlists → songs; picking a song plays it with the rest of that list as the queue. Now playing: turn = volume, press = play/pause, back = menus. Radio: see below. Favourites are the `FAVOURITES` list (105.7, 94.5). Opening the radio pauses the music.
- `music/`: the library (empty for now, contents git-ignored). `music/Playlists/` for playlists.
- `sample_data.py`: fake tracks pointing into `sample_music/`. No longer used by `desktop.py` or `pi.py`.
- `desktop.py`: Tkinter simulator at 2× scale. Keys stand in for the knob: Up/Down or mouse wheel = turn, Enter/Space = press, Backspace/Left = hold (back), Esc = quit. Ticks once a second.
- `pi.py`: drives the real display and the rotary knob. gpiozero callbacks put events on a queue; the main loop handles all queued clicks, then redraws once, and ticks every second. Prints the time each frame takes to draw.
- `music_screen.py`: original standalone wiring test (portrait, shapes and text).
- `assets/fonts/`: bundled DejaVu Sans (regular and bold) so text is identical on both machines. Program assets only; album art comes from the music library, never `assets/`.

## Running

- Laptop (Windows, PowerShell): `.venv\Scripts\python desktop.py` from the repo folder. The `.venv` holds Pillow and mutagen (`requirements-desktop.txt`). VS Code must have `.venv` selected as its interpreter, or Pillow shows as missing.
- Pi: `~/.venv/bin/python3 pi.py`. The Pi's venv is `~/.venv`, created with `--system-site-packages` (Bookworm blocks system pip with "externally managed environment"). Packages are in `requirements-pi.txt`. In Geany, Execute is set to `/home/arimerten/.venv/bin/python3 "%f"`.
- To get changes onto the Pi: commit and push from the laptop, then `git pull` on the Pi. Only commit or push when the user asks.

## Hardware

- Panel: 240×320 **ST7789** (the ILI9341 driver gives scrambled output). Used landscape: `pi.py` passes the panel's native 240×320 with `rotation=90` (270 if upside down), and the images are 320×240.
- Wiring (BCM): CS = GPIO8 (CE0), DC = GPIO24, RESET = GPIO25, MOSI = GPIO10, SCK = GPIO11, VCC and backlight on 3.3V.
- Colour fix: `disp.write(0x20)` (inversion **off**) after init. 0x21 is inversion on.
- `/boot/firmware/config.txt` needs `dtoverlay=spi0-0cs` under `dtparam=spi=on`, or CE0 gives "GPIO busy".
- Rotary knob (KY-040 style) via gpiozero: CLK = GPIO5, DT = GPIO6, SW = GPIO13, + to 3.3V. Short press = select, hold 0.6 s = back. Clockwise = down the list / volume up.
- Clock: the screen uses `datetime.now()`. The Pi 5's built-in RTC with a battery on the BAT connector keeps time offline, and NTP corrects it when online, so the app needs no clock code.

## Current screen layout (now playing)

- Top bar (24 px): `VOL n% | h:mm am/pm | Sun 25 Oct`, in three equal sections with dividers.
- Left: album art at 150×150, or a grey box with a red border reading "MISSING ALBUM ART".
- Right: Name (bold, wraps to 2 lines, then "..."), Album, Genre (grey, truncated). `m:ss/m:ss` is bottom-aligned with the art.
- No progress bar or play/pause icon. The user asked for just the time text.

## Radio screen layout

Styled like an old wooden radio (colours in `screens.py`; the wood and dial are drawn once and cached by `radio_background()`).

- Top bar: `VOL n%`, `FM RADIO`, clock, in brass on dark wood.
- Cream tuning dial 87.5–108 MHz with a red needle; brass triangles mark favourites.
- Amber readout of the frequency (unlit `188.8` behind it, "TUNING" lamp) and a 10-bar volume meter.
- Push-button keys: TUNE, VOL, then each favourite (4 shown; scrolls if more). Turn picks a key (amber outline). Press TUNE or VOL to light it, then the knob tunes in 0.1 MHz steps or changes volume until pressed again (hold also stops). Pressing a favourite tunes to it; the tuned favourite stays pushed in. Hold = back to Home.
- No SDR control yet: `Radio.frequency` is what the SDR code should tune to.

## Things to check on real hardware

The simulator can't show these, so test on the Pi after each new screen:

- SPI refresh speed: a full-frame redraw per button press may feel slow and need partial updates.
- Knob: one step per detent (some encoders give two), direction (swap GPIO5/6 if reversed), button bounce.
- Colour or panel quirks.

## Plans and preferences

- Menus are to be built in plain Python (scrollable lists, submenus, about 150–200 lines), not LVGL.
- Music library uses MusicBee's layout: `Artist/Album/NN - Title.ext`.
- The user prefers short, concise docs. Keep the README brief.
- Possible additions that were offered but not requested yet: saving/removing favourites from the radio screen (and remembering them after restart), letter-jump or faster scrolling for long lists, album art thumbnails in lists, a clock-source indicator (NTP, RTC or `--:--`), and a set-time screen.
