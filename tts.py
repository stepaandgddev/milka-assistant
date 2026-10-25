import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import requests
from PySide6.QtCore import QObject, QProcess, QThread, Signal

TTS_TIMEOUT = float(os.environ.get("TTS_TIMEOUT", "60"))
TTS_HEALTH_TIMEOUT = float(os.environ.get("TTS_HEALTH_TIMEOUT", "5"))
TTS_TEMP_DIR = Path(tempfile.gettempdir()) / "milky-tts"

GROQ_SPEECH_URL = "https://api.groq.com/openai/v1/audio/speech"


class TtsError(RuntimeError):
    pass


def _normalize_base_url(value):
    url = str(value or "").strip().rstrip("/")
    if not url:
        raise TtsError("Set the Milka TTS URL in Settings.")
    if not url.lower().startswith(("http://", "https://")):
        raise TtsError("The Milka TTS URL must start with http:// or https://.")
    return url


def _response_error(response):
    detail = ""
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    if isinstance(payload, dict):
        detail = payload.get("error") or payload.get("detail") or ""
        if isinstance(detail, dict):
            detail = detail.get("message") or detail
    elif payload:
        detail = payload
    detail = " ".join(str(detail).split())
    if len(detail) > 240:
        detail = detail[:237] + "..."
    if detail:
        return f"HTTP {response.status_code}: {detail}"
    return f"HTTP {response.status_code}"


def _wav_bytes(response):
    data = response.content
    if not data:
        raise TtsError("TTS returned an empty response.")
    if (
        len(data) < 12
        or data[:4] not in (b"RIFF", b"RF64")
        or data[8:12] != b"WAVE"
    ):
        content_type = response.headers.get("Content-Type", "unknown")
        raise TtsError(f"TTS returned non-WAV data ({content_type}).")
    return data


def _speed(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 1.0
    return max(0.5, min(2.0, number))


def check_milka_health(base_url):
    base = _normalize_base_url(base_url)
    try:
        response = requests.get(
            base + "/health", timeout=TTS_HEALTH_TIMEOUT
        )
    except requests.RequestException as error:
        raise TtsError(f"Cannot reach {base}: {error}") from error
    if not response.ok:
        raise TtsError(_response_error(response))
    body = " ".join(response.text.split())
    if len(body) > 160:
        body = body[:157] + "..."
    return f"OK ({response.status_code})" + (f": {body}" if body else "")


def synthesize(text, tts_settings):
    text = str(text or "").strip()
    if not text:
        raise TtsError("There is no text to speak.")
    provider = str(tts_settings.get("provider", "milka")).strip().lower()
    if provider == "groq":
        return _synthesize_groq(text, tts_settings)
    return _synthesize_milka(text, tts_settings)


def _synthesize_milka(text, tts_settings):
    base = _normalize_base_url(tts_settings.get("milka_url"))
    voice = str(tts_settings.get("milka_voice") or "sveta").strip()
    payload = {
        "input": text,
        "voice": voice,
        "response_format": "wav",
        "speed": _speed(tts_settings.get("milka_speed")),
    }
    try:
        response = requests.post(
            base + "/v1/audio/speech",
            json=payload,
            timeout=TTS_TIMEOUT,
        )
    except requests.RequestException as error:
        raise TtsError(f"Cannot reach {base}: {error}") from error
    if not response.ok:
        raise TtsError(_response_error(response))
    return _wav_bytes(response)


def _synthesize_groq(text, tts_settings):
    api_key = str(
        tts_settings.get("groq_api_key")
        or os.environ.get("GROQ_API_KEY", "")
    ).strip()
    if not api_key:
        raise TtsError("Set the Groq API key in Settings.")
    payload = {
        "model": str(
            tts_settings.get("groq_model") or "canopylabs/orpheus-v1-english"
        ).strip(),
        "input": text,
        "voice": str(
            tts_settings.get("groq_voice") or "troy"
        ).strip(),
        "response_format": "wav",
    }
    try:
        response = requests.post(
            GROQ_SPEECH_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=TTS_TIMEOUT,
        )
    except requests.RequestException as error:
        raise TtsError(f"Cannot reach Groq: {error}") from error
    if not response.ok:
        raise TtsError(_response_error(response))
    return _wav_bytes(response)


def cleanup_temp_files(keep=None):
    try:
        TTS_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    keep_path = Path(keep) if keep else None
    for path in TTS_TEMP_DIR.glob("milky-*.wav"):
        if keep_path is not None and path == keep_path:
            continue
        try:
            path.unlink()
        except OSError:
            pass


def write_temp_wav(data):
    cleanup_temp_files()
    try:
        TTS_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        path = TTS_TEMP_DIR / f"milky-{uuid.uuid4().hex}.wav"
        path.write_bytes(data)
    except OSError as error:
        raise TtsError(f"Could not save TTS audio: {error}") from error
    return path


class TtsWorker(QThread):

    ready = Signal(str)
    failed = Signal(str)

    def __init__(self, text, tts_settings, parent=None):
        super().__init__(parent)
        self._text = text
        self._tts_settings = dict(tts_settings)

    def run(self):
        try:
            data = synthesize(self._text, self._tts_settings)
            self.ready.emit(str(write_temp_wav(data)))
        except Exception as error:
            self.failed.emit(str(error))


class AudioPlayer(QObject):

    finished = Signal()
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = None
        self._path = None

    def play(self, path):
        self.stop()
        self._path = str(path)
        if sys.platform == "win32":
            self._play_windows()
            return

        command = self._player_command()
        if command is None:
            self._path = None
            self.failed.emit(
                "No audio player found. Install paplay, pw-play, aplay, or ffplay."
            )
            return

        program, arguments = command
        process = QProcess(self)
        self._process = process
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)
        process.start(program, arguments + [self._path])

    def _play_windows(self):
        try:
            import winsound
        except ImportError as error:
            self._path = None
            self.failed.emit(f"Windows audio is unavailable: {error}")
            return
        try:
            winsound.PlaySound(
                self._path,
                winsound.SND_FILENAME | winsound.SND_ASYNC,
            )
        except Exception as error:
            self._path = None
            self.failed.emit(f"Could not play TTS audio: {error}")

    @staticmethod
    def _player_command():
        if sys.platform.startswith("linux"):
            candidates = [
                ("paplay", []),
                ("pw-play", []),
                ("aplay", ["-q"]),
                (
                    "ffplay",
                    ["-nodisp", "-autoexit", "-loglevel", "quiet"],
                ),
            ]
        elif sys.platform == "darwin":
            candidates = [("afplay", [])]
        else:
            return None
        for name, arguments in candidates:
            program = shutil.which(name)
            if program:
                return program, arguments
        return None

    def _on_finished(self, exit_code, _exit_status):
        process = self._process
        self._process = None
        self._path = None
        if process is not None:
            process.deleteLater()
        if exit_code == 0:
            self.finished.emit()
        else:
            self.failed.emit(f"Audio player exited with code {exit_code}.")

    def _on_error(self, error):
        process = self._process
        self._process = None
        self._path = None
        if process is not None:
            process.deleteLater()
        self.failed.emit(f"Could not play TTS audio: {error}")

    def stop(self):
        if sys.platform == "win32":
            try:
                import winsound

                winsound.PlaySound(None, 0)
            except Exception:
                pass
        process = self._process
        self._process = None
        self._path = None
        if process is not None:
            try:
                process.finished.disconnect(self._on_finished)
                process.errorOccurred.disconnect(self._on_error)
            except (RuntimeError, TypeError):
                pass
            if process.state() != QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(500)
            process.deleteLater()
