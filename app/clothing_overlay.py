"""Rendering and validation for generated clothing overlays."""

import re

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel

from outfit_store import SLOT_ORDER

# Prefix of the official self-portrait eye path.  It must never appear in a
# clothing overlay: that would cover Milky's animated face with a second face.
OFFICIAL_FACE_SIGNATURE = "M284 273C284 218 251 189"

_MAX_SAMPLES = 10000
_MAX_COVERAGE = 6200

_RECT_TAG_RE = re.compile(r"<rect\b[^>]*?/?>", re.IGNORECASE | re.DOTALL)
_UNSAFE_RE = re.compile(
    r"<(?:script|foreignObject|image)\b|\bon\w+\s*=",
    re.IGNORECASE,
)
_SIZE_ATTRIBUTE_RE = re.compile(
    r'(?<![\w-])(?:width|height)\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
# Milky's eyes occupy x 40..160, y 59..116.  A face accessory may frame them
# or tint them with transparent lenses, but it must not turn them into an
# opaque wall.
EYE_ZONE = (40, 59, 161, 117)
FACE_EYE_MAX_OPAQUE = 0.72


def _full_canvas_size(value):
    value = str(value or "").strip().lower()
    if value in {"200", "200px", "100%"}:
        return True
    try:
        return float(value.removesuffix("px")) == 200.0
    except ValueError:
        return False


def clean_svg_markup(value):
    """Return a bare ``<svg>...</svg>`` block, or ``None``."""
    if value is None:
        return None
    code = str(value).strip()
    if not code:
        return None
    if code.startswith("```"):
        code = code.strip("`").strip()
        if code.lower().startswith("svg"):
            code = code[3:].strip()
    start = code.lower().find("<svg")
    if start == -1:
        return None
    code = code[start:]
    end = code.lower().rfind("</svg>")
    if end == -1:
        return None
    return code[: end + len("</svg>")].strip() or None


def strip_canvas_rects(code):
    """Remove full-canvas rectangles that models use as a background."""

    def replace(match):
        tag = match.group(0)
        sizes = _SIZE_ATTRIBUTE_RE.findall(tag)
        if len(sizes) >= 2 and all(_full_canvas_size(size) for size in sizes[:2]):
            return ""
        return tag

    return _RECT_TAG_RE.sub(replace, code)


def _render_overlay(code):
    renderer = QSvgRenderer(QByteArray(code.encode("utf-8")))
    if not renderer.isValid():
        return None
    image = QImage(200, 200, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, 200, 200))
    painter.end()
    return image


def validate_clothing_svg(value):
    """Return a safe, transparent clothing SVG or ``None``.

    The checks catch the common failure modes: invalid XML, a copied
    self-portrait, unsafe embedded content, an empty overlay, and a full-canvas
    opaque background that would hide Milky's face.
    """
    code = clean_svg_markup(value)
    if code is None:
        return None
    if OFFICIAL_FACE_SIGNATURE in code or _UNSAFE_RE.search(code):
        return None
    code = strip_canvas_rects(code)

    image = _render_overlay(code)
    if image is None:
        return None

    visible = 0
    for y in range(0, 200, 2):
        for x in range(0, 200, 2):
            alpha = (image.pixel(x, y) >> 24) & 0xFF
            if alpha > 12:
                visible += 1
                if visible > _MAX_COVERAGE:
                    return None
    if visible < _MAX_SAMPLES * 0.0015:
        return None

    corners = ((2, 2), (197, 2), (2, 197), (197, 197))
    if all(((image.pixel(x, y) >> 24) & 0xFF) > 160 for x, y in corners):
        return None
    return code


def clothing_bounds(value):
    """Return the visible ``(left, top, right, bottom)`` bounds, or ``None``."""
    code = clean_svg_markup(value)
    if code is None:
        return None
    image = _render_overlay(strip_canvas_rects(code))
    if image is None:
        return None

    left, top, right, bottom = 200, 200, -1, -1
    for y in range(200):
        for x in range(200):
            if ((image.pixel(x, y) >> 24) & 0xFF) <= 12:
                continue
            left = min(left, x)
            top = min(top, y)
            right = max(right, x)
            bottom = max(bottom, y)
    if right < left:
        return None
    return left, top, right, bottom


def _opaque_ratio(image, box, threshold=160):
    """Return the fraction of opaque pixels in a rectangle."""
    left, top, right, bottom = box
    total = 0
    opaque = 0
    for y in range(top, bottom):
        for x in range(left, right):
            total += 1
            if ((image.pixel(x, y) >> 24) & 0xFF) >= threshold:
                opaque += 1
    return opaque / total if total else 0.0


def clothing_fits(slot, value, name=""):
    """Keep accessories in their intended band and the eyes unobstructed."""
    bounds = clothing_bounds(value)
    if bounds is None:
        return False
    _left, top, _right, bottom = bounds
    if slot == "head":
        # A hat may sit on the forehead, not over the eyes.
        return bottom <= 76
    if slot == "face":
        if top < 52 or bottom > 162:
            return False
        code = clean_svg_markup(value)
        image = _render_overlay(strip_canvas_rects(code)) if code else None
        if image is None:
            return False
        return _opaque_ratio(image, EYE_ZONE) <= FACE_EYE_MAX_OPAQUE
    if slot == "neck":
        # Keep scarves, bow ties and necklaces below the smile.
        return top >= 145
    if slot == "body":
        # Body clothing starts below the floating face.
        return top >= 145
    return True


class AvatarLabel(QLabel):
    """The animated face label with face-safe clothing layers.

    Body, neck, head and other items are painted *behind* the animated face
    line art.  That keeps the eyes and smile visible even when a scarf, hat or
    collar is large.  Only face-slot items (glasses and masks) are painted in
    front, because they are meant to sit over the face; those are separately
    checked for eye clearance before they are worn.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._back_renderers = []
        self._front_renderers = []
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: transparent;")

    def set_outfit(self, items):
        """Replace the layers drawn around the current animation frame."""
        order = {slot: index for index, slot in enumerate(SLOT_ORDER)}
        back = []
        front = []
        valid_items = (
            entry for entry in (items or []) if isinstance(entry, dict)
        )
        for item in sorted(
            valid_items,
            key=lambda entry: order.get(entry.get("slot"), len(order)),
        ):
            svg = str(item.get("svg") or "")
            if not svg:
                continue
            data = QByteArray(svg.encode("utf-8"))
            renderer = QSvgRenderer(data)
            if renderer.isValid():
                # Keep the bytes alive together with the renderer.
                target = front if item.get("slot") == "face" else back
                target.append((renderer, data))
        self._back_renderers = back
        self._front_renderers = front
        self.update()

    def paintEvent(self, event):
        """Compose clothing, the current face frame, then face accessories."""
        movie = self.movie()
        if movie is None:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Clear the previous frame; otherwise transparent pixels can ghost.
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Source
        )
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver
        )

        target = QRectF(self.rect())
        for renderer, _data in self._back_renderers:
            renderer.render(painter, target)

        frame = movie.currentPixmap()
        if not frame.isNull():
            painter.drawPixmap(target.topLeft(), frame)

        for renderer, _data in self._front_renderers:
            renderer.render(painter, target)
        painter.end()
