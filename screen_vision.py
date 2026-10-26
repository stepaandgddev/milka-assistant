"""Capture the user's screen for the vision model.

The screenshot is kept in memory and sent only for the current request.  It is
never written to disk by this module.
"""

import base64

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QCursor, QGuiApplication


class ScreenCaptureError(RuntimeError):
    pass


def capture_screen(max_width=1600, jpeg_quality=82):
    """Return the active screen as a JPEG-ready payload.

    ``max_width`` limits the larger image dimension.  Downscaling keeps the
    request small enough for cloud vision APIs while preserving readable text.
    """
    try:
        max_width = max(640, min(3840, int(max_width)))
    except (TypeError, ValueError):
        max_width = 1600
    try:
        jpeg_quality = max(50, min(95, int(jpeg_quality)))
    except (TypeError, ValueError):
        jpeg_quality = 82

    screen = QGuiApplication.screenAt(QCursor.pos())
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    if screen is None:
        raise ScreenCaptureError("No screen is available.")

    pixmap = screen.grabWindow(0)
    if pixmap.isNull():
        raise ScreenCaptureError(
            "The screen could not be captured. On Wayland, try an X11 or "
            "XWayland session."
        )

    image = pixmap.toImage()
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        raise ScreenCaptureError("The screen capture was empty.")

    if max(image.width(), image.height()) > max_width:
        image = image.scaled(
            max_width,
            max_width,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise ScreenCaptureError("Could not allocate the screenshot buffer.")
    try:
        saved = image.save(buffer, "JPEG", jpeg_quality)
        data = bytes(buffer.data())
    finally:
        buffer.close()

    if not saved or not data:
        raise ScreenCaptureError("The screenshot could not be encoded as JPEG.")

    return {
        "base64": base64.b64encode(data).decode("ascii"),
        "mime": "image/jpeg",
        "width": image.width(),
        "height": image.height(),
    }
