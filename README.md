# RaspiMusicPlayer

Raspberry Pi music player and FM radio with a 240×320 ST7789 SPI screen. Screens are designed in a simulator on a computer, and the same code runs on the Pi.

## Wiring (BCM)

Screen: VCC → 3.3V · GND → GND · CS → GPIO8 (CE0) · RESET → GPIO25 · DC → GPIO24 · SDI → GPIO10 · SCK → GPIO11 · LED → 3.3V

Rotary knob: CLK → GPIO5 · DT → GPIO6 · SW → GPIO13 · + → 3.3V · GND → GND

Turn to scroll (or change volume while playing), press to select (or play/pause), hold to go back. On the radio, turn to pick a key and press it; TUNE and VOL then follow the knob until pressed again.

## Pi setup

1. Enable SPI in `sudo raspi-config`, then add `dtoverlay=spi0-0cs` under `dtparam=spi=on` in `/boot/firmware/config.txt` and reboot. Without the overlay you get a "GPIO busy" error.
2. Install:
   ```bash
   sudo apt install -y python3-pil
   python3 -m venv --system-site-packages ~/.venv
   git clone https://github.com/<your-username>/RaspiMusicPlayer.git
   cd RaspiMusicPlayer
   ~/.venv/bin/pip install -r requirements-pi.txt
   ```
3. Set your time zone in `sudo raspi-config` under **Localisation Options → Timezone**.
4. Run `~/.venv/bin/python3 pi.py`. To update later, run `git pull`.

## Clock without Wi-Fi (Pi 5)

The screen shows the Pi's system time. The Pi 5's built-in clock keeps time while it's off if a battery is plugged into the **BAT** connector. With Wi-Fi, the time comes from the internet; without it, the time comes from that clock.

- Official rechargeable battery: turn on charging by adding `dtparam=rtc_bbat_vchg=3000000` to `/boot/firmware/config.txt`, then reboot. Don't add this line for a non-rechargeable cell.
- Check it's working with `timedatectl` or `sudo hwclock --show`.

## Computer (simulator)

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements-desktop.txt
.venv\Scripts\python desktop.py
```

Up/Down or the mouse wheel turn the knob, Enter presses it, Backspace holds it (back).

## Code layout

- `screens.py` and `library.py` are shared by both machines and must **not** import Pi-only modules (`board`, `digitalio`, `gpiozero`, `adafruit_*`).
- `pi.py` drives the real screen, and `desktop.py` is the simulator.

## Music library

Put music in `music/` using MusicBee's folder layout: `Artist/Album/01 - Title.mp3`. Playlists (`.m3u`) go in `music/Playlists/`. The music isn't stored in git, so copy it onto the Pi separately. Album art comes from an image in the album folder (e.g. `cover.jpg` or `folder.jpg`), or else from art embedded in the song file.

## Radio

Favourite stations are in `FAVOURITES` in `app.py`. The SDR isn't connected to the screen yet.

## Troubleshooting

- **Wrong colours or white background:** `pi.py` sends `disp.write(0x20)` to turn inversion off. Try `0x21` if colours are still wrong.
- **Scrambled image:** use the ST7789 driver, not ILI9341, or lower `BAUDRATE`.
