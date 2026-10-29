import os
import random
import re
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
    QHBoxLayout,
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
    compact_history,
    configure_history,
    fit_selfie_group,
    fix_selfie_fill,
    history_command,
    load_history,
    load_memory,
    save_history,
    save_memory,
    wants_screen_view,
)
from clothing_art import (
    fallback_clothing,
    wants_clothing,
    wants_wear_overlay,
)
from clothing_overlay import AvatarLabel, clothing_fits, validate_clothing_svg
from outfit_store import infer_slot, load_outfit, save_outfit, wear_item
from runtime import data_path, resource_path
from screen_vision import ScreenCaptureError, capture_screen
from settings_dialog import SettingsDialog
from settings_store import active_provider, load_settings, vision_provider
from svg_art import (
    asked_to_draw,
    draw_for,
    includes_milky,
    is_plain_selfie,
    subject_for,
    wants_selfie,
)
from tts import TtsWorker as TtsSynthesisWorker, AudioPlayer
from web_search import configure_search
from addon_manager import (
    configure_addons,
    set_animation_callback,
    shutdown_addons,
)
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


def apply_runtime_settings(settings):
    """Push search and history options from settings.json into the modules."""
    configure_search(settings.get("search") or {})
    history = settings.get("history") or {}
    configure_history(
        history.get("limit", 20),
        history.get("keep_recent", 6),
    )
    try:
        configure_addons(settings.get("addons") or {})
    except Exception as error:
        print(f"[addons] could not load addons: {error}", flush=True)


