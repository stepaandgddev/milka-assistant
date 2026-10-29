"""Capture the user's screen for the vision model.

On Wayland, Qt cannot read the compositor's framebuffer directly.  Milky uses
the freedesktop screenshot portal over D-Bus instead.  The portal writes the
capture to a temporary file, which this module reads and then removes.  The
JPEG sent to the vision model is kept only in memory.
"""

import base64
import os
import sys
import uuid
from pathlib import Path

from PySide6.QtCore import (
    QBuffer,
    QEventLoop,
    QIODevice,
    QObject,
    QTimer,
    QUrl,
    Qt,
    SLOT,
    Slot,
)
from PySide6.QtGui import QCursor, QGuiApplication, QImage

try:
    from PySide6.QtDBus import QDBus, QDBusConnection, QDBusMessage
except (ImportError, OSError):  # QtDBus is not shipped on every platform.
    QDBus = None
    QDBusConnection = None
    QDBusMessage = None


PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
PORTAL_SCREENSHOT_INTERFACE = "org.freedesktop.portal.Screenshot"
PORTAL_REQUEST_INTERFACE = "org.freedesktop.portal.Request"
PORTAL_TIMEOUT_MS = 30000


class ScreenCaptureError(RuntimeError):
    pass


if QDBusConnection is not None:

    class _PortalResponse(QObject):
        """Receive one ``org.freedesktop.portal.Request.Response`` signal."""

        def __init__(self, loop):
            super().__init__()
            self.loop = loop
            self.response = None
            self.results = {}

        @Slot("uint", "QVariantMap")
        def on_response(self, response, results):
            self.response = int(response)
            self.results = dict(results)
            self.loop.quit()


def _capture_limits(max_width, jpeg_quality):
    try:
        max_width = max(640, min(3840, int(max_width)))
    except (TypeError, ValueError):
        max_width = 1600
    try:
        jpeg_quality = max(50, min(95, int(jpeg_quality)))
    except (TypeError, ValueError):
        jpeg_quality = 82
    return max_width, jpeg_quality


def _encode_image(image, max_width, jpeg_quality):
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


def _portal_capture(max_width, jpeg_quality):
    """Capture through xdg-desktop-portal, required on Wayland."""
    if QDBusConnection is None:
        raise ScreenCaptureError(
            "D-Bus screenshot support is unavailable in this PySide6 build."
        )

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        raise ScreenCaptureError(
            "Could not connect to the D-Bus session bus. "
            "Make sure xdg-desktop-portal is running."
        )

    sender = bus.baseService()
    if not sender:
        raise ScreenCaptureError("The D-Bus session has no unique name.")

    # The portal predicts this path from the caller's unique name and token,
    # so the Response signal can be connected before the screenshot is taken.
    sender = sender[1:] if sender.startswith(":") else sender
    sender = sender.replace(".", "_")
    token = f"milky{uuid.uuid4().hex}"
    request_path = f"{PORTAL_PATH}/request/{sender}/{token}"

    loop = QEventLoop()
    receiver = _PortalResponse(loop)
    slot = SLOT("on_response(uint,QVariantMap)")
    connected = bus.connect(
        PORTAL_BUS,
        request_path,
        PORTAL_REQUEST_INTERFACE,
        "Response",
        receiver,
        slot,
    )
    if not connected:
        raise ScreenCaptureError(
            "Could not listen for the D-Bus screenshot response."
        )

    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    portal_file = None

    try:
        message = QDBusMessage.createMethodCall(
            PORTAL_BUS,
            PORTAL_PATH,
            PORTAL_SCREENSHOT_INTERFACE,
            "Screenshot",
        )
        message.setArguments(
            [
                "",
                {
                    "handle_token": token,
                    "interactive": False,
                },
            ]
        )
        reply = bus.call(message, QDBus.CallMode.Block, 10000)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            detail = reply.errorMessage() or reply.errorName()
            raise ScreenCaptureError(
                f"The D-Bus screenshot request failed: {detail}"
            )

        if receiver.response is None:
            timer.start(PORTAL_TIMEOUT_MS)
            loop.exec()

        if receiver.response is None:
            raise ScreenCaptureError("The screenshot request timed out.")
        if receiver.response == 1:
            raise ScreenCaptureError("Screenshot permission was cancelled.")
        if receiver.response != 0:
            raise ScreenCaptureError(
                f"The screenshot portal returned response {receiver.response}."
            )

        uri = str(receiver.results.get("uri") or "").strip()
        if not uri:
            raise ScreenCaptureError(
                "The screenshot portal did not return an image file."
            )
        local_path = QUrl(uri).toLocalFile()
        if not local_path:
            raise ScreenCaptureError(
                "The screenshot portal returned an invalid image path."
            )

        portal_file = Path(local_path)
        image = QImage(str(portal_file))
        if image.isNull():
            raise ScreenCaptureError(
                "The screenshot portal returned an unreadable image."
            )
        return _encode_image(image, max_width, jpeg_quality)
    finally:
        timer.stop()
        try:
            bus.disconnect(
                PORTAL_BUS,
                request_path,
                PORTAL_REQUEST_INTERFACE,
                "Response",
                receiver,
                slot,
            )
        except Exception:
            pass
        if portal_file is not None:
            try:
                portal_file.unlink()
            except OSError:
                pass


def _qt_capture(max_width, jpeg_quality):
    """Fallback for X11 and for platforms without a screenshot portal."""
    screen = QGuiApplication.screenAt(QCursor.pos())
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    if screen is None:
        raise ScreenCaptureError("No screen is available.")

    pixmap = screen.grabWindow(0)
    if pixmap.isNull():
        raise ScreenCaptureError("The screen capture was empty.")

    return _encode_image(pixmap.toImage(), max_width, jpeg_quality)


def _is_wayland():
    return bool(os.environ.get("WAYLAND_DISPLAY")) or (
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    )


def capture_screen(max_width=1600, jpeg_quality=82):
    """Return a desktop screenshot as a JPEG-ready payload.

    ``max_width`` limits the larger image dimension.  Downscaling keeps the
    request small enough for cloud vision APIs while preserving readable text.
    On Wayland, capture goes through the desktop portal over D-Bus; Qt's
    ``grabWindow`` is used only as a fallback outside Wayland.
    """
    max_width, jpeg_quality = _capture_limits(max_width, jpeg_quality)

    portal_error = None
    if sys.platform.startswith("linux") and QDBusConnection is not None:
        try:
            return _portal_capture(max_width, jpeg_quality)
        except ScreenCaptureError as error:
            portal_error = error
            # On Wayland, Qt would usually produce a black frame.  Show the
            # portal error instead of silently sending an empty screenshot.
            if _is_wayland():
                raise

    if _is_wayland() and QDBusConnection is None:
        raise ScreenCaptureError(
            "D-Bus screenshot support is unavailable in this PySide6 build."
        )

    try:
        return _qt_capture(max_width, jpeg_quality)
    except ScreenCaptureError as error:
        if portal_error is not None:
            raise ScreenCaptureError(
                f"{portal_error} Qt fallback also failed: {error}"
            ) from error
        raise
