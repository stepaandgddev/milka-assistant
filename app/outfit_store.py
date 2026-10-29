"""Persistent storage for the clothing Milky is wearing.

The outfit lives in its own JSON file, separate from ``settings.json``.  This
keeps large SVG overlays out of the provider settings and means an outfit
survives application restarts even when the settings dialog is not touched.
"""

import json
import os
import re
import uuid

from dotenv import load_dotenv

from runtime import data_path

load_dotenv(data_path(".env"))

OUTFIT_PATH = data_path(os.environ.get("OUTFIT_FILE", "outfit.json"))

SLOTS = ("head", "face", "neck", "body", "other")
SLOT_LABELS = {
    "head": "Head",
    "face": "Face",
    "neck": "Neck",
    "body": "Body",
    "other": "Other",
}
SLOT_ORDER = ("body", "neck", "face", "head", "other")
SLOT_DEFAULT_NAMES = {
    "head": "Head accessory",
    "face": "Face accessory",
    "neck": "Neck accessory",
    "body": "Body clothing",
    "other": "Accessory",
}

MAX_ITEMS = 8
MAX_NAME_LENGTH = 60
MAX_SVG_LENGTH = 30000

_HAT_RE = re.compile(
    r"\bшапк\w*|\bшапочк\w*|\bкепк\w*|\bшляп\w*|\bберет\w*|\bушанк\w*|"
    r"\bпанам\w*|\bкапюшон\w*|\b(?:hat|hats|cap|caps|beanie|beanies|beret|"
    r"bonnet|hood|fedora)\b",
    re.IGNORECASE,
)
_CROWN_RE = re.compile(
    r"\bкорон\w*|\bдиадем\w*|\bтиар\w*|\bвенец\b|\bвенок\w*|"
    r"\b(?:crown|crowns|tiara|tiaras|diadem)\w*\b",
    re.IGNORECASE,
)
_GLASSES_RE = re.compile(
    r"\bочк\w*|\bочкар\w*|\bпенсне\b|\bмонокл\w*|\b(?:glasses|sunglasses|"
    r"shades|spectacles|monocle|eyeglasses)\b",
    re.IGNORECASE,
)
_MASK_RE = re.compile(
    r"\bмаск\w*|\b(?:mask|masks|face\s+mask|surgical\s+mask)\b",
    re.IGNORECASE,
)
_SCARF_RE = re.compile(
    r"\bшарф\w*|\bснуд\w*|\bворотник\w*|\b(?:scarf|scarves|muffler|snood|"
    r"collar|collars)\b",
    re.IGNORECASE,
)
_NECKLACE_RE = re.compile(
    r"\bожерель\w*|\bколье\b|\bбусы\b|\bцепочк\w*|\bкулон\w*|"
    r"\bмедальон\w*|\b(?:necklace|necklaces|choker|pendant|locket)\b",
    re.IGNORECASE,
)
_BOW_RE = re.compile(
    r"\bбант\w*|\bбабочк\w*|\b(?:bow|bows|bowtie|bow-tie|necktie|neck-tie)\b",
    re.IGNORECASE,
)
_EARRINGS_RE = re.compile(
    r"\bсерьг\w*|\bсерёж\w*|\b(?:earring|earrings)\b",
    re.IGNORECASE,
)
_BODY_RE = re.compile(
    r"\bплать\w*|\bюбк\w*|\bфутболк\w*|\bсвитер\w*|\bкофт\w*|\bкуртк\w*|"
    r"\bпальто\b|\bпиджак\w*|\bрубашк\w*|\bтоп\b|\bмайк\w*|\bшорт\w*|"
    r"\bбрюк\w*|\bштаны\b|\bкомбинезон\w*|\b(?:dress|dresses|shirt|shirts|"
    r"t-shirt|tshirt|sweater|hoodie|jacket|coat|skirt|pants|trousers|"
    r"shorts|robe|cloak|cape|apron)\b",
    re.IGNORECASE,
)


