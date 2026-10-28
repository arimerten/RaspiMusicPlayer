"""
Reading the music library. Shared by the laptop and the Pi.

The library is laid out the way MusicBee organises it:

  music/<Artist>/<Album>/01 - Title.mp3
  music/<Artist>/<Album>/cover.jpg     (optional)
  music/Playlists/<Name>.m3u           (optional)

Album art is found by checking, in order:
  1. An image file in the song's album folder (cover.jpg, folder.jpg, ...)
  2. Art embedded in the song file's tags (MP3, FLAC, M4A)
"""

import io
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path, PurePosixPath, PureWindowsPath

from PIL import Image, ImageOps

MUSIC_DIR = Path(__file__).parent / "music"
PLAYLISTS_FOLDER = "Playlists"  # inside MUSIC_DIR; not treated as an artist

AUDIO_TYPES = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav", ".aac", ".wma"}
PLAYLIST_TYPES = {".m3u", ".m3u8"}
IMAGE_TYPES = {".jpg", ".jpeg", ".png"}

# Preferred names for album art files, best first (case doesn't matter)
ART_NAMES = ["cover", "folder", "front", "album", "albumart"]


def find_art_file(song_path):
    """Return the path to an album art image in the song's folder, or None."""
    folder = Path(song_path).parent
    if not folder.is_dir():
        return None

    images = [f for f in folder.iterdir() if f.suffix.lower() in IMAGE_TYPES]
    if not images:
        return None
    for name in ART_NAMES:
        for image in images:
            if image.stem.lower() == name:
                return image
    return sorted(images)[0]  # no preferred name, so use any image in the folder


def read_embedded_art(song_path):
    """Return the raw bytes of the cover art stored inside the song file, or None."""
    try:
        import mutagen
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4

        audio = mutagen.File(song_path)
    except ImportError:
        return None  # mutagen not installed, so only folder images are used
    except Exception:
        return None  # missing file or not an audio file mutagen understands

    if audio is None:
        return None
    if isinstance(audio, FLAC):
        return audio.pictures[0].data if audio.pictures else None
    if isinstance(audio, MP4):
        covers = (audio.tags or {}).get("covr")
        return bytes(covers[0]) if covers else None
    if audio.tags is not None and hasattr(audio.tags, "getall"):  # MP3 (ID3 tags)
        pictures = audio.tags.getall("APIC")
        return pictures[0].data if pictures else None
    return None


@lru_cache(maxsize=16)
def load_album_art(song_path, size):
    """
    Return the album art as a size x size image, or None if there isn't any.

    Cached, so redrawing the screen every second doesn't reload the image.
    """
    if not song_path:
        return None
    art_file = find_art_file(song_path)
    source = art_file if art_file else read_embedded_art(song_path)
    if source is None:
        return None
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    try:
        with Image.open(source) as img:
            return ImageOps.fit(img.convert("RGB"), (size, size), Image.LANCZOS)
    except (OSError, ValueError):
        return None  # file exists but isn't a readable image


@dataclass
class Song:
    path: Path
    title: str
    number: int
    artist: str
    album: str


@dataclass
class Album:
    name: str
    artist: str
    songs: list = field(default_factory=list)


@dataclass
class Playlist:
    name: str
    songs: list = field(default_factory=list)


@dataclass
class Library:
    artists: dict = field(default_factory=dict)   # artist name -> list of Albums
    albums: list = field(default_factory=list)    # every album, sorted by name
    playlists: list = field(default_factory=list)


def sort_key(name):
    """Sort ignoring case and a leading 'The ', like MusicBee does."""
    name = name.casefold()
    return name[4:] if name.startswith("the ") else name


def song_from_file(path, artist, album):
    """Make a Song from a file named like '01 - Title.mp3' (the number is optional)."""
    match = re.match(r"^(\d+)(?:\s*[-.]\s*|\s+)(.+)$", path.stem)
    if match:
        return Song(path, match.group(2), int(match.group(1)), artist, album)
    return Song(path, path.stem, 0, artist, album)


def subfolders(folder):
    return sorted((f for f in folder.iterdir() if f.is_dir()), key=lambda f: sort_key(f.name))


def scan_library(music_dir=MUSIC_DIR):
    """Read the Artist/Album folders and playlists. Only file names are read, so it's quick."""
    library = Library()
    if not music_dir.is_dir():
        return library

    for artist_dir in subfolders(music_dir):
        if artist_dir.name == PLAYLISTS_FOLDER:
            continue
        albums = []
        for album_dir in subfolders(artist_dir):
            songs = [song_from_file(f, artist_dir.name, album_dir.name)
                     for f in album_dir.iterdir() if f.suffix.lower() in AUDIO_TYPES]
            if songs:
                songs.sort(key=lambda s: (s.number, sort_key(s.title)))
                albums.append(Album(album_dir.name, artist_dir.name, songs))
        if albums:
            library.artists[artist_dir.name] = albums
            library.albums.extend(albums)
    library.albums.sort(key=lambda a: (sort_key(a.name), sort_key(a.artist)))

    playlist_dir = music_dir / PLAYLISTS_FOLDER
    if playlist_dir.is_dir():
        by_location = {location_key(song.path): song for album in library.albums for song in album.songs}
        files = sorted((f for f in playlist_dir.iterdir() if f.suffix.lower() in PLAYLIST_TYPES),
                       key=lambda f: sort_key(f.stem))
        for file in files:
            library.playlists.append(Playlist(file.stem, read_playlist(file, by_location)))
    return library


def location_key(path):
    """The last three parts of a song's path (Artist, Album, file), ignoring case."""
    return tuple(part.casefold() for part in path.parts[-3:])


def read_playlist(file, by_location):
    """
    Return the songs listed in an .m3u playlist.

    Songs are matched on their Artist/Album/file part only, so a playlist exported
    from MusicBee with full Windows paths still works on the Pi.
    Songs that aren't in the library are skipped.
    """
    songs = []
    for line in file.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        path = PureWindowsPath(line) if "\\" in line else PurePosixPath(line)
        song = by_location.get(location_key(path))
        if song:
            songs.append(song)
    return songs


def read_tags(song_path):
    """Return the song's title, genre and length from its tags. Missing values are left out."""
    try:
        import mutagen

        audio = mutagen.File(song_path, easy=True)
    except ImportError:
        return {}
    except Exception:
        return {}
    if audio is None:
        return {}

    tags = audio.tags or {}
    result = {}
    for key in ("title", "genre"):
        values = tags.get(key)
        if values:
            result[key] = values[0]
    if audio.info and audio.info.length:
        result["duration"] = int(audio.info.length)
    return result
