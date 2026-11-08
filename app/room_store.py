"""Persistent state for Milky's virtual room."""

import json
import hashlib
from runtime import data_path

ROOM_PATH = data_path("room.json")
DEFAULT_ROOM = {
    "theme": "cozy studio",
    "walls": "#f5dfc4",
    "floor": "#b9825b",
    "furniture": ["desk", "bookshelf", "soft sofa", "plants", "warm lamps"],
    "note": "A warm, creative room where Milky can think, draw and listen.",
}


def load_room():
    try:
        data = json.loads(ROOM_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULT_ROOM)
    result = dict(DEFAULT_ROOM)
    if isinstance(data, dict):
        result.update({key: value for key, value in data.items() if key in result})
    return result


def save_room(room):
    ROOM_PATH.write_text(json.dumps(room, ensure_ascii=False, indent=2), encoding="utf-8")


def update_room_from_memory(memory):
    """Reflect remembered interests in the room, without random changes."""
    room = load_room()
    values = " ".join(f"{key} {value}" for key, value in (memory or {}).items()).casefold()
    furniture = [str(item) for item in room.get("furniture", [])]
    rules = (
        (("music corner", ("music", "музык", "песн", "spotify")),
         ("drawing easel", ("draw", "рисован", "арт", "иллюстра")),
         ("game console", ("game", "игр", "minecraft", "steam")),
         ("bookshelf", ("book", "книг", "читать", "литератур")),
         ("plants", ("plant", "растени", "цвет"))),
    )[0]
    added = []
    for item, keywords in rules:
        if any(word in values for word in keywords) and item not in furniture:
            furniture.append(item)
            added.append(item)
    if not added:
        return room
    room["furniture"] = furniture[-12:]
    room["note"] = "Milky arranged the room around remembered interests."
    room["memory_signature"] = hashlib.sha1(values.encode("utf-8")).hexdigest()[:12]
    save_room(room)
    return room


def update_room_from_request(instruction: str):
    """Apply a short natural-language request made in Milky's chat."""
    room = load_room()
    text = instruction.strip()
    lowered = text.lower()
    additions = []
    for item, words in {
        "aquarium": ("aquarium", "аквариум"),
        "bookshelf": ("bookshelf", "книжн", "книги", "шкаф"),
        "plants": ("plant", "plants", "растени", "цвет"),
        "sofa": ("sofa", "диван", "кресло"),
        "drawing easel": ("easel", "мольберт", "рисован"),
        "music corner": ("music", "музык", "колонк"),
        "warm lamps": ("lamp", "ламп", "свет"),
    }.items():
        if any(word in lowered for word in words):
            additions.append(item)
    furniture = [str(item) for item in room.get("furniture", [])]
    for item in additions:
        if item not in furniture:
            furniture.append(item)
    removing = any(word in lowered for word in ("remove", "убери", "удали"))
    if removing:
        furniture = [item for item in furniture if not any(word in item.lower() for word in additions)]
    changed = set(furniture) != set(room.get("furniture", []))
    if not additions:
        # Keep the request visible even when it uses an object that is not in
        # the built-in vocabulary. The room is an open-ended personal space.
        item = text[:60]
        if item:
            furniture.append(item)
            changed = True
    room["furniture"] = furniture[-10:]
    room["note"] = f"Milky changed the room herself: {text}"
    save_room(room)
    if removing:
        return "Removed the requested room decoration and updated the room."
    if changed:
        added = ", ".join(additions) if additions else text[:60]
        return f"Added to Milky's room: {added}."
    return "The room already had that decoration; its note was updated."
