"""Readable memory graph: a central user hub and spacious fact cards."""

import math
from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QWidget, QToolTip

from memory_graph import delete_fact, get_fact_nodes, get_relations, load_memory_history

COLORS = {
    "person": ("#ffd6e7", "#c83d70"),
    "location": ("#c8f4ef", "#168f86"),
    "interest": ("#fff1b8", "#b78300"),
    "preference": ("#d9f7df", "#32915a"),
    "work": ("#ffe0c2", "#b96718"),
    "fact": ("#e4e8f4", "#52658f"),
}


class MemoryGraphWidget(QWidget):
    node_selected = Signal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.nodes = []
        self.relations = []
        self.positions = {}
        self.hovered = None
        self.selected = None
        self.filter_text = ""
        self.filter_type = "all"
        self.search_results = []
        self.setMinimumSize(1000, 760)
        self.setMouseTracking(True)
        self.zoom = 1.0
        self.offset = QPointF(0, 0)
        self._dragging = False
        self._last_mouse = QPointF()
        self.refresh()

    def refresh(self):
        self.nodes = get_fact_nodes()
        if self.filter_text or self.filter_type != "all":
            needle = self.filter_text.casefold()
            self.nodes = [
                n for n in self.nodes
                if (not needle or needle in str(n.get("label", "")).casefold() or needle in str(n.get("key", "")).casefold())
                and (self.filter_type == "all" or n.get("type") == self.filter_type)
            ]
        self.relations = get_relations()
        self._layout()
        self.update()

    def _layout(self):
        w, h = max(self.width(), 1000), max(self.height(), 760)
        self.positions = {"__user__": (w // 2, h // 2)}
        facts = self.nodes
        rings = max(1, math.ceil(len(facts) / 6))
        for i, node in enumerate(facts):
            ring = i // 6 + 1
            index = i % 6
            count = min(6, len(facts) - (ring - 1) * 6)
            angle = -math.pi / 2 + index * (2 * math.pi / max(1, count))
            radius = min(w, h) * 0.30 * ring
            self.positions[node["id"]] = (
                int(w / 2 + math.cos(angle) * radius),
                int(h / 2 + math.sin(angle) * radius),
            )

    def _card_rect(self, node_id):
        x, y = self.positions[node_id]
        if node_id == "__user__":
            return x - 72, y - 32, 144, 64
        return x - 92, y - 35, 184, 70

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # The background belongs to the viewport, not to the movable graph.
        # Paint it before applying pan/zoom so no grey area appears while
        # navigating beyond the original graph position.
        painter.fillRect(self.rect(), QColor("#f7f8fc"))
        painter.save()
        painter.translate(self.offset)
        painter.scale(self.zoom, self.zoom)

        # Soft grid improves orientation without competing with text.
        painter.setPen(QPen(QColor("#e6e9f2"), 1))
        for x in range(0, self.width(), 40): painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 40): painter.drawLine(0, y, self.width(), y)

        for relation in self.relations:
            a, b = relation.get("from"), relation.get("to")
            if a not in self.positions or b not in self.positions: continue
            x1, y1 = self.positions[a]; x2, y2 = self.positions[b]
            painter.setPen(QPen(QColor("#aeb7cb"), 2))
            painter.drawLine(x1, y1, x2, y2)

        for node in self.nodes:
            self._draw_card(painter, node)
        if self.nodes:
            x, y = self.positions["__user__"]
            painter.setBrush(QColor("#536dfe")); painter.setPen(QPen(QColor("#3046c5"), 3))
            painter.drawRoundedRect(x - 72, y - 32, 144, 64, 18, 18)
            painter.setPen(Qt.GlobalColor.white); painter.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
            painter.drawText(x - 65, y - 10, 130, 24, Qt.AlignmentFlag.AlignCenter, "You")
            painter.setFont(QFont("sans-serif", 9)); painter.drawText(x - 65, y + 10, 130, 16, Qt.AlignmentFlag.AlignCenter, "memory hub")
        painter.restore()

    def _draw_card(self, painter, node):
        node_id = node["id"]; x, y = self.positions[node_id]
        bg, accent = COLORS.get(node.get("type"), COLORS["fact"])
        left, top, width, height = self._card_rect(node_id)
        selected = node_id == self.hovered
        painter.setBrush(QColor(bg)); painter.setPen(QPen(QColor(accent), 3 if selected else 2))
        painter.drawRoundedRect(left, top, width, height, 14, 14)
        painter.setPen(QColor(accent)); painter.setFont(QFont("sans-serif", 9, QFont.Weight.Bold))
        painter.drawText(left + 12, top + 18, width - 24, 16, 0, node.get("type", "fact").upper())
        painter.setPen(QColor("#202637")); painter.setFont(QFont("sans-serif", 11, QFont.Weight.Bold))
        painter.drawText(left + 12, top + 39, width - 24, 25, int(Qt.TextFlag.TextWordWrap), str(node.get("label", ""))[:70])

    def mouseMoveEvent(self, event):
        if self._dragging:
            current = event.position()
            self.offset += current - self._last_mouse
            self._last_mouse = current
            self.update()
            return
        self.hovered = None
        graph_pos = (event.position() - self.offset) / self.zoom
        for node in self.nodes:
            left, top, width, height = self._card_rect(node["id"])
            if left <= graph_pos.x() <= left + width and top <= graph_pos.y() <= top + height:
                self.hovered = node["id"]
                QToolTip.showText(event.globalPosition().toPoint(), f"{node['key']}: {node['label']}", self)
                break
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            return
        graph_pos = (event.position() - self.offset) / self.zoom
        self.selected = None
        on_card = False
        for node in self.nodes:
            left, top, width, height = self._card_rect(node["id"])
            if left <= graph_pos.x() <= left + width and top <= graph_pos.y() <= top + height:
                on_card = True
                self.selected = node["id"]
                self.node_selected.emit(node)
                break
        if event.button() == Qt.MouseButton.MiddleButton or not on_card:
            self._dragging = True
            self._last_mouse = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.update()

    def delete_selected(self):
        if not self.selected:
            return False
        deleted = delete_fact(self.selected)
        if deleted:
            self.selected = None
            self.refresh()
        return deleted

    def history_text(self):
        history = load_memory_history()
        if not history:
            return "No memory changes yet."
        lines = []
        for item in reversed(history[-100:]):
            timestamp = str(item.get("timestamp", "")).replace("T", " ").replace("+00:00", " UTC")
            value = item.get("value", "")
            lines.append(f"{timestamp} — {item.get('action', 'changed')}: {item.get('key', '')}" + (f" — {value}" if value else ""))
        return "\n".join(lines)

    def wheelEvent(self, event):
        old_zoom = self.zoom
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom = max(0.35, min(2.5, self.zoom * factor))
        cursor = event.position()
        self.offset = cursor - (cursor - self.offset) * (self.zoom / old_zoom)
        self.update()

    def resizeEvent(self, event):
        self._layout()
        super().resizeEvent(event)

    def set_filter(self, text):
        self.filter_text = str(text or "").strip()
        self.refresh()

    def search(self, text):
        """Search memory and focus the first matching card."""
        self.set_filter(text)
        self.search_results = list(self.nodes)
        if self.search_results:
            self.selected = self.search_results[0]["id"]
            self.hovered = self.selected
        else:
            self.selected = None
            self.hovered = None
        self.update()

    def search_count(self):
        return len(self.search_results) if self.filter_text else len(self.nodes)

    def set_type_filter(self, value):
        self.filter_type = str(value or "all")
        self.refresh()
