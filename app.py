"""
What's on screen and how the controls move around it. Shared by the laptop and the Pi.

The player has one rotary knob with a push button, so everything is driven by four actions:
  turn(step)  knob turned; +1 per click clockwise, -1 anticlockwise
  press()     knob pressed
  back()      knob held down
  tick()      once a second, for the song position and the clock

Library:      turn = move up/down the list, press = open / play, hold = back a page
Now playing:  turn = volume, press = play/pause, hold = back to the library
"""

from dataclasses import dataclass, field
from typing import Callable

from library import read_tags, scan_library, sort_key
from screens import VISIBLE_ROWS, Track, render_list, render_now_playing

VOLUME_STEP = 5


@dataclass
class MenuItem:
    label: str
    detail: str = ""
    open: Callable = None  # returns a Page to show, or None if it did something else (e.g. play)


@dataclass
class Page:
    title: str
    items: list = field(default_factory=list)
    empty_text: str = "Nothing here"
    selected: int = 0
    top: int = 0  # first row on screen

    def move(self, step):
        if not self.items:
            return
        self.selected = max(0, min(len(self.items) - 1, self.selected + step))
        if self.selected < self.top:
            self.top = self.selected
        elif self.selected >= self.top + VISIBLE_ROWS:
            self.top = self.selected - VISIBLE_ROWS + 1


def plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


class App:
    def __init__(self, library=None):
        self.library = library or scan_library()
        self.volume = 50
        self.queue = []       # songs from the list the playing song was chosen from
        self.queue_index = 0
        self.track = None
        self.now_playing = False
        self.pages = [Page("Library", self.home_items())]

    # ----- Controls -----

    def turn(self, step):
        if self.now_playing:
            self.volume = max(0, min(100, self.volume + step * VOLUME_STEP))
        else:
            self.pages[-1].move(step)

    def press(self):
        if self.now_playing:
            self.track.playing = not self.track.playing
            return
        page = self.pages[-1]
        if page.items and page.items[page.selected].open:
            new_page = page.items[page.selected].open()
            if new_page:
                self.pages.append(new_page)

    def back(self):
        if self.now_playing:
            self.now_playing = False
        elif len(self.pages) > 1:
            self.pages.pop()
        elif self.track:
            self.now_playing = True

    def tick(self):
        """Advance the song position, like real playback would."""
        track = self.track
        if not track or not track.playing:
            return
        track.position += 1
        if track.duration and track.position >= track.duration:
            if self.queue_index + 1 < len(self.queue):
                self.play(self.queue, self.queue_index + 1)
            else:
                track.position = track.duration
                track.playing = False

    def render(self, now=None):
        if self.now_playing:
            return render_now_playing(self.track, self.volume, now)
        page = self.pages[-1]
        rows = [(item.label, item.detail) for item in page.items]
        return render_list(page.title, rows, page.selected, page.top, now, page.empty_text)

    # ----- Playing -----

    def play(self, songs, index):
        song = songs[index]
        tags = read_tags(song.path)
        self.queue = songs
        self.queue_index = index
        self.track = Track(
            title=tags.get("title", song.title),
            artist=song.artist,
            album=song.album,
            genre=tags.get("genre", ""),
            path=str(song.path),
            duration=tags.get("duration", 0),
        )
        self.now_playing = True
        self.pages[0].items = self.home_items()

    # ----- Pages -----

    def home_items(self):
        lib = self.library
        items = [
            MenuItem("Artists", plural(len(lib.artists), "artist"), self.artists_page),
            MenuItem("Albums", plural(len(lib.albums), "album"), self.albums_page),
            MenuItem("Playlists", plural(len(lib.playlists), "playlist"), self.playlists_page),
        ]
        if self.track:
            items.insert(0, MenuItem("Now Playing", self.track.title, self.show_now_playing))
        return items

    def show_now_playing(self):
        self.now_playing = True

    def artists_page(self):
        items = [MenuItem(name, plural(len(albums), "album"), lambda name=name: self.artist_page(name))
                 for name, albums in self.library.artists.items()]
        return Page("Artists", items, "No music yet - add to music/")

    def artist_page(self, name):
        albums = sorted(self.library.artists[name], key=lambda a: sort_key(a.name))
        items = [MenuItem(album.name, plural(len(album.songs), "song"), lambda album=album: self.album_page(album))
                 for album in albums]
        return Page(name, items)

    def albums_page(self):
        items = [MenuItem(album.name, album.artist, lambda album=album: self.album_page(album))
                 for album in self.library.albums]
        return Page("Albums", items, "No music yet - add to music/")

    def album_page(self, album):
        return self.songs_page(album.name, album.songs, show_artist=False)

    def playlists_page(self):
        items = [MenuItem(playlist.name, plural(len(playlist.songs), "song"),
                          lambda playlist=playlist: self.songs_page(playlist.name, playlist.songs))
                 for playlist in self.library.playlists]
        return Page("Playlists", items, "No playlists - add to music/Playlists/")

    def songs_page(self, title, songs, show_artist=True):
        items = [MenuItem(song.title, f"{song.artist} - {song.album}" if show_artist else "",
                          lambda i=i: self.play(songs, i))
                 for i, song in enumerate(songs)]
        return Page(title, items)
