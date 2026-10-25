import sys
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtWidgets import QApplication

try:
    import pytesseract
    from PIL import Image

    _OCR_AVAILABLE = True
except ImportError:
    pytesseract = None
    Image = None
    _OCR_AVAILABLE = False

LANGUAGE_MAP = {
    "eng": "eng",
    "rus": "rus",
}


class ScreenReader:

    def __init__(self, settings, parent=None):
        self._settings = dict(settings or {})
        self._parent = parent
        self._timer = QTimer(parent)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self._tick)
        self._last_text = ""
        self._enabled = bool(self._settings.get("enabled", False))
        self._interval = float(self._settings.get("interval", 10.0))
        self._language = str(self._settings.get("language", "eng"))
        self._app = QApplication.instance() or QApplication(sys.argv)

        if self._enabled:
            self.start()

    def update_settings(self, settings):
        self._settings = dict(settings or {})
        enabled = bool(self._settings.get("enabled", False))
        interval = float(self._settings.get("interval", 10.0))
        language = str(self._settings.get("language", "eng"))

        was_running = self._timer.isActive()
        self._timer.stop()

        self._enabled = enabled
        self._interval = interval
        self._language = language

        if enabled:
            self._timer.start(int(interval * 1000))
        elif was_running:
            self._last_text = ""

    def start(self):
        if not self._enabled:
            return
        self._timer.start(int(self._interval * 1000))

    def stop(self):
        self._timer.stop()

    def is_available(self):
        return _OCR_AVAILABLE

    def capture_and_read(self, speak_callback=None):
        """Capture the primary screen, OCR it, and call speak_callback with new text."""
        if not _OCR_AVAILABLE:
            return None, "OCR is not available. Install pytesseract, Pillow and tesseract-ocr."

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return None, "No screen available."

        pixmap = screen.grabWindow(0)
        image = pixmap.toImage()

        # Convert QImage to PIL Image
        image = image.convertToFormat(QImage.Format.Format_RGBA8888)
        width = image.width()
        height = image.height()
        ptr = image.bits()
        ptr.setsize(height * width * 4)
        arr = bytes(ptr)
        pil_image = Image.frombytes("RGBA", (width, height), arr)

        lang = LANGUAGE_MAP.get(self._language, "eng")
        try:
            text = pytesseract.image_to_string(pil_image, lang=lang)
        except Exception as error:
            return None, f"OCR failed: {error}"

        text = " ".join(text.split())
        if not text or text == self._last_text:
            return text, ""

        self._last_text = text
        if speak_callback:
            speak_callback(text)
        return text, ""

    def _tick(self):
        self.capture_and_read()