class ChatWorker(QThread):

    replied = Signal(dict)
    failed = Signal(str)
    searching = Signal(str)

    def __init__(
        self,
        text,
        history,
        memory,
        provider,
        parent=None,
        image_settings=None,
        vision_provider=None,
        screen_image=None,
    ):
        super().__init__(parent)
        self._text = text
        self._history = history
        self._memory = memory
        self._provider = provider
        self._image_settings = image_settings or {}
        self._vision_provider = vision_provider
        self._screen_image = screen_image

    def run(self):
        try:
            self.replied.emit(
                chat(
                    self._text,
                    self._provider,
                    history=self._history,
                    memory=self._memory,
                    image_settings=self._image_settings,
                    vision_provider=self._vision_provider,
                    screen_image=self._screen_image,
                    on_search=self.searching.emit,
                )
            )
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):

    message_submitted = Signal(str)
    addon_animation = Signal(str, str, int)

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

        self.movie = QMovie(asset_path("assets/gifs/milka_idle.gif"))
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
        self._addon_gif = None
        self._addon_owner = ""
        self._addon_showing = False
        self._addon_animation_timer = QTimer(self)
        self._addon_animation_timer.setSingleShot(True)
        self._addon_animation_timer.timeout.connect(
            self._clear_addon_animation
        )
        self._history = load_history()
        self._memory = load_memory()
        self._settings = load_settings()
        self.addon_animation.connect(
            self._on_addon_animation_request,
            Qt.ConnectionType.QueuedConnection,
        )
        set_animation_callback(self._request_addon_animation)
        apply_runtime_settings(self._settings)
        self._provider = active_provider(self._settings)
        self._drawing_settings = self._settings.get("drawing") or {}
        self._vision_settings = self._settings.get("vision") or {}
        self._life_settings = self._settings.get("life") or {}
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
        self._pending_screen_request = None
        self._screen_question_pending = False
        self._reply_gif = "milka_idle.gif"
        self._toast = None
        self._life_toast = None

        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self.hide_reply)

        self._drawing_timer = QTimer(self)
        self._drawing_timer.setSingleShot(True)
        self._drawing_timer.timeout.connect(self._finish_drawing_animation)

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._hide_drawing_toast)

        self._life_toast_timer = QTimer(self)
        self._life_toast_timer.setSingleShot(True)
        self._life_toast_timer.timeout.connect(self._hide_life_toast)

        self._life_timer = QTimer(self)
        self._life_timer.setSingleShot(True)
        self._life_timer.timeout.connect(self._life_tick)

        self.setup_tray()
        self._schedule_life(first=True)

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
        self._clear_screen_question()
        self.input.setPlaceholderText("Say something...")
        self.input.clear()
        self.set_widget_visible(self.input, False)
        self.set_gif(next_gif)
        if next_gif == "milka_idle.gif":
            self._apply_addon_animation_if_idle()

    def submit_input(self):
        text = self.input.text().strip()

        if self._screen_question_pending:
            request = self._pending_screen_request or "Look at the screen."
            self._clear_screen_question()
            self.input.setPlaceholderText("Say something...")
            combined = self._combine_screen_request(request, text)
            self._submit_message(combined, screen_request=True)
            return

        if not text:
            self.hide_input("milka_listening.gif")
            return

        if not self._screen_question_pending:
            action = history_command(text)
            if action is not None:
                self.hide_input("milka_idle.gif")
                self._apply_history_action(action, text)
                return

        if wants_screen_view(text):
            self._ask_screen_question(text)
            return

        self._submit_message(text)

    def _ask_screen_question(self, request):
        """Ask what to look for before taking a screenshot."""
        if not self._vision_settings.get("enabled", False):
            self.show_status(
                "Screen vision is disabled. Enable it in Settings → Screen vision."
            )
            return

        self._pending_screen_request = str(request or "").strip()
        self._screen_question_pending = True
        self.input.clear()
        self.show_input()
        self.input.setPlaceholderText("What should I look for?")
        self.bubble.setText(
            "What should I look for on the screen? "
            "Type your question and press Enter."
        )
        self.set_widget_visible(self.bubble, True)
        self._bubble_timer.stop()
        self.input.setFocus(Qt.FocusReason.MouseFocusReason)

    def _clear_screen_question(self):
        self._pending_screen_request = None
        self._screen_question_pending = False

    @staticmethod
    def _combine_screen_request(request, question):
        request = " ".join(str(request or "").split()).strip()
        question = " ".join(str(question or "").split()).strip()
        if not request:
            request = "Look at the screen."
        if not question or question.casefold() in request.casefold():
            return request
        return f"{request}\nQuestion about the screen: {question}"

    def _submit_message(self, text, screen_request=False):
        self._bubble_timer.stop()
        self.set_widget_visible(self.bubble, False)
        self.hide_input("milka_thinking.gif")

        screen_image = None
        if screen_request:
            screen_image = self._capture_for_request(text, force=True)
            if screen_image is None:
                return

        self.message_submitted.emit(text)
        self._last_user_text = text
        history = list(self._history)
        self._history.append({"role": "user", "content": text})
        self._history = self._history[-HISTORY_LIMIT:]
        save_history(self._history)
        self.ask_ai(text, history, dict(self._memory), screen_image=screen_image)

    def _apply_history_action(self, action, text):
        russian = bool(re.search(r"[а-яА-ЯЁё]", text))
        if action == "clear":
            self._history = []
            save_history(self._history)
            self.show_status(
                "История очищена." if russian else "History cleared."
            )
            return

        compacted, removed = compact_history(self._history)
        if removed <= 0:
            self.show_status(
                "История и так короткая — сжимать нечего."
                if russian
                else "The history is already short."
            )
            return

        self._history = compacted
        save_history(self._history)
        kept = sum(1 for item in compacted if item.get("role") != "summary")
        if russian:
            message = (
                f"Сжала историю: убрала {removed} старых сообщений, "
                f"оставила последние {kept} и краткую сводку."
            )
        else:
            message = (
                f"Compacted the history: removed {removed} older messages, "
                f"kept the last {kept} and a short summary."
            )
        self.show_status(message)
        self._bubble_timer.start(7000)

    def _capture_for_request(self, text, force=False):
        if not force and not wants_screen_view(text):
            return None
        if not self._vision_settings.get("enabled", False):
            self.show_status(
                "Screen vision is disabled. Enable it in Settings → Screen vision."
            )
            return None
        try:
            return capture_screen(
                max_width=self._vision_settings.get("max_width", 1600),
                jpeg_quality=self._vision_settings.get("jpeg_quality", 82),
            )
        except ScreenCaptureError as error:
            self.show_status(f"Could not capture the screen: {error}")
            return None

    def ask_ai(self, text, history, memory, screen_image=None):
        selected_vision = (
            vision_provider(self._settings) if screen_image is not None else None
        )
        worker = ChatWorker(
            text,
            history,
            memory,
            dict(self._provider),
            self,
            image_settings=dict(self._drawing_settings),
            vision_provider=selected_vision,
            screen_image=screen_image,
        )
        self._worker = worker
        worker.replied.connect(lambda result, w=worker: self.show_reply(w, result))
        worker.failed.connect(lambda error, w=worker: self.show_error(w, error))
        worker.searching.connect(self.on_searching)
        worker.finished.connect(lambda w=worker: self.clear_worker(w))
        worker.start()

    def on_searching(self, query):
        if self._worker is not None:
            self.set_gif("milka_search.gif")

    def look_at_screen(self):
        """Ask what to look for before Milky captures the screen."""
        if self._worker is not None:
            return
        if not self._vision_settings.get("enabled", False):
            self.show_status(
                "Screen vision is disabled. Enable it in Settings → Screen vision."
            )
            return
        self._ask_screen_question("Look at the screen.")

    def clear_worker(self, worker):
        if self._worker is worker:
            self._worker = None
            self._apply_addon_animation_if_idle()

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
            self._restore_base_gif()

    def _life_delay_ms(self):
        try:
            minimum = int(self._life_settings.get("min_minutes", 10))
            maximum = int(self._life_settings.get("max_minutes", 30))
        except (TypeError, ValueError):
            minimum, maximum = 10, 30
        minimum = max(1, minimum)
        maximum = max(minimum, maximum)
        return random.randint(minimum, maximum) * 60 * 1000

    def _schedule_life(self, first=False):
        self._life_timer.stop()
        if not self._life_settings.get("enabled", True):
            return
        if not (
            self._life_settings.get("suggest_outfit", True)
            or self._life_settings.get("draw", True)
        ):
            return
        if first:
            # Make the feature discoverable soon after launch, then settle
            # into the configured interval.
            self._life_timer.start(random.randint(1, 3) * 60 * 1000)
            return
        self._life_timer.start(self._life_delay_ms())

    def _life_tick(self):
        """Run one small spontaneous action, then schedule the next one."""
        self._schedule_life()
        if not self._life_settings.get("enabled", True):
            return
        if (
            self._worker is not None
            or self.input.isVisible()
            or self.bubble.isVisible()
            or self._life_toast is not None
            or not self.isVisible()
        ):
            return
        actions = []
        if self._life_settings.get("suggest_outfit", True):
            actions.append("outfit")
        if self._life_settings.get("draw", True):
            actions.append("draw")
        if not actions:
            return
        if random.choice(actions) == "outfit":
            self._suggest_outfit()
        else:
            self._spontaneous_draw()

    def _suggest_outfit(self):
        options = (
            ("a warm hat", "put on a warm hat"),
            ("round glasses", "put on round glasses"),
            ("a soft scarf", "put on a soft scarf"),
            ("a golden crown", "put on a golden crown"),
            ("a delicate necklace", "put on a delicate necklace"),
            ("a bow tie", "put on a bow tie"),
            ("gold earrings", "put on gold earrings"),
        )
        label, request = random.choice(options)
        self._show_life_toast(
            f"Want me to put on {label}?",
            lambda: self._accept_outfit(request, label),
        )

    def _accept_outfit(self, request, label):
        if not self._apply_wear(None, request):
            self.show_status("I could not find that accessory.")
            return
        self.set_gif(EMOTIONS["happy"])
        self.bubble.setText(f"Okay! I put on {label}.")
        self.set_widget_visible(self.bubble, True)
        self._bubble_timer.start(5000)

    def _spontaneous_draw(self):
        options = (
            ("cat", "a cat"),
            ("dog", "a dog"),
            ("bunny", "a bunny"),
            ("snowman", "a snowman"),
            ("sun", "the sun"),
            ("moon", "the moon"),
            ("star", "a star"),
            ("heart", "a heart"),
            ("flower", "a flower"),
            ("fish", "a fish"),
            ("butterfly", "a butterfly"),
            ("rainbow", "a rainbow"),
            ("tree", "a tree"),
            ("house", "a little house"),
            ("coffee", "a cup of coffee"),
        )
        subject, label = random.choice(options)
        if self._save_drawing(draw_for(subject)) is None:
            return
        self._reply_gif = EMOTIONS["happy"]
        self._play_drawing_animation()
        self._show_drawing_toast()
        self.bubble.setText(f"I felt like drawing {label}.")
        self.set_widget_visible(self.bubble, True)
        self._bubble_timer.start(6000)

    def _show_life_toast(self, text, on_accept):
        """Show a small question above Milky with accept and dismiss buttons."""
        self._hide_life_toast(immediate=True)

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
        content = QWidget(toast)
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setMaximumWidth(270)
        label.setStyleSheet(
            "QLabel {"
            "  background: rgba(32, 28, 44, 238);"
            "  color: white;"
            "  border: 1px solid rgba(255, 255, 255, 90);"
            "  border-left: 4px solid #ff7ab8;"
            "  border-radius: 11px;"
            "  padding: 9px 13px;"
            "  font-size: 13px;"
            "}"
        )
        body.addWidget(label)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(6)
        accept = QPushButton("Sure")
        decline = QPushButton("Not now")
        for button in (accept, decline):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        accept.setStyleSheet(
            "QPushButton {"
            "  background: #ff7ab8;"
            "  color: #241a2c;"
            "  border: none;"
            "  border-radius: 9px;"
            "  padding: 6px 14px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover { background: #ff9cc9; }"
        )
        decline.setStyleSheet(
            "QPushButton {"
            "  background: rgba(32, 28, 44, 238);"
            "  color: white;"
            "  border: 1px solid rgba(255, 255, 255, 90);"
            "  border-radius: 9px;"
            "  padding: 6px 12px;"
            "  font-size: 12px;"
            "}"
            "QPushButton:hover { background: rgba(66, 52, 92, 245); }"
        )
        buttons.addWidget(accept)
        buttons.addWidget(decline)
        buttons.addStretch()
        body.addLayout(buttons)

        outer.addWidget(content)

        effect = QGraphicsOpacityEffect(content)
        effect.setOpacity(0.0)
        content.setGraphicsEffect(effect)
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

        def choose():
            self._hide_life_toast(immediate=True)
            on_accept()

        accept.clicked.connect(choose)
        decline.clicked.connect(self._hide_life_toast)

        toast.show()
        toast.raise_()
        self._life_toast = toast
        self._life_toast_timer.start(20000)

    def _hide_life_toast(self, immediate=False):
        self._life_toast_timer.stop()
        toast = self._life_toast
        if toast is None:
            return
        self._life_toast = None
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
        look_action = menu.addAction("Look at screen")
        look_action.triggered.connect(self.look_at_screen)
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
        movie = QMovie(asset_path("assets/gifs/milka_idle.gif"))
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
        return QIcon(asset_path("assets/milka_idle.svg"))

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
        if target == "milka_idle.gif":
            self._restore_base_gif()
        else:
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
        apply_runtime_settings(self._settings)
        self._provider = active_provider(self._settings)
        self._drawing_settings = self._settings.get("drawing") or {}
        self._vision_settings = self._settings.get("vision") or {}
        self._tts_settings = self._settings.get("tts") or {}
        self._life_settings = self._settings.get("life") or {}
        self._outfit = load_outfit()
        self.gif_label.set_outfit(self._outfit)
        if self._tray is not None:
            self._tray.setToolTip(self.tray_tooltip())
        self._schedule_life()
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
        look_action = menu.addAction("Look at screen")
        look_action.triggered.connect(self.look_at_screen)
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
        self._life_timer.stop()
        self._life_toast_timer.stop()
        self._addon_animation_timer.stop()
        self._hide_drawing_toast(immediate=True)
        self._hide_life_toast(immediate=True)
        # Close drawing preview and gallery
        if self._svg_preview is not None:
            self._svg_preview.close()
            self._svg_preview = None
        if self._svg_gallery is not None:
            self._svg_gallery.close()
            self._svg_gallery = None
        try:
            shutdown_addons()
        except Exception as error:
            print(f"[addons] shutdown failed: {error}", flush=True)
        set_animation_callback(None)

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

    def _request_addon_animation(self, addon_id, source, duration_ms):
        self.addon_animation.emit(addon_id, source, duration_ms)

    def _on_addon_animation_request(self, addon_id, source, duration_ms):
        addon_id = str(addon_id or "").strip()
        source = str(source or "").strip()
        if not source:
            if self._addon_owner == addon_id:
                self._clear_addon_animation()
            return

        path = self._resolve_animation_path(source)
        if path is None:
            print(f"[addons] animation not found: {source}", flush=True)
            return

        self._addon_owner = addon_id
        self._addon_gif = str(path)
        self._addon_animation_timer.stop()
        try:
            duration = int(duration_ms)
        except (TypeError, ValueError):
            duration = 0
        if duration > 0:
            self._addon_animation_timer.start(min(duration, 3600000))
        self._apply_addon_animation_if_idle()

    def _resolve_animation_path(self, source):
        path = Path(source)
        if path.is_absolute() or len(path.parts) > 1:
            candidate = path
        else:
            candidate = resource_path(Path("assets/gifs") / path.name)
        try:
            candidate = candidate.resolve()
        except OSError:
            return None
        if not candidate.is_file():
            return None
        if candidate.suffix.lower() not in {".gif", ".webp", ".mng"}:
            return None
        return candidate

    def _addon_is_idle(self):
        return (
            self._worker is None
            and not self.input.isVisible()
            and not self.bubble.isVisible()
            and self._current_gif != "milka_drawing.gif"
        )

    def _apply_addon_animation_if_idle(self):
        if not self._addon_gif or not self._addon_is_idle():
            return
        if self._addon_showing and self._current_gif == self._addon_gif:
            return
        if self.set_gif_path(self._addon_gif):
            self._addon_showing = True

    def _restore_base_gif(self):
        if self._addon_gif and self._addon_is_idle():
            self._apply_addon_animation_if_idle()
        else:
            self.set_gif("milka_idle.gif")

    def _clear_addon_animation(self):
        self._addon_gif = None
        self._addon_owner = ""
        self._addon_animation_timer.stop()
        if self._addon_showing:
            self._addon_showing = False
            self.set_gif("milka_idle.gif")

    def set_gif(self, filename):
        self._set_gif_source(
            str(filename),
            resource_path(Path("assets/gifs") / filename),
        )

    def set_gif_path(self, path):
        path = Path(path)
        if not path.is_file():
            return False
        self._set_gif_source(str(path), path)
        return True

    def _set_gif_source(self, key, path):
        if key == self._current_gif:
            return
        self._current_gif = key
        self.movie.stop()
        self.movie = QMovie(str(path))
        self.movie.setScaledSize(QSize(GIF_SIZE, GIF_SIZE))
        self.gif_label.setMovie(self.movie)
        self.movie.start()
        if key != self._addon_gif:
            self._addon_showing = False

    def eventFilter(self, watched, event):
        if watched is self.input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.hide_input()
                return True
        return super().eventFilter(watched, event)


def run():
    app = QApplication(sys.argv)
    window = MainWindow()
    app.setQuitOnLastWindowClosed(not window.tray_available())
    window.show()
    app.aboutToQuit.connect(window.shutdown)
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())