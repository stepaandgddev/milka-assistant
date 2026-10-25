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
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import (
    QDesktopServices,
    QGuiApplication,
    QIcon,
    QMovie,
    QMouseEvent,
    QShowEvent,
)
from PySide6.QtCore import (
    Qt,
    QPoint,
    QSize,
    QUrl,
    QEvent,
    Signal,
    QTimer,
    QThread,
)

from ai_client import (
    EMOTIONS,
    chat,
    load_history,
    load_memory,
    save_history,
    save_memory,
)
from runtime import resource_path
from settings_dialog import SettingsDialog
from settings_store import active_provider, load_settings
from tts import TtsWorker as TtsSynthesisWorker, AudioPlayer

GIF_SIZE = 200
HISTORY_LIMIT = 100


def asset_path(relative):
    return str(resource_path(relative))


class ChatWorker(QThread):

    replied = Signal(dict)
    failed = Signal(str)

    def __init__(self, text, history, memory, provider, parent=None):
        super().__init__(parent)
        self._text = text
        self._history = history
        self._memory = memory
        self._provider = provider

    def run(self):
        try:
            self.replied.emit(
                chat(
                    self._text,
                    self._provider,
                    history=self._history,
                    memory=self._memory,
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

        self.gif_label = QLabel(self)
        self.gif_label.setStyleSheet("background: transparent;")
        self.gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gif_label.setFixedSize(GIF_SIZE, GIF_SIZE)
        layout.addWidget(self.gif_label)

        self.movie = QMovie(asset_path("gifs/milka_idle.gif"))
        self.movie.setScaledSize(QSize(GIF_SIZE, GIF_SIZE))
        self.gif_label.setMovie(self.movie)
        self.movie.start()
        self._current_gif = "milka_idle.gif"

        self._is_dragging = False
        self._drag_position = QPoint()
        self._worker = None
        self._history = load_history()
        self._memory = load_memory()
        self._settings = load_settings()
        self._provider = active_provider(self._settings)
        self._positioned = False
        self._tray = None
        self._tts_player = AudioPlayer(self)
        self._tts_settings = self._settings.get("tts") or {}
        self._tts_worker = None

        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self.hide_reply)

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
        history = list(self._history)
        self._history.append({"role": "user", "content": text})
        self._history = self._history[-HISTORY_LIMIT:]
        save_history(self._history)
        self.ask_ai(text, history, dict(self._memory))

    def ask_ai(self, text, history, memory):
        worker = ChatWorker(text, history, memory, dict(self._provider), self)
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

        self.set_gif(EMOTIONS.get(emotion, EMOTIONS["speaking"]))

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

    def open_settings(self):
        dialog = SettingsDialog(self._settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._settings = load_settings()
        self._provider = active_provider(self._settings)
        self._tts_settings = self._settings.get("tts") or {}
        if self._tray is not None:
            self._tray.setToolTip(self.tray_tooltip())
        self.show_status(f"Active endpoint: {self._provider.get('name', 'AI')}")

    def show_status(self, text):
        self._bubble_timer.stop()
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