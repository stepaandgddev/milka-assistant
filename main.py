import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

if (
    sys.platform.startswith("linux")
    and not os.environ.get("QT_QPA_PLATFORM")
    and os.environ.get("WAYLAND_DISPLAY")
    and os.environ.get("DISPLAY")
):
    os.environ["QT_QPA_PLATFORM"] = "xcb"

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGraphicsOpacityEffect,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import (
    QDesktopServices,
    QGuiApplication,
    QIcon,
    QImage,
    QImageReader,
    QMovie,
    QMouseEvent,
    QPainter,
    QPixmap,
    QShowEvent,
)
from PySide6.QtCore import (
    Qt,
    QByteArray,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    QUrl,
    QEvent,
    Signal,
    QTimer,
    QThread,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QSvgWidget

from ai_client import (
    EMOTIONS,
    SELFIE_SIGNATURE,
    chat,
    fit_selfie_group,
    fix_selfie_fill,
    load_history,
    load_memory,
    save_history,
    save_memory,
)
from clothing_art import (
    fallback_clothing,
    wants_clothing,
    wants_wear_overlay,
)
from clothing_overlay import AvatarLabel, clothing_fits, validate_clothing_svg
from outfit_store import infer_slot, load_outfit, save_outfit, wear_item
from runtime import data_path, resource_path
from settings_dialog import SettingsDialog
from settings_store import active_provider, load_settings
from svg_art import (
    asked_to_draw,
    draw_for,
    includes_milky,
    is_plain_selfie,
    subject_for,
    wants_selfie,
)
from tts import TtsWorker as TtsSynthesisWorker, AudioPlayer
GIF_SIZE = 200
HISTORY_LIMIT = 100
SVG_DIR = data_path("svg_drawings")
DRAWING_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg", ".webp"}


def asset_path(relative):
    return str(resource_path(relative))


def drawing_files():
    """Return every gallery drawing, in both SVG and raster formats."""
    if not SVG_DIR.exists():
        return []
    try:
        files = [
            path
            for path in SVG_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in DRAWING_EXTENSIONS
        ]
    except OSError:
        return []
    return files


def drawing_mtime(path):
    try:
        return path.stat().st_mtime
    except OSError:
        return 0


def repair_saved_selfies():
    """Fix older drawings where copied self-portrait paths got a black fill."""
    for svg_file in SVG_DIR.glob("*.svg"):
        try:
            code = svg_file.read_text(encoding="utf-8")
        except OSError:
            continue
        fixed = fit_selfie_group(fix_selfie_fill(code))
        if fixed == code:
            continue
        try:
            svg_file.write_text(fixed, encoding="utf-8")
        except OSError:
            pass


class ChatWorker(QThread):

    replied = Signal(dict)
    failed = Signal(str)

    def __init__(
        self, text, history, memory, provider, parent=None, image_settings=None
    ):
        super().__init__(parent)
        self._text = text
        self._history = history
        self._memory = memory
        self._provider = provider
        self._image_settings = image_settings or {}

    def run(self):
        try:
            self.replied.emit(
                chat(
                    self._text,
                    self._provider,
                    history=self._history,
                    memory=self._memory,
                    image_settings=self._image_settings,
                )
            )
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):

    message_submitted = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Milky")
        self.resize(GIF_SIZE, GIF_SIZE)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )

        central_widget = QWidget()
        central_widget.setStyleSheet("background: transparent;")
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Say something...")
        self.input.setFixedWidth(GIF_SIZE)
        self.input.setStyleSheet(
            "QLineEdit {"
            "  background: rgba(25, 25, 25, 220);"
            "  color: white;"
            "  border: 1px solid rgba(255, 255, 255, 90);"
            "  border-radius: 9px;"
            "  padding: 5px 9px;"
            "}"
        )
        self.input.hide()
        self.input.returnPressed.connect(self.submit_input)
        self.input.installEventFilter(self)
        layout.addWidget(self.input)

        self.bubble = QLabel(self)
        self.bubble.setWordWrap(True)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bubble.setFixedWidth(GIF_SIZE)
        self.bubble.setStyleSheet(
            "QLabel {"
            "  background: rgba(255, 255, 255, 235);"
            "  color: #222;"
            "  border: 1px solid rgba(0, 0, 0, 40);"
            "  border-radius: 10px;"
            "  padding: 8px 10px;"
            "  font-size: 14px;"
            "}"
        )
        self.bubble.hide()
        layout.addWidget(self.bubble)

        self.gif_label = AvatarLabel(self)
        self.gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gif_label.setFixedSize(GIF_SIZE, GIF_SIZE)
        layout.addWidget(self.gif_label)

        self._outfit = load_outfit()
        self.gif_label.set_outfit(self._outfit)

        self.movie = QMovie(asset_path("gifs/milka_idle.gif"))
        self.movie.setScaledSize(QSize(GIF_SIZE, GIF_SIZE))
        self.gif_label.setMovie(self.movie)
        self.movie.start()
        self._current_gif = "milka_idle.gif"

        # SVG drawings directory
        SVG_DIR.mkdir(parents=True, exist_ok=True)
        repair_saved_selfies()
        self._drawing_counter = len(drawing_files())

        self._is_dragging = False
        self._drag_position = QPoint()
        self._worker = None
        self._history = load_history()
        self._memory = load_memory()
        self._settings = load_settings()
        self._provider = active_provider(self._settings)
        self._drawing_settings = self._settings.get("drawing") or {}
        self._positioned = False
        self._tray = None
        self._tts_player = AudioPlayer(self)
        self._tts_settings = self._settings.get("tts") or {}
        self._tts_worker = None
        self._svg_gallery = None
        self._svg_gallery_placed = False
        self._svg_grid = None
        self._svg_preview = None
        self._last_user_text = None
        self._reply_gif = "milka_idle.gif"
        self._toast = None

        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self.hide_reply)

        self._drawing_timer = QTimer(self)
        self._drawing_timer.setSingleShot(True)
        self._drawing_timer.timeout.connect(self._finish_drawing_animation)

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._hide_drawing_toast)

        self.setup_tray()

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if not self._positioned:
            self.position_in_corner()
            self._positioned = True

    def position_in_corner(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        screen_geometry = screen.availableGeometry()
        padding = 10
        self.adjustSize()
        x = screen_geometry.x() + screen_geometry.width() - self.width() - padding * 3
        y = screen_geometry.y() + screen_geometry.height() - self.height() - padding
        self.move(x, y)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and not self._is_dragging:
            if self.input.isVisible():
                self.hide_input()
            else:
                self.show_input()
        event.accept()

    def show_input(self):
        self._bubble_timer.stop()
        self.set_widget_visible(self.bubble, False)
        self.set_gif("milka_listening.gif")
        self.set_widget_visible(self.input, True)
        self.raise_()
        self.activateWindow()
        self.input.setFocus(Qt.FocusReason.MouseFocusReason)

    def hide_input(self, next_gif="milka_idle.gif"):
        self.input.clear()
        self.set_widget_visible(self.input, False)
        self.set_gif(next_gif)

    def submit_input(self):
        text = self.input.text().strip()
        if not text:
            self.hide_input("milka_listening.gif")
            return
        self.hide_input("milka_thinking.gif")
        self.message_submitted.emit(text)
        self._last_user_text = text
        history = list(self._history)
        self._history.append({"role": "user", "content": text})
        self._history = self._history[-HISTORY_LIMIT:]
        save_history(self._history)
        self.ask_ai(text, history, dict(self._memory))

    def ask_ai(self, text, history, memory):
        worker = ChatWorker(
            text,
            history,
            memory,
            dict(self._provider),
            self,
            image_settings=dict(self._drawing_settings),
        )
        self._worker = worker
        worker.replied.connect(lambda result, w=worker: self.show_reply(w, result))
        worker.failed.connect(lambda error, w=worker: self.show_error(w, error))
        worker.finished.connect(lambda w=worker: self.clear_worker(w))
        worker.start()

    def clear_worker(self, worker):
        if self._worker is worker:
            self._worker = None

    def show_reply(self, worker, result):
        if worker is not self._worker or self.input.isVisible():
            return
        emotion = result.get("emotion") or "speaking"
        text = result.get("text") or ""
        memories = result.get("memories") or []
        if memories:
            for item in memories:
                self._memory[item["key"]] = item["value"]
            save_memory(self._memory)
        search_query = result.get("search_query")
        urls = []
        if search_query:
            urls.append(
                "https://www.google.com/search?q=" + quote_plus(search_query)
            )
        for url in result.get("open_urls") or []:
            if url not in urls:
                urls.append(url)
        for url in urls:
            parsed = QUrl(url)
            if parsed.scheme().lower() in ("http", "https") and parsed.host():
                QDesktopServices.openUrl(parsed)

        self._drawing_timer.stop()
        self._reply_gif = EMOTIONS.get(emotion, EMOTIONS["speaking"])
        self.set_gif(self._reply_gif)

        # Validate generated clothing (face-safe layering), then save any
        # drawing to the gallery instead of replacing Milky's face.
        request = self._last_user_text or ""
        wear_applied = self._apply_wear(result.get("wear"), request)
        saved_image = None
        image = result.get("image")
        if isinstance(image, dict):
            saved_image = self._save_raster_drawing(image)
        if saved_image is not None:
            self._play_drawing_animation()
            self._show_drawing_toast()
        else:
            svg_code = result.get("svg")
            if svg_code and not self._svg_is_valid(svg_code):
                svg_code = None
            if (
                svg_code
                and not wants_selfie(request)
                and not includes_milky(request)
                and subject_for(request) not in (None, "selfie")
                and SELFIE_SIGNATURE in svg_code
            ):
                svg_code = None
            if wants_selfie(request) and is_plain_selfie(request):
                svg_code = draw_for(request)
            elif not svg_code and asked_to_draw(request):
                svg_code = draw_for(request)
            if (wear_applied or wants_clothing(request)) and not asked_to_draw(
                request
            ):
                # Clothing overlays are not gallery drawings.
                svg_code = None
            if svg_code and self._save_drawing(svg_code):
                self._play_drawing_animation()
                self._show_drawing_toast()

        if not text:
            self._bubble_timer.start(1500)
            return
        self._history.append({"role": "assistant", "content": text})
        self._history = self._history[-HISTORY_LIMIT:]
        save_history(self._history)
        self.bubble.setText(text)
        self.set_widget_visible(self.bubble, True)
        duration = max(4000, min(15000, len(text) * 90))
        self._bubble_timer.start(duration)
        # Speak the reply if TTS is enabled
        self._speak_reply(text)

    def _speak_reply(self, text):
        if not self._tts_settings.get("enabled"):
            return
        provider = self._tts_settings.get("provider", "milka")
        if provider == "groq" and not self._tts_settings.get("groq_api_key"):
            return
        self._tts_worker = TtsSynthesisWorker(text, self._tts_settings, self)
        self._tts_worker.ready.connect(lambda path: self._play_tts_audio(path))
        self._tts_worker.failed.connect(lambda err: print(f"TTS error: {err}"))
        self._tts_worker.start()

    def _play_tts_audio(self, path):
        self._tts_player.play(Path(path))

    def show_error(self, worker, error):
        if worker is not self._worker or self.input.isVisible():
            return
        self._drawing_timer.stop()
        # A provider failure should not leave a simple clothing request empty.
        self._apply_wear(None, self._last_user_text or "")
        message = " ".join(error.split())
        if len(message) > 180:
            message = message[:177] + "..."
        self.set_gif(EMOTIONS["sad"])
        provider_name = self._provider.get("name", "AI")
        self.bubble.setText(f"Error {provider_name}: {message}")
        self.set_widget_visible(self.bubble, True)
        self._bubble_timer.start(8000)

    def hide_reply(self):
        self.set_widget_visible(self.bubble, False)
        if self._current_gif != "milka_drawing.gif":
            self.set_gif("milka_idle.gif")

    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self.tray_icon(), self)
        self._tray.setToolTip(self.tray_tooltip())
        menu = QMenu(self)
        toggle_action = menu.addAction("Show / Hide")
        toggle_action.triggered.connect(self.toggle_window)
        settings_action = menu.addAction("Settings...")
        settings_action.triggered.connect(self.open_settings)
        svg_action = menu.addAction("Show drawing gallery")
        svg_action.triggered.connect(self.show_svg_gallery)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)
        self._tray_menu = menu
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self.on_tray_activated)
        self._tray.show()

    def tray_available(self):
        return self._tray is not None and self._tray.isVisible()

    def tray_icon(self):
        movie = QMovie(asset_path("gifs/milka_idle.gif"))
        movie.jumpToFrame(0)
        pixmap = movie.currentPixmap()
        if not pixmap.isNull():
            return QIcon(
                pixmap.scaled(
                    64,
                    64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        return QIcon(asset_path("milka_idle.svg"))

    def tray_tooltip(self):
        return (
            f"Milky — {self._provider.get('name', 'AI')} / "
            f"{self._provider.get('model', '')}"
        )

    def on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.toggle_window()

    def toggle_window(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _svg_is_valid(self, svg_code):
        renderer = QSvgRenderer(QByteArray(svg_code.encode("utf-8")))
        return renderer.isValid()

    def _fallback_clothing(self, request):
        if not request or asked_to_draw(request):
            return None
        return fallback_clothing(request)

    def _apply_wear(self, wear, request):
        """Validate, persist, and display one generated clothing item."""
        # A drawing request must not secretly dress Milky.  "Draw a cat
        # wearing a hat" describes the picture, not a request for an overlay;
        # only a direct imperative ("надень", "put on") counts.
        if asked_to_draw(request) and not wants_wear_overlay(request):
            return False
        svg = None
        name = ""
        slot = ""
        if isinstance(wear, dict):
            svg = validate_clothing_svg(wear.get("svg"))
            name = str(wear.get("name") or "").strip()
            slot = str(wear.get("slot") or "").strip()
            if svg:
                slot = infer_slot(name, slot)
                if not clothing_fits(slot, svg, name):
                    fallback = self._fallback_clothing(request)
                    if fallback is not None:
                        name, slot, svg = fallback
                        svg = validate_clothing_svg(svg)
                        if not svg:
                            return False
        if not svg:
            fallback = self._fallback_clothing(request)
            if fallback is None:
                return False
            name, slot, svg = fallback
            svg = validate_clothing_svg(svg)
            if not svg:
                return False

        items, item = wear_item(self._outfit, name, slot, svg)
        if item is None:
            fallback = self._fallback_clothing(request)
            if fallback is None:
                return False
            name, slot, svg = fallback
            items, item = wear_item(self._outfit, name, slot, svg)
            if item is None:
                return False

        try:
            self._outfit = save_outfit(items)
        except OSError as error:
            print(f"Outfit save error: {error}")
            # Show the item now even if the disk write failed.
            self._outfit = items
        self.gif_label.set_outfit(self._outfit)
        return True

    def _next_drawing_path(self, extension):
        SVG_DIR.mkdir(parents=True, exist_ok=True)
        index = self._drawing_counter + 1
        path = SVG_DIR / f"milky_draw_{index}{extension}"
        while path.exists():
            index += 1
            path = SVG_DIR / f"milky_draw_{index}{extension}"
        return index, path

    def _save_drawing(self, svg_code):
        """Write a new SVG drawing to the gallery folder."""
        index, path = self._next_drawing_path(".svg")
        try:
            path.write_text(svg_code, encoding="utf-8")
        except OSError:
            return None
        self._drawing_counter = index
        self._refresh_svg_gallery()
        return path

    def _save_raster_drawing(self, image):
        """Write a Cloudflare PNG/JPEG/WebP drawing to the gallery folder."""
        data = image.get("data") if isinstance(image, dict) else None
        if not isinstance(data, (bytes, bytearray)) or not data:
            return None
        extension = str(image.get("ext") or "").lower()
        if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
            extension = ".jpg"
        index, path = self._next_drawing_path(extension)
        try:
            path.write_bytes(bytes(data))
        except OSError:
            return None
        self._drawing_counter = index
        self._refresh_svg_gallery()
        return path

    def _play_drawing_animation(self):
        """Play the drawing GIF while the new artwork is announced."""
        if self._current_gif == "milka_drawing.gif":
            self.movie.stop()
            self.movie.start()
        else:
            self.set_gif("milka_drawing.gif")
        self._drawing_timer.start(6000)

    def _finish_drawing_animation(self):
        target = self._reply_gif if self.bubble.isVisible() else "milka_idle.gif"
        if target == "milka_drawing.gif":
            target = "milka_idle.gif"
        self.set_gif(target)

    def _show_drawing_toast(self):
        """Show an animated notification above Milky's face."""
        self._hide_drawing_toast(immediate=True)

        toast = QWidget(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        toast.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        toast.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        outer = QVBoxLayout(toast)
        outer.setContentsMargins(0, 0, 0, 0)

        button = QPushButton("Новый рисунок в галерее!")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton {"
            "  background: rgba(32, 28, 44, 238);"
            "  color: white;"
            "  border: 1px solid rgba(255, 255, 255, 90);"
            "  border-left: 4px solid #ff7ab8;"
            "  border-radius: 11px;"
            "  padding: 9px 14px 9px 11px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(66, 52, 92, 245);"
            "}"
        )
        button.clicked.connect(self._open_gallery_from_toast)
        outer.addWidget(button)

        effect = QGraphicsOpacityEffect(button)
        effect.setOpacity(0.0)
        button.setGraphicsEffect(effect)
        toast._fade_effect = effect

        toast.adjustSize()
        position = self._toast_position(toast)
        toast.move(position.x(), position.y() + 14)

        fade = QPropertyAnimation(effect, b"opacity", toast)
        fade.setDuration(220)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        slide = QPropertyAnimation(toast, b"pos", toast)
        slide.setDuration(280)
        slide.setStartValue(QPoint(position.x(), position.y() + 14))
        slide.setEndValue(position)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        slide.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        toast.show()
        toast.raise_()
        self._toast = toast
        self._toast_timer.start(4600)

    def _toast_position(self, toast):
        geometry = self.frameGeometry()
        x = geometry.center().x() - toast.width() // 2
        y = geometry.top() - toast.height() - 10
        screen = QGuiApplication.screenAt(geometry.center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            x = max(area.left() + 6, min(x, area.right() - toast.width() - 6))
            if y < area.top() + 6:
                y = geometry.bottom() + 10
        return QPoint(x, y)

    def _hide_drawing_toast(self, immediate=False):
        self._toast_timer.stop()
        toast = self._toast
        if toast is None:
            return
        self._toast = None
        effect = getattr(toast, "_fade_effect", None)
        if immediate or effect is None:
            toast.close()
            toast.deleteLater()
            return
        fade = QPropertyAnimation(effect, b"opacity", toast)
        fade.setDuration(260)
        fade.setStartValue(effect.opacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.Type.InCubic)
        fade.finished.connect(toast.close)
        fade.finished.connect(toast.deleteLater)
        fade.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _open_gallery_from_toast(self):
        self._hide_drawing_toast(immediate=True)
        self.show_svg_gallery()

    def show_svg_gallery(self):
        """Open a scrollable gallery with previews of every SVG/raster drawing."""
        if self._svg_gallery is None:
            self._build_svg_gallery()
        if not self._svg_gallery_placed:
            self._center_on_screen(self._svg_gallery)
            self._svg_gallery_placed = True
        self._populate_svg_gallery()
        self._svg_gallery.show()
        self._svg_gallery.raise_()
        self._svg_gallery.activateWindow()

    def _center_on_screen(self, window):
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = area.center().x() - window.width() // 2
        y = area.center().y() - window.height() // 2
        window.move(x, y)

    def _build_svg_gallery(self):
        gallery = QWidget(
            self,
            Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint,
        )
        gallery.setWindowTitle("Milky's Drawings")
        gallery.resize(680, 560)

        outer = QVBoxLayout(gallery)
        hint = QLabel("Click a drawing to view it larger. Use Delete to remove it.")
        hint.setStyleSheet("color: #666;")
        outer.addWidget(hint)

        scroll = QScrollArea(gallery)
        scroll.setWidgetResizable(True)
        host = QWidget()
        grid = QGridLayout(host)
        grid.setSpacing(12)
        grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        scroll.setWidget(host)
        outer.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(gallery.close)
        outer.addWidget(close_btn)

        self._svg_gallery = gallery
        self._svg_grid = grid

    def _populate_svg_gallery(self):
        grid = self._svg_grid
        if grid is None:
            return
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        svg_files = sorted(
            drawing_files(),
            key=drawing_mtime,
            reverse=True,
        )
        if not svg_files:
            grid.addWidget(
                QLabel("No drawings yet. Ask Milky to draw something!"),
                0,
                0,
            )
            return

        for index, svg_file in enumerate(svg_files):
            tile = QWidget()
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(0, 0, 0, 0)
            tile_layout.setSpacing(2)

            button = QToolButton(tile)
            button.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextUnderIcon
            )
            button.setIcon(self._svg_thumbnail(svg_file))
            button.setIconSize(QSize(136, 136))
            button.setText(svg_file.stem)
            button.setToolTip(f"{svg_file.name} — click to enlarge")
            button.clicked.connect(
                lambda checked=False, path=svg_file: self._show_svg_preview(path)
            )
            tile_layout.addWidget(button)

            delete_btn = QPushButton("Delete", tile)
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setToolTip(f"Delete {svg_file.name}")
            delete_btn.setStyleSheet(
                "QPushButton {"
                "  border: none;"
                "  background: transparent;"
                "  color: #b04a6a;"
                "  font-size: 11px;"
                "  padding: 0;"
                "}"
                "QPushButton:hover { color: #d21f4f; }"
            )
            delete_btn.clicked.connect(
                lambda checked=False, path=svg_file: self._delete_svg(path)
            )
            tile_layout.addWidget(
                delete_btn, alignment=Qt.AlignmentFlag.AlignHCenter
            )

            grid.addWidget(tile, index // 4, index % 4)

    def _delete_svg(self, svg_file):
        gallery = self._svg_gallery or self
        answer = QMessageBox.question(
            gallery,
            "Delete drawing",
            f"Delete {svg_file.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            svg_file.unlink()
        except OSError as error:
            QMessageBox.warning(
                gallery,
                "Delete drawing",
                f"Could not delete {svg_file.name}:\n{error}",
            )
            return
        if (
            self._svg_preview is not None
            and getattr(self._svg_preview, "_svg_path", None) == svg_file
        ):
            self._svg_preview.close()
            self._svg_preview.deleteLater()
            self._svg_preview = None
        self._populate_svg_gallery()

    def _refresh_svg_gallery(self):
        if self._svg_gallery is not None and self._svg_gallery.isVisible():
            self._populate_svg_gallery()

    def _svg_thumbnail(self, svg_file):
        side = 136
        pixmap = QPixmap(side * 2, side * 2)
        pixmap.setDevicePixelRatio(2.0)
        pixmap.fill(Qt.GlobalColor.transparent)
        if svg_file.suffix.lower() == ".svg":
            renderer = QSvgRenderer(str(svg_file))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(painter, QRectF(0, 0, side, side))
            painter.end()
            return QIcon(pixmap)

        reader = QImageReader(str(svg_file))
        reader.setAutoTransform(True)
        image_size = reader.size()
        if image_size.isValid():
            image_size.scale(
                QSize(side * 2, side * 2),
                Qt.AspectRatioMode.KeepAspectRatio,
            )
            reader.setScaledSize(image_size)
        source = QPixmap.fromImage(reader.read())
        if source.isNull():
            return QIcon()
        source = source.scaled(
            side * 2,
            side * 2,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter = QPainter(pixmap)
        x = (side * 2 - source.width()) // 2
        y = (side * 2 - source.height()) // 2
        painter.drawPixmap(x, y, source)
        painter.end()
        return QIcon(pixmap)

    def _show_svg_preview(self, svg_file):
        if self._svg_preview is not None:
            self._svg_preview.close()
            self._svg_preview.deleteLater()
            self._svg_preview = None

        preview = QWidget(
            self,
            Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint,
        )
        preview.setWindowTitle(f"Milky — {svg_file.stem}")
        preview.resize(560, 620)

        layout = QVBoxLayout(preview)
        if svg_file.suffix.lower() == ".svg":
            artwork = QSvgWidget(str(svg_file))
            artwork.setFixedSize(520, 520)
        else:
            artwork = QLabel()
            artwork.setFixedSize(520, 520)
            artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap(str(svg_file))
            if pixmap.isNull():
                artwork.setText("Could not load this drawing.")
            else:
                artwork.setPixmap(
                    pixmap.scaled(
                        520,
                        520,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        layout.addWidget(artwork, alignment=Qt.AlignmentFlag.AlignCenter)

        caption = QLabel(svg_file.name)
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setStyleSheet("color: #666;")
        layout.addWidget(caption)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(preview.close)
        layout.addWidget(close_btn)

        self._svg_preview = preview
        preview._svg_path = svg_file
        self._center_on_screen(preview)
        preview.show()
        preview.raise_()

    def open_settings(self):
        dialog = SettingsDialog(self._settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._settings = load_settings()
        self._provider = active_provider(self._settings)
        self._drawing_settings = self._settings.get("drawing") or {}
        self._tts_settings = self._settings.get("tts") or {}
        self._outfit = load_outfit()
        self.gif_label.set_outfit(self._outfit)
        if self._tray is not None:
            self._tray.setToolTip(self.tray_tooltip())
        self.show_status(f"Active endpoint: {self._provider.get('name', 'AI')}")

    def show_status(self, text):
        self._bubble_timer.stop()
        self._drawing_timer.stop()
        self.set_gif("milka_idle.gif")
        self.bubble.setText(text)
        self.set_widget_visible(self.bubble, True)
        self._bubble_timer.start(4000)

    def quit_app(self):
        self.shutdown()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        settings_action = menu.addAction("Settings...")
        settings_action.triggered.connect(self.open_settings)
        toggle_action = menu.addAction("Show / Hide")
        toggle_action.triggered.connect(self.toggle_window)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)
        menu.exec(event.globalPos())

    def shutdown(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(3000)
            if self._worker.isRunning():
                self._worker.terminate()
                self._worker.wait(1000)
        # Stop TTS player
        if self._tts_player is not None:
            self._tts_player.stop()
        self._drawing_timer.stop()
        self._toast_timer.stop()
        self._hide_drawing_toast(immediate=True)
        # Close drawing preview and gallery
        if self._svg_preview is not None:
            self._svg_preview.close()
            self._svg_preview = None
        if self._svg_gallery is not None:
            self._svg_gallery.close()
            self._svg_gallery = None

    def closeEvent(self, event):
        if self._tray is not None and self._tray.isVisible():
            self.hide()
            event.ignore()
            return
        self.shutdown()
        super().closeEvent(event)

    def set_widget_visible(self, widget, visible):
        if widget.isVisible() == visible:
            return
        bottom_right = self.frameGeometry().bottomRight()
        widget.setVisible(visible)
        self.centralWidget().layout().activate()
        self.adjustSize()
        self.move(
            bottom_right.x() - self.width() + 1,
            bottom_right.y() - self.height() + 1,
        )

    def set_gif(self, filename):
        if filename == self._current_gif:
            return
        self._current_gif = filename
        self.movie.stop()
        self.movie = QMovie(asset_path(Path("gifs") / filename))
        self.movie.setScaledSize(QSize(GIF_SIZE, GIF_SIZE))
        self.gif_label.setMovie(self.movie)
        self.movie.start()

    def eventFilter(self, watched, event):
        if watched is self.input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.hide_input()
                return True
        return super().eventFilter(watched, event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    app.setQuitOnLastWindowClosed(not window.tray_available())
    window.show()
    app.aboutToQuit.connect(window.shutdown)
    sys.exit(app.exec())