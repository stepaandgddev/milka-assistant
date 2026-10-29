"""Control the local Spotify desktop app through MPRIS or Windows media sessions.

On Linux commands use MPRIS/gdbus. On Windows they use the native Global
System Media Transport Controls API, so the Spotify Web API is not required.

While Spotify is playing, the addon asks Milky to show the bundled
``assets/music_headphones.gif`` animation. Pausing or closing Spotify removes
it again.
"""

from __future__ import annotations

import os
import asyncio
import inspect
import re
import shutil
import subprocess
import threading
import time
from typing import Any, Callable

from addon_api import tool

try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as _MediaManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as _PlaybackStatus,
    )
except ImportError:  # Windows support is optional on Linux.
    _MediaManager = None
    _PlaybackStatus = None

MPRIS_DEST = "org.mpris.MediaPlayer2.spotify"
MPRIS_PATH = "/org/mpris/MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
PROPS_IFACE = "org.freedesktop.DBus.Properties"

ANIMATION = "assets/music_headphones.gif"
POLL_SECONDS = 2.0
IDLE_POLL_SECONDS = 4.0
LAUNCH_TIMEOUT = 15.0
PLAYBACK_TIMEOUT = 5.0


class SpotifyError(RuntimeError):
    """A user-facing Spotify or MPRIS failure."""


def _unescape(value: str) -> str:
    return value.replace("\\'", "'").replace("\\\\", "\\")


def search_uri(query: str) -> str:
    """Build a Spotify search URI that opens the best matching track.

    Spotify's desktop client starts the first result when it receives
    ``spotify:search:``. Each word is quoted so the client prefers an exact
    match instead of a broad search.
    """
    cleaned = re.sub(r'["\r\n\t]+', " ", query or "")
    words = [
        word
        for word in cleaned.split()
        if any(character.isalnum() for character in word)
    ][:12]
    if not words:
        return ""
    phrase = " ".join(f'"{word}"' for word in words)[:220]
    return f"spotify:search:{phrase}"


def _variant_string(text: str, key: str) -> str:
    match = re.search(
        rf"'{re.escape(key)}': <'((?:[^'\\]|\\.)*)'>",
        text,
        re.S,
    )
    return _unescape(match.group(1)) if match else ""


def _variant_uint(text: str, key: str) -> int:
    match = re.search(rf"'{re.escape(key)}': <u?int64 (\d+)>", text)
    return int(match.group(1)) if match else 0


def _variant_track_id(text: str) -> str:
    match = re.search(
        r"'mpris:trackid': <(?:objectpath )?'((?:[^'\\]|\\.)*)'>",
        text,
        re.S,
    )
    if not match:
        return ""
    track_id = _unescape(match.group(1))
    return track_id.rsplit("/", 1)[-1]


def parse_metadata(text: str) -> dict[str, Any]:
    """Parse the GVariant text returned by MPRIS Metadata."""
    artists: list[str] = []
    artists_match = re.search(r"'xesam:artist': <\[(.*?)\]>", text, re.S)
    if artists_match:
        artists = [
            _unescape(item)
            for item in re.findall(
                r"'((?:[^'\\]|\\.)*)'",
                artists_match.group(1),
            )
        ]
    track_id = _variant_track_id(text)
    url = _variant_string(text, "xesam:url") or (
        f"https://open.spotify.com/track/{track_id}" if track_id else ""
    )
    return {
        "title": _variant_string(text, "xesam:title"),
        "artist": ", ".join(artists),
        "album": _variant_string(text, "xesam:album"),
        "image": _variant_string(text, "mpris:artUrl"),
        "trackId": track_id,
        "url": url,
        "durationMs": _variant_uint(text, "mpris:length") // 1000,
    }


