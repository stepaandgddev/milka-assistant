# Spotify for Milky

Controls the local Spotify desktop app through MPRIS on Linux and Windows Media
Sessions on Windows. While Spotify is playing,
Milky shows the bundled `assets/music_headphones.gif` animation. Pausing or
closing Spotify removes it again.

It does not need the Spotify Web API, a Premium account, or the `dbus-python`
package.

## Requirements

- Linux with a running graphical session and `gdbus` (usually from the `glib2`
  / `libglib2.0-bin` package), or Windows 10/11.
- Spotify desktop, installed as a Flatpak (`com.spotify.Client`) or a native
  `spotify` command on Linux.
- Windows: install the optional WinRT bindings in the Python environment used
  by Milky: `pip install winrt-Windows.Media.Control`.

On Windows, open the official Spotify desktop app and start a track once. The
addon reads the Spotify media session supplied by Windows; it does not inspect
the Spotify window or use the browser player.

## Install

Copy this folder into Milky's `addons/` directory:

```text
<Milky>/addons/spotify/
```

Alternatively, install it from **Settings → Skills** using this repository URL
and the `spotify` subfolder.

Then open **Settings → Skills**, enable **Spotify**, and reload skills if needed.
The addon is installed with its icon and animation asset.

## Tools

The assistant receives these tools:

- `current_track` — playback status, track, artist and album
- `play_pause` — toggle playback
- `play_track` — search Spotify and play the best match, or resume with an empty query
- `next_track` — skip forward
- `previous_track` — go back
- `set_volume` — set the volume from 0 to 100

Examples you can ask Milky:

- "What is playing on Spotify?"
- "Put on some music." / "Play Ken Carson."
- "Pause the music."
- "Next track, please."
- "Set Spotify volume to 30%."

## Animation behavior

The addon polls playback in the background. The headphones animation appears
when playback starts and disappears when Spotify is paused, stopped or closed.
Chat replies, input, and drawing animations temporarily take priority, then the
headphones return automatically.

## Notes

Spotify search uses the client's own `spotify:search:` URI. The first matching
track is started by Spotify itself. The addon never reads Spotify credentials or
sends data anywhere except to the local MPRIS interface.
# milka-spotify-ext
# milka-spotify-ext
