"""Read the public Firebase catalog used by the extension store."""

from __future__ import annotations

import requests

SHOP_DATABASE_URL = "https://milkaai-default-rtdb.firebaseio.com"


def fetch_catalog(timeout=15):
    """Return the public /shop tree, or a useful error for the UI."""
    response = requests.get(f"{SHOP_DATABASE_URL}/shop.json", timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


def extensions_from_catalog(data):
    raw = data.get("extensions", {}) if isinstance(data, dict) else {}
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, dict):
        values = []
        for key, value in raw.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("id", key)
                values.append(item)
    else:
        values = []
    return [item for item in values if isinstance(item, dict)]


__all__ = ["SHOP_DATABASE_URL", "fetch_catalog", "extensions_from_catalog"]