class LocalSpotify:
    """A small MPRIS client backed by the ``gdbus`` command."""

    def __init__(
        self,
        runner: Callable[[list[str]], str] | None = None,
        app_id: str = "com.spotify.Client",
    ) -> None:
        self._runner = runner or self._run
        self.app_id = app_id
        self._lock = threading.RLock()
        self._available_until = 0.0
        self._available_value = False

    @property
    def _is_windows(self) -> bool:
        return os.name == "nt"

    @staticmethod
    def _windows_call(operation):
        """Run a WinRT async operation without requiring an event loop."""
        result = operation()
        if inspect.isawaitable(result):
            return asyncio.run(result)
        return result

    def _windows_session(self):
        if _MediaManager is None:
            raise SpotifyError(
                "Windows Spotify support needs the 'winrt-Windows.Media.Control' package."
            )
        manager = self._windows_call(_MediaManager.request_async)
        sessions = manager.get_sessions()
        for session in sessions:
            source = str(
                getattr(session, "source_app_user_model_id", "") or ""
            ).lower()
            # Store and classic Spotify builds expose different AUMIDs, for
            # example SpotifyAB.SpotifyMusic_... and Spotify.exe. Do not rely
            # on one exact package identifier.
            if "spotify" in source or "spotify" in str(session).lower():
                return session
        return None

    def _windows_now_playing(self) -> dict[str, Any]:
        try:
            session = self._windows_session()
        except SpotifyError:
            raise
        except Exception as error:
            raise SpotifyError(f"Windows media session error: {error}") from error
        if session is None:
            return {"connected": False}
        try:
            properties = self._windows_call(session.try_get_media_properties_async)
            playback = session.get_playback_info()
            status = playback.playback_status
            playing = status == _PlaybackStatus.PLAYING
            return {
                "connected": True,
                "playing": playing,
                "device": "Spotify (Windows)",
                "title": str(properties.title or ""),
                "artist": str(properties.artist or ""),
                "album": str(properties.album_title or ""),
            }
        except Exception as error:
            raise SpotifyError(f"Could not read Spotify media session: {error}") from error

    @staticmethod
    def _run(args: list[str]) -> str:
        env = dict(os.environ)
        if (
            not env.get("DBUS_SESSION_BUS_ADDRESS")
            and hasattr(os, "getuid")
        ):
            env["DBUS_SESSION_BUS_ADDRESS"] = (
                f"unix:path=/run/user/{os.getuid()}/bus"
            )
        try:
            process = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
            )
        except subprocess.TimeoutExpired as error:
            raise SpotifyError("Spotify did not respond in time.") from error
        except OSError as error:
            raise SpotifyError(
                "gdbus is required to control Spotify. Install GLib tools."
            ) from error
        if process.returncode != 0:
            message = (process.stderr or process.stdout or "").strip()
            raise SpotifyError(message or "Spotify is not available.")
        return process.stdout

    def _call(self, method: str, *arguments: str) -> str:
        args = [
            "gdbus",
            "call",
            "--session",
            "--dest",
            MPRIS_DEST,
            "--object-path",
            MPRIS_PATH,
            "--method",
            f"{PLAYER_IFACE}.{method}",
            *arguments,
        ]
        with self._lock:
            return self._runner(args)

    def _get(self, prop: str) -> str:
        args = [
            "gdbus",
            "call",
            "--session",
            "--dest",
            MPRIS_DEST,
            "--object-path",
            MPRIS_PATH,
            "--method",
            f"{PROPS_IFACE}.Get",
            PLAYER_IFACE,
            prop,
        ]
        with self._lock:
            return self._runner(args)

    def _set(self, prop: str, value: str) -> str:
        args = [
            "gdbus",
            "call",
            "--session",
            "--dest",
            MPRIS_DEST,
            "--object-path",
            MPRIS_PATH,
            "--method",
            f"{PROPS_IFACE}.Set",
            PLAYER_IFACE,
            prop,
            value,
        ]
        with self._lock:
            return self._runner(args)

    def available(self, refresh: bool = False) -> bool:
        if self._is_windows:
            value = bool(self._windows_now_playing().get("connected"))
            self._available_value = value
            self._available_until = time.monotonic() + 1.5
            return value
        now = time.monotonic()
        if not refresh and now < self._available_until:
            return self._available_value
        try:
            self._get("PlaybackStatus")
            value = True
        except SpotifyError:
            value = False
        self._available_value = value
        self._available_until = now + 1.5
        return value

    def _playback_status(self) -> str:
        text = self._get("PlaybackStatus")
        match = re.search(r"'([^']*)'", text)
        return match.group(1) if match else "Stopped"

    def now_playing(self) -> dict[str, Any]:
        if self._is_windows:
            return self._windows_now_playing()
        if not self.available():
            return {"connected": False}
        try:
            status = self._playback_status()
            metadata = parse_metadata(self._get("Metadata"))
        except SpotifyError:
            return {"connected": False}
        result: dict[str, Any] = {
            "connected": True,
            "playing": status == "Playing",
            "device": "Spotify (local)",
        }
        if metadata.get("title"):
            result.update(metadata)
        return result

    def _wait_for_playback(
        self,
        previous_id: str = "",
        timeout: float = PLAYBACK_TIMEOUT,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            time.sleep(0.2)
            now = self.now_playing()
            last = now
            if not now.get("playing"):
                continue
            if not previous_id or now.get("trackId") != previous_id:
                return now
        return last or self.now_playing()

    def ensure_running(self) -> None:
        if self.available():
            return
        if not self.launch():
            raise SpotifyError(
                "Spotify is not running. Start Spotify and try again."
            )
        if not self.available(refresh=True):
            raise SpotifyError(
                "Spotify is running, but its MPRIS controls are not available."
            )

    def play(self, query: str = "") -> dict[str, Any]:
        self.ensure_running()
        query = " ".join((query or "").split())[:200]
        if query:
            before = self.now_playing().get("trackId", "")
            uri = search_uri(query)
            if not uri:
                raise SpotifyError("The search query is empty.")
            self._call("OpenUri", uri)
            return self._wait_for_playback(before)
        self._call("Play")
        return self._wait_for_playback("", timeout=1.5)

    def pause(self) -> dict[str, Any]:
        if self._is_windows:
            session = self._windows_session()
            if session is None:
                raise SpotifyError("Spotify is not running or has no active media session.")
            self._windows_call(session.try_pause_async)
            return self.now_playing()
        self._call("Pause")
        return self.now_playing()

    def resume(self) -> dict[str, Any]:
        if self._is_windows:
            session = self._windows_session()
            if session is None:
                raise SpotifyError("Spotify is not running or has no active media session.")
            self._windows_call(session.try_play_async)
            return self._wait_for_playback("", timeout=1.5)
        self._call("Play")
        return self._wait_for_playback("", timeout=1.5)

    def next(self) -> dict[str, Any]:
        if self._is_windows:
            session = self._windows_session()
            if session is None:
                raise SpotifyError("Spotify is not running or has no active media session.")
            self._windows_call(session.try_skip_next_async)
            return self._wait_for_playback("", timeout=3.0)
        before = self.now_playing().get("trackId", "")
        self._call("Next")
        return self._wait_for_playback(before, timeout=3.0)

    def previous(self) -> dict[str, Any]:
        if self._is_windows:
            session = self._windows_session()
            if session is None:
                raise SpotifyError("Spotify is not running or has no active media session.")
            self._windows_call(session.try_skip_previous_async)
            return self._wait_for_playback("", timeout=3.0)
        before = self.now_playing().get("trackId", "")
        self._call("Previous")
        return self._wait_for_playback(before, timeout=3.0)

    def set_volume(self, percent: Any) -> dict[str, Any]:
        if self._is_windows:
            raise SpotifyError(
                "Spotify volume control is not available through Windows Media Sessions."
            )
        try:
            value = max(0, min(100, int(float(percent))))
        except (TypeError, ValueError):
            value = 50
        self._set("Volume", f"<{value / 100:.2f}>")
        return self.now_playing()

    def launch(self) -> bool:
        if self._is_windows:
            try:
                os.startfile("spotify:")
            except OSError:
                return False
            deadline = time.monotonic() + LAUNCH_TIMEOUT
            while time.monotonic() < deadline:
                if self.available(refresh=True):
                    return True
                time.sleep(0.4)
            return self.available(refresh=True)
        flatpak = shutil.which("flatpak")
        command: list[str] | None = None
        if flatpak:
            try:
                probe = subprocess.run(
                    [flatpak, "info", self.app_id],
                    capture_output=True,
                    timeout=5,
                )
            except (OSError, subprocess.TimeoutExpired):
                probe = None
            if probe is not None and probe.returncode == 0:
                command = [flatpak, "run", self.app_id]
        if command is None:
            spotify = shutil.which("spotify")
            if spotify:
                command = [spotify]
        if command is None:
            return False
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            return False
        deadline = time.monotonic() + LAUNCH_TIMEOUT
        while time.monotonic() < deadline:
            if self.available(refresh=True):
                return True
            if process.poll() is not None:
                break
            time.sleep(0.4)
        return self.available(refresh=True)


class _PlayingWatcher:
    """Keep Milky's music animation in sync with Spotify playback."""

    def __init__(self, spotify: LocalSpotify, ctx) -> None:
        self._spotify = spotify
        self._ctx = ctx
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="milky-spotify",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if (
            self._thread.is_alive()
            and threading.current_thread() is not self._thread
        ):
            self._thread.join(timeout=6.0)

    def _run(self) -> None:
        last_playing = None
        while not self._stop.is_set():
            try:
                now = self._spotify.now_playing()
                playing = bool(now.get("playing"))
                connected = bool(now.get("connected"))
            except Exception:
                playing = False
                connected = False
            if playing != last_playing:
                if playing:
                    _show_music_animation(self._ctx)
                else:
                    _stop_music_animation(self._ctx)
                last_playing = playing
            self._stop.wait(
                POLL_SECONDS if connected else IDLE_POLL_SECONDS
            )


def _show_music_animation(ctx) -> None:
    try:
        ctx.play_animation(ANIMATION)
    except Exception:
        pass


def _stop_music_animation(ctx) -> None:
    try:
        ctx.stop_animation()
    except Exception:
        pass


def _label(info: dict[str, Any], include_status: bool = True) -> str:
    title = str(info.get("title") or "").strip()
    artist = str(info.get("artist") or "").strip()
    album = str(info.get("album") or "").strip()
    if not title:
        return "unknown track"
    text = f"{artist} — {title}" if artist else title
    if album:
        text += f" ({album})"
    if include_status:
        text += " — " + ("playing" if info.get("playing") else "paused")
    return text


def _sync_animation(ctx, info: dict[str, Any] | None = None) -> dict[str, Any]:
    if info is None:
        info = _spotify.now_playing()
    if info.get("playing"):
        _show_music_animation(ctx)
    else:
        _stop_music_animation(ctx)
    return info


def _ready() -> LocalSpotify:
    _spotify.ensure_running()
    return _spotify


_spotify = LocalSpotify()
_watcher: _PlayingWatcher | None = None


@tool(
    "current_track",
    "Return Spotify playback status and the current track.",
)
def current_track(ctx):
    try:
        info = _sync_animation(ctx)
    except SpotifyError as error:
        return str(error)
    if not info.get("connected"):
        if os.name == "nt":
            return (
                "Spotify is not visible to Windows Media Sessions. "
                "Start playback once in the official Spotify desktop app."
            )
        return "Spotify is not running."
    if not info.get("title"):
        return "Spotify is running, but no track is loaded."
    return _label(info)


@tool("play_pause", "Toggle Spotify playback (play or pause).")
def play_pause(ctx):
    _ready()
    info = _spotify.now_playing()
    if info.get("playing"):
        info = _spotify.pause()
        _sync_animation(ctx, info)
        if info.get("title"):
            return f"Paused: {_label(info, include_status=False)}."
        return "Paused Spotify."
    info = _spotify.resume()
    _sync_animation(ctx, info)
    if info.get("title"):
        state = "Playing" if info.get("playing") else "Resumed"
        return f"{state}: {_label(info, include_status=False)}."
    return "Resumed Spotify."


@tool(
    "play_track",
    "Search Spotify and play the best matching track. With an empty query, "
    "resume the current track.",
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Song title and optional artist, for example "
                    "'Ken Carson overseas'."
                ),
            },
        },
    },
)
def play_track(ctx, query=""):
    query = " ".join(str(query or "").split()).strip()
    _ready()
    info = _spotify.play(query)
    _sync_animation(ctx, info)
    if info.get("playing") and info.get("title"):
        return f"Playing: {_label(info, include_status=False)}."
    if info.get("title"):
        return (
            "Opened Spotify, but playback is still paused. "
            f"Current track: {_label(info, include_status=False)}."
        )
    return "Opened Spotify, but playback has not started yet."


