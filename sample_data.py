"""
Fake tracks for trying out screens before real music playback exists.

They point into sample_music/, which is laid out like a MusicBee library.
The song files themselves don't exist -- only the folder art matters for now.
"""

from pathlib import Path

from screens import Track

SAMPLE_MUSIC = Path(__file__).parent / "sample_music"

SAMPLE_TRACKS = [
    Track(
        title="Sunset Drive",
        artist="The Example Band",
        album="Placeholder Album",
        genre="Synthwave",
        path=str(SAMPLE_MUSIC / "The Example Band" / "Placeholder Album" / "01 - Sunset Drive.mp3"),
        duration=214,
    ),
    Track(
        title="A Song With A Really Long Title That Will Not Fit",
        artist="Artist Without Album Art",
        album="An Album Name That Is Also Quite Long",
        genre="Indie Rock",
        path=str(SAMPLE_MUSIC / "Artist Without Album Art" / "No Cover" / "01 - Long Title.mp3"),
        duration=187,
    ),
]
