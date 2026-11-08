"""Read-only view of Milky's room."""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QLinearGradient, QRadialGradient
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from room_store import load_room
from ai_client import load_memory
from room_store import update_room_from_memory


class RoomCanvas(QWidget):
    def __init__(self, room, parent=None):
        super().__init__(parent)
        self.room = room
        self.setMinimumSize(720, 430)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        floor_y = int(h * .70)
        wall = QColor(self.room.get("walls", "#f5dfc4"))
        floor = QColor(self.room.get("floor", "#b9825b"))
        gradient = QLinearGradient(0, 0, 0, floor_y)
        gradient.setColorAt(0, wall.lighter(112)); gradient.setColorAt(1, wall)
        painter.fillRect(0, 0, w, floor_y, gradient)
        painter.fillRect(0, floor_y, w, h - floor_y, floor)
        painter.setPen(QPen(floor.darker(125), 2))
        for y in range(floor_y + 18, h, 22): painter.drawLine(0, y, w, y)
        # Window with sky, curtains, crossbars and a soft sun.
        painter.setPen(QPen(QColor("#6b4b49"), 7)); painter.setBrush(QColor("#9ed7e5"))
        painter.drawRect(55, 58, 205, 145)
        painter.setPen(QPen(QColor("#e6f6f4"), 3))
        painter.drawLine(157, 62, 157, 199); painter.drawLine(59, 130, 256, 130)
        painter.setPen(QPen(QColor("#d79a9d"), 16)); painter.drawLine(42, 52, 42, 210); painter.drawLine(270, 52, 270, 210)
        # Rug.
        painter.setPen(QPen(QColor("#c98483"), 3)); painter.setBrush(QColor("#e4a8a0"))
        painter.drawRoundedRect(210, floor_y + 28, 390, 105, 28, 28)
        painter.setPen(QPen(QColor("#f4c7b7"), 2)); painter.drawEllipse(250, floor_y + 45, 310, 70)
        items = [str(item).lower() for item in self.room.get("furniture", [])]
        # Furniture is drawn as a scene, never as a list of labels.
        if any("sofa" in item or "диван" in item for item in items):
            painter.setPen(QPen(QColor("#623f52"), 3)); painter.setBrush(QColor("#9b5d78"))
            painter.drawRoundedRect(285, floor_y - 98, 220, 72, 18, 18); painter.drawRoundedRect(305, floor_y - 145, 180, 62, 16, 16)
            painter.setBrush(QColor("#d99ab0")); painter.drawRoundedRect(320, floor_y - 133, 48, 35, 10, 10); painter.drawRoundedRect(420, floor_y - 133, 48, 35, 10, 10)
        if any("desk" in item or "стол" in item for item in items):
            painter.setPen(QPen(QColor("#4e3025"), 3)); painter.setBrush(QColor("#70452d")); painter.drawRect(w - 205, floor_y - 110, 165, 22)
            painter.drawRect(w - 190, floor_y - 88, 14, 88); painter.drawRect(w - 75, floor_y - 88, 14, 88)
            painter.setBrush(QColor("#8fd0da")); painter.drawRect(w - 160, floor_y - 145, 75, 48)
        if any("plant" in item or "раст" in item or "цвет" in item for item in items):
            painter.setPen(QPen(QColor("#65402f"), 3)); painter.setBrush(QColor("#b87550")); painter.drawEllipse(90, floor_y - 62, 58, 55)
            painter.setPen(QPen(QColor("#397a4e"), 8)); painter.drawLine(119, floor_y - 58, 119, floor_y - 180)
            painter.setBrush(QColor("#4f9b60")); painter.drawEllipse(82, floor_y - 190, 48, 38); painter.drawEllipse(120, floor_y - 165, 53, 38); painter.drawEllipse(105, floor_y - 215, 42, 38)
        if any("aquarium" in item or "аквариум" in item for item in items):
            painter.setPen(QPen(QColor("#315c72"), 4)); painter.setBrush(QColor("#73c9dc")); painter.drawRoundedRect(390, 82, 165, 112, 8, 8)
            painter.setBrush(QColor("#d98842")); painter.drawEllipse(430, 125, 34, 20); painter.drawEllipse(500, 150, 25, 15); painter.setPen(QPen(QColor("#4d9b67"), 4)); painter.drawLine(410, 180, 430, 145); painter.drawLine(465, 180, 480, 135)
        if any("book" in item or "книг" in item or "шкаф" in item for item in items):
            painter.setPen(QPen(QColor("#5b352b"), 6)); painter.drawLine(610, 85, 610, floor_y - 25); painter.drawLine(700, 85, 700, floor_y - 25)
            for y in (115, 160, 205): painter.drawLine(610, y, 700, y)
            for x, color in ((620, "#d75e5e"), (637, "#e4b04f"), (654, "#6b91cf"), (672, "#7ab278")):
                painter.setPen(QPen(QColor(color), 9)); painter.drawLine(x, 95, x, 111)
        # Warm ceiling lamp and glow unify the scene.
        glow = QRadialGradient(w // 2, 20, 130); glow.setColorAt(0, QColor(255, 235, 164, 90)); glow.setColorAt(1, QColor(255, 235, 164, 0))
        painter.setBrush(glow); painter.setPen(Qt.PenStyle.NoPen); painter.drawEllipse(w // 2 - 130, -110, 260, 260)
        painter.setPen(QPen(QColor("#402b27"), 2)); painter.drawText(24, 30, "Milky's room")


class RoomDialog(QDialog):
    """A window for observing; it contains no room controls."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Milky's Room")
        self.resize(760, 540)
        self.canvas = RoomCanvas(load_room())
        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)
        layout.addWidget(QLabel("This is Milky's room. She changes it herself while she lives and grows."))
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(500)

    def refresh(self):
        update_room_from_memory(load_memory())
        self.canvas.room = load_room()
        self.canvas.update()

    def closeEvent(self, event):
        self._refresh_timer.stop()
        super().closeEvent(event)
