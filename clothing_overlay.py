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
_BOW_NAME_RE = re.compile(
    r"\bбант\w*|\bбабочк\w*|"
    r"\b(?:bow|bows|bowtie|bow-tie|necktie|neck-tie)\b",
    re.IGNORECASE,
)


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


def clothing_fits(slot, value, name=""):
    """Keep common accessories in their intended vertical band."""
    bounds = clothing_bounds(value)
    if bounds is None:
        return False
    _left, top, _right, bottom = bounds
    if slot == "head":
        return bottom <= 82
    if slot == "face":
        return top >= 52 and bottom <= 162
    if slot == "neck":
        # A bow tie naturally sits a little higher than a scarf or necklace.
        minimum = 132 if _BOW_NAME_RE.search(str(name or "")) else 138
        return top >= minimum
    if slot == "body":
        return top >= 140
    return True


class AvatarLabel(QLabel):
    """The animated face label with transparent clothing painted on top."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._renderers = []
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: transparent;")

    def set_outfit(self, items):
        """Replace the items drawn over the current animation frame."""
        order = {slot: index for index, slot in enumerate(SLOT_ORDER)}
        renderers = []
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
                renderers.append((renderer, data))
        self._renderers = renderers
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._renderers:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        target = QRectF(self.rect())
        for renderer, _data in self._renderers:
            renderer.render(painter, target)
        painter.end()