@tool("next_track", "Skip to the next Spotify track.")
def next_track(ctx):
    _ready()
    info = _spotify.next()
    _sync_animation(ctx, info)
    if info.get("title"):
        return f"Next track: {_label(info)}."
    return "Skipped to the next Spotify track."


@tool("previous_track", "Go back to the previous Spotify track.")
def previous_track(ctx):
    _ready()
    info = _spotify.previous()
    _sync_animation(ctx, info)
    if info.get("title"):
        return f"Previous track: {_label(info)}."
    return "Went back to the previous Spotify track."


@tool(
    "set_volume",
    "Set the Spotify volume from 0 to 100.",
    {
        "type": "object",
        "properties": {
            "percent": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Volume percentage.",
            },
        },
        "required": ["percent"],
    },
)
def set_volume(ctx, percent=50):
    try:
        value = max(0, min(100, int(float(percent))))
    except (TypeError, ValueError):
        value = 50
    _ready()
    info = _spotify.set_volume(value)
    _sync_animation(ctx, info)
    return f"Spotify volume set to {value}%."


def setup(ctx):
    """Start watching Spotify so the headphones animation follows playback."""
    global _watcher
    if _watcher is not None:
        _watcher.stop()
        _watcher = None
    if not shutil.which("gdbus"):
        ctx.log("gdbus is not installed; Spotify tools are unavailable.")
        _stop_music_animation(ctx)
        return
    _watcher = _PlayingWatcher(_spotify, ctx)
    _watcher.start()


def shutdown(ctx):
    """Stop the watcher and remove the addon's animation."""
    global _watcher
    watcher = _watcher
    _watcher = None
    if watcher is not None:
        watcher.stop()
    _stop_music_animation(ctx)