def infer_slot(name, requested=""):
    """Return a valid slot, using the item name when the model is vague."""
    requested = str(requested or "").strip().lower()
    if requested in SLOTS and requested != "other":
        return requested

    text = str(name or "")
    for slot, pattern in (
        ("head", _HAT_RE),
        ("head", _CROWN_RE),
        ("face", _GLASSES_RE),
        ("face", _MASK_RE),
        ("neck", _SCARF_RE),
        ("neck", _NECKLACE_RE),
        ("neck", _BOW_RE),
        ("other", _EARRINGS_RE),
        ("body", _BODY_RE),
    ):
        if pattern.search(text):
            return slot
    if requested in SLOTS:
        return requested
    return "other"


def _clean_name(value, slot):
    name = " ".join(str(value or "").split()).strip()
    if not name:
        name = SLOT_DEFAULT_NAMES.get(slot, "Clothing")
    if len(name) > MAX_NAME_LENGTH:
        name = name[: MAX_NAME_LENGTH - 3].rstrip() + "..."
    return name


def _clean_svg(value):
    svg = str(value or "").strip()
    if not svg:
        return None
    if svg.startswith("```"):
        svg = svg.strip("`").strip()
        if svg.lower().startswith("svg"):
            svg = svg[3:].strip()
    start = svg.lower().find("<svg")
    if start == -1:
        return None
    svg = svg[start:]
    end = svg.lower().rfind("</svg>")
    if end == -1:
        return None
    svg = svg[: end + len("</svg>")].strip()
    if len(svg) > MAX_SVG_LENGTH:
        return None
    return svg or None


def normalize_item(raw):
    """Validate and normalize one outfit item, or return ``None``."""
    if not isinstance(raw, dict):
        return None
    svg = _clean_svg(raw.get("svg"))
    if svg is None:
        return None

    slot = infer_slot(raw.get("name"), raw.get("slot"))
    name = _clean_name(raw.get("name"), slot)
    item_id = str(raw.get("id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", item_id):
        item_id = uuid.uuid4().hex
    return {
        "id": item_id,
        "name": name,
        "slot": slot,
        "svg": svg,
    }


def normalize_outfit(raw):
    """Normalize a stored outfit and enforce one item per slot."""
    if isinstance(raw, dict):
        raw = raw.get("items")
    if not isinstance(raw, list):
        return []

    items = []
    seen_ids = set()
    for entry in raw:
        item = normalize_item(entry)
        if item is None:
            continue
        items = [
            existing
            for existing in items
            if existing["slot"] != item["slot"]
        ]
        if item["id"] in seen_ids:
            item["id"] = uuid.uuid4().hex
        seen_ids.add(item["id"])
        items.append(item)
    return items[:MAX_ITEMS]


def load_outfit():
    """Read the saved outfit. Missing or broken files mean no clothing."""
    try:
        data = json.loads(OUTFIT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return normalize_outfit(data)


def save_outfit(items):
    """Save the outfit atomically and return its normalized form."""
    clean = normalize_outfit(items)
    OUTFIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTFIT_PATH.with_name(OUTFIT_PATH.name + ".tmp")
    temporary.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, OUTFIT_PATH)
    return clean


def wear_item(items, name, slot, svg):
    """Add or replace an item in its slot.

    Returns ``(new_items, item)``.  When the SVG is invalid, ``item`` is
    ``None`` and the existing outfit is returned unchanged.
    """
    current = normalize_outfit(items)
    item = normalize_item(
        {
            "name": name,
            "slot": slot,
            "svg": svg,
        }
    )
    if item is None:
        return current, None
    current = [
        existing for existing in current if existing["slot"] != item["slot"]
    ]
    current.append(item)
    return normalize_outfit(current), item


def remove_item(items, item_id):
    """Remove one item by its stable id."""
    return normalize_outfit(
        [
            item
            for item in normalize_outfit(items)
            if item["id"] != str(item_id or "")
        ]
    )
