"""Discover, load and run Milky addons.

Addons are folders in ``addons/``. Each folder has an ``addon.json`` manifest
and an entry module (``addon.py`` by default). Addon tools are exposed to the
chat model as ``addon__<addon>__<tool>`` functions.

Addons can declare visual settings in their manifest. Milky merges saved
values with defaults and passes them to the addon as ``ctx.settings``.

Addons are ordinary Python code and run with the same permissions as Milky.
Only install addons you trust.
"""

from __future__ import annotations

import copy
import importlib.util
import inspect
import json
import math
import os
import re
import sys
import threading
import traceback
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from addon_api import AddonContext
from runtime import data_path, resource_path

ADDONS_DIR = data_path("addons")
BUNDLED_ADDONS_DIR = resource_path("addons")
MANIFEST_NAME = "addon.json"
MAX_RESULT_CHARS = 7000
API_VERSION = 1
MAX_SETTINGS_FIELDS = 48

SETTINGS_FIELD_TYPES = {
    "str": "string",
    "string": "string",
    "text": "string",
    "password": "string",
    "secret": "string",
    "int": "int",
    "integer": "int",
    "bool": "bool",
    "boolean": "bool",
    "checkbox": "bool",
    "switch": "bool",
    "float": "number",
    "number": "number",
    "double": "number",
    "select": "select",
    "choice": "select",
    "enum": "select",
    "path": "path",
    "file": "path",
    "folder": "path",
    "directory": "path",
}

_lock = threading.RLock()
_records = []
_records_by_id = {}
_tool_map = {}
_module_counter = 0
_animation_callback = None


@dataclass
class AddonRecord:
    addon_id: str
    name: str
    version: str
    description: str
    path: Path
    enabled: bool
    entry_path: Path | None = None
    icon_path: Path | None = None
    error: str = ""
    tools: list = field(default_factory=list)
    settings_schema: list = field(default_factory=list)
    settings: dict = field(default_factory=dict)
    module: object = None
    context: object = None
    module_name: str = ""


def _slug(value, fallback="tool"):
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "")).strip("_")
    return (text or fallback)[:64]


def _short_hash(value):
    return format(zlib.crc32(str(value).encode("utf-8")) & 0xFFFFFFFF, "08x")[:6]


def _asset_count(folder):
    assets = folder / "assets"
    try:
        if not assets.is_dir():
            return 0
        return sum(1 for path in assets.rglob("*") if path.is_file())
    except OSError:
        return 0


def _log(message):
    try:
        print(message, flush=True)
    except Exception:
        pass


def _error_text(error):
    detail = " ".join(str(error).split()) or error.__class__.__name__
    return detail[:300]


def _manifest_error(folder, message):
    addon_id = _slug(folder.name, "addon")
    return {
        "id": addon_id,
        "name": folder.name,
        "version": "",
        "description": "",
        "entry_path": None,
        "icon_path": None,
        "error": message,
        "settings": [],
    }


def _read_manifest(folder):
    path = folder / MANIFEST_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return _manifest_error(folder, "Missing addon.json")
    except (OSError, json.JSONDecodeError) as error:
        return _manifest_error(folder, f"Cannot read addon.json: {error}")
    if not isinstance(data, dict):
        return _manifest_error(folder, "addon.json must contain an object")

    addon_id = _slug(data.get("id") or folder.name, "addon")
    name = " ".join(str(data.get("name") or addon_id).split()) or addon_id
    version = str(data.get("version") or "").strip()[:30]
    description = " ".join(str(data.get("description") or "").split())[:300]
    entry = str(data.get("entry") or "addon.py").strip() or "addon.py"
    try:
        api = int(data.get("api", 1))
    except (TypeError, ValueError):
        api = 1

    error = ""
    if api > API_VERSION:
        error = f"Addon requires API {api}; Milky supports {API_VERSION}."
    entry_path = (folder / entry).resolve()
    try:
        entry_path.relative_to(folder.resolve())
    except ValueError:
        error = "The addon entry must stay inside its folder."
        entry_path = folder / "addon.py"
    if not error and not entry_path.is_file():
        error = f"Entry file not found: {entry}"

    icon_path = None
    icon = str(data.get("icon") or "").strip()
    if icon:
        candidate = (folder / icon).resolve()
        try:
            candidate.relative_to(folder.resolve())
        except ValueError:
            candidate = None
        if candidate is not None and candidate.is_file():
            icon_path = candidate

    return {
        "id": addon_id,
        "name": name,
        "version": version,
        "description": description,
        "entry_path": entry_path,
        "icon_path": icon_path,
        "error": error,
        "settings": _normalize_settings_schema(data.get("settings")),
    }


def _addon_roots():
    roots = []
    seen = set()
    for root in (ADDONS_DIR, BUNDLED_ADDONS_DIR):
        try:
            resolved = root.resolve()
        except OSError:
            resolved = root
        if resolved in seen or not root.is_dir():
            continue
        seen.add(resolved)
        roots.append(root)
    return roots


def _iter_addon_folders():
    folders = []
    seen = set()
    for root in _addon_roots():
        for path in sorted(root.iterdir()):
            if (
                not path.is_dir()
                or path.name.startswith((".", "_"))
                or path.name == "__pycache__"
            ):
                continue
            try:
                key = path.resolve()
            except OSError:
                key = path
            if key in seen:
                continue
            seen.add(key)
            folders.append(path)
    return folders


def _schema(value):
    if not isinstance(value, dict):
        return {"type": "object", "properties": {}}
    schema = dict(value)
    if schema.get("type") != "object":
        return {"type": "object", "properties": {}}
    if not isinstance(schema.get("properties"), dict):
        schema["properties"] = {}
    if not isinstance(schema.get("required"), list):
        schema.pop("required", None)
    return schema


def _setting_label(key):
    return " ".join(str(key).replace("_", " ").split()).title()


def _setting_number(value, integer=False):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if integer:
        return int(round(number))
    return number


def _setting_options(raw):
    if isinstance(raw, dict):
        raw = [
            {"value": key, "label": value}
            for key, value in raw.items()
        ]
    if not isinstance(raw, (list, tuple)):
        return []
    options = []
    seen = set()
    for item in raw[:100]:
        if isinstance(item, dict):
            value = item.get("value", item.get("id", ""))
            label = item.get("label", item.get("name", value))
        else:
            value = label = item
        value = str(value)
        label = " ".join(str(label or value).split())
        if not value or value in seen:
            continue
        seen.add(value)
        options.append({"value": value, "label": label or value})
    return options


def _setting_default_type(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "number"
    return "string"


def _setting_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value or "").strip().lower()
    if text in ("1", "true", "yes", "on", "enabled"):
        return True
    if text in ("", "0", "false", "no", "off", "disabled"):
        return False
    return bool(text)


def _normalize_setting_field(key, raw):
    key = str(key or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", key):
        return None
    spec = dict(raw) if isinstance(raw, dict) else {"default": raw}
    raw_type = str(spec.get("type") or "").strip().lower()
    if not raw_type:
        raw_type = _setting_default_type(spec.get("default"))
    field_type = SETTINGS_FIELD_TYPES.get(raw_type, "string")

    label = " ".join(
        str(spec.get("label") or _setting_label(key)).split()
    )[:80]
    description = " ".join(str(spec.get("description") or "").split())[:500]
    placeholder = str(spec.get("placeholder") or "")[:300]
    options = _setting_options(spec.get("options")) if field_type == "select" else []

    minimum = _setting_number(
        spec.get("min"), integer=field_type == "int"
    )
    maximum = _setting_number(
        spec.get("max"), integer=field_type == "int"
    )
    if minimum is not None and maximum is not None and minimum > maximum:
        minimum, maximum = maximum, minimum
    if field_type == "int":
        if minimum is not None:
            minimum = max(-2147483648, min(2147483647, minimum))
        if maximum is not None:
            maximum = max(-2147483648, min(2147483647, maximum))
        step = _setting_number(spec.get("step"), integer=True) or 1
        step = max(1, min(2147483647, step))
        decimals = 0
    elif field_type == "number":
        if minimum is not None:
            minimum = max(-1.0e9, min(1.0e9, minimum))
        if maximum is not None:
            maximum = max(-1.0e9, min(1.0e9, maximum))
        step = _setting_number(spec.get("step")) or 0.1
        step = max(0.0001, min(1.0e9, step))
        decimals = _setting_number(spec.get("decimals"), integer=True)
        if decimals is None:
            decimals = 2
        decimals = max(0, min(6, decimals))
    else:
        step = 1
        decimals = 0

    pick = str(spec.get("pick") or "").strip().lower()
    if field_type == "path" and raw_type == "file":
        pick = "file"
    if pick not in ("file", "directory"):
        pick = "directory"

    field = {
        "key": key,
        "label": label or _setting_label(key),
        "type": field_type,
        "description": description,
        "placeholder": placeholder,
        "min": minimum,
        "max": maximum,
        "step": step,
        "decimals": decimals,
        "suffix": str(spec.get("suffix") or "")[:20],
        "options": options,
        "pick": pick,
        "secret": bool(
            spec.get("secret")
            or raw_type in ("password", "secret")
        ),
        "multiline": bool(
            spec.get("multiline")
            or raw_type == "text"
        ),
    }
    if "default" in spec:
        default = spec.get("default")
    elif field_type == "bool":
        default = False
    elif field_type in ("int", "number"):
        default = 0
    elif field_type == "select":
        default = options[0]["value"] if options else ""
    else:
        default = ""
    field["default"] = _coerce_setting_value(field, default)
    return field


def _normalize_settings_schema(raw):
    """Return a safe, declarative settings schema for the settings window."""
    if isinstance(raw, dict):
        entries = []
        for key, spec in raw.items():
            if isinstance(spec, dict):
                entry = dict(spec)
                entry.setdefault("key", key)
            else:
                entry = {"key": key, "default": spec}
            entries.append(entry)
    elif isinstance(raw, (list, tuple)):
        entries = list(raw)
    else:
        return []

    schema = []
    seen = set()
    for entry in entries:
        if len(schema) >= MAX_SETTINGS_FIELDS:
            break
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        field = _normalize_setting_field(key, entry)
        if field is None or field["key"] in seen:
            continue
        seen.add(field["key"])
        schema.append(field)
    return schema


def _coerce_setting_value(field, value):
    field_type = field.get("type", "string")
    minimum = field.get("min")
    maximum = field.get("max")
    if field_type == "bool":
        return _setting_bool(value)
    if field_type == "int":
        try:
            number = int(float(value))
            if not math.isfinite(float(value)):
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            try:
                number = int(field.get("default") or 0)
            except (TypeError, ValueError, OverflowError):
                number = 0
        if minimum is not None:
            number = max(int(minimum), number)
        if maximum is not None:
            number = min(int(maximum), number)
        return number
    if field_type == "number":
        try:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            try:
                number = float(field.get("default") or 0.0)
            except (TypeError, ValueError, OverflowError):
                number = 0.0
            if not math.isfinite(number):
                number = 0.0
        if minimum is not None:
            number = max(float(minimum), number)
        if maximum is not None:
            number = min(float(maximum), number)
        return round(number, 6)
    if field_type == "select":
        text = str(value if value is not None else "").strip()
        options = field.get("options") or []
        if any(option["value"] == text for option in options):
            return text
        if options:
            return options[0]["value"]
        return ""
    text = str(value if value is not None else "").strip()
    if field_type == "path":
        return text
    return text


def coerce_addon_setting(field, value):
    """Return a safe value for one normalized addon settings field."""
    return _coerce_setting_value(field, value)


def _merge_addon_settings(schema, raw):
    """Merge saved values with manifest defaults, keeping legacy keys."""
    values = {}
    saved = raw if isinstance(raw, dict) else {}
    for field in schema:
        key = field["key"]
        if key in saved:
            values[key] = _coerce_setting_value(field, saved[key])
        else:
            values[key] = copy.deepcopy(field.get("default"))
    for key, value in saved.items():
        if key not in values:
            values[str(key)] = value
    return values


def _module_tools(module):
    tools = []
    seen = set()

    def add(name, description, parameters, handler):
        name = str(name or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
            return
        if name in seen or not callable(handler):
            return
        seen.add(name)
        tools.append(
            {
                "name": name,
                "description": " ".join(str(description or "").split()),
                "parameters": _schema(parameters),
                "handler": handler,
            }
        )

    for value in vars(module).values():
        metadata = getattr(value, "__milky_tool__", None)
        if isinstance(metadata, dict) and callable(value):
            add(
                metadata.get("name") or getattr(value, "__name__", "tool"),
                metadata.get("description", ""),
                metadata.get("parameters"),
                value,
            )

    declared = getattr(module, "TOOLS", None)
    if isinstance(declared, dict):
        for name, spec in declared.items():
            if callable(spec):
                add(name, getattr(spec, "__doc__", ""), None, spec)
            elif isinstance(spec, dict):
                add(
                    spec.get("name") or name,
                    spec.get("description", ""),
                    spec.get("parameters"),
                    spec.get("handler") or spec.get("callable"),
                )
    return tools


def _public_name(addon_id, tool_name, used):
    base = (
        f"addon__{_slug(addon_id, 'addon')[:20]}__{_slug(tool_name)}"
    )[:64]
    if base not in used:
        return base
    suffix = "_" + _short_hash(f"{addon_id}:{tool_name}")
    return base[: 64 - len(suffix)] + suffix


def _load_addon(record, addon_settings):
    global _module_counter
    if record.entry_path is None:
        return
    _module_counter += 1
    module_name = (
        f"milky_addon_{_slug(record.addon_id, 'addon')}_{_module_counter}"
    )
    record.module_name = module_name
    addon_dir = record.path
    added_path = False
    try:
        if str(addon_dir) not in sys.path:
            sys.path.insert(0, str(addon_dir))
            added_path = True
        spec = importlib.util.spec_from_file_location(
            module_name, record.entry_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not create a module spec")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        record.module = module
        data_dir = ADDONS_DIR / ".data" / _slug(record.addon_id, "addon")
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            data_dir = record.path
        settings = (
            copy.deepcopy(addon_settings)
            if isinstance(addon_settings, dict)
            else {}
        )
        record.settings = settings
        record.context = AddonContext(
            addon_id=record.addon_id,
            addon_dir=record.path,
            data_dir=data_dir,
            settings=settings,
            _animation_callback=_animation_callback,
        )
        setup = getattr(module, "setup", None)
        if callable(setup):
            try:
                setup(record.context)
            except Exception as error:
                record.error = f"setup failed: {_error_text(error)}"
                _log(traceback.format_exc().rstrip())
        record.tools = _module_tools(module)
    except Exception as error:
        record.error = _error_text(error)
        record.tools = []
        record.module = None
        sys.modules.pop(module_name, None)
        _log(traceback.format_exc().rstrip())
    finally:
        if added_path:
            try:
                sys.path.remove(str(addon_dir))
            except ValueError:
                pass


def _unload_all():
    for record in _records:
        module = record.module
        context = record.context
        if module is not None:
            shutdown = getattr(module, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown(context)
                except Exception:
                    _log(traceback.format_exc().rstrip())
        if context is not None:
            context._animation_enabled = False
        if module is not None and record.module_name:
            sys.modules.pop(record.module_name, None)


def set_animation_callback(callback):
    """Set the UI callback used by ``AddonContext.play_animation()``.

    The callback receives ``(addon_id, source, duration_ms)``. It is called
    from addon worker threads, so the UI must dispatch it to the main thread.
    """
    global _animation_callback
    _animation_callback = callback if callable(callback) else None


def configure_addons(settings=None):
    """Reload addons from disk using the ``addons`` settings section."""
    global _records, _records_by_id, _tool_map
    with _lock:
        _unload_all()
        _records = []
        _records_by_id = {}
        _tool_map = {}

        try:
            ADDONS_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        addons = settings if isinstance(settings, dict) else {}
        disabled = {
            str(item).strip()
            for item in addons.get("disabled") or []
            if str(item).strip()
        }
        per_addon = addons.get("settings")
        if not isinstance(per_addon, dict):
            per_addon = {}

        for folder in _iter_addon_folders():
            manifest = _read_manifest(folder)
            addon_id = manifest["id"]
            if addon_id in _records_by_id:
                _log(
                    f"[addons] duplicate addon id {addon_id!r}: skipping "
                    f"{folder}"
                )
                continue
            record = AddonRecord(
                addon_id=addon_id,
                name=manifest["name"],
                version=manifest["version"],
                description=manifest["description"],
                path=folder,
                enabled=addon_id not in disabled,
                entry_path=manifest.get("entry_path"),
                icon_path=manifest.get("icon_path"),
                error=manifest.get("error", ""),
                settings_schema=manifest.get("settings") or [],
            )
            record.settings = _merge_addon_settings(
                record.settings_schema, per_addon.get(addon_id)
            )
            _records_by_id[addon_id] = record
            _records.append(record)
            if not record.enabled or record.error or record.entry_path is None:
                continue

            _load_addon(record, record.settings)

            used = set(_tool_map)
            for addon_tool in record.tools:
                public = _public_name(
                    record.addon_id, addon_tool["name"], used
                )
                used.add(public)
                _tool_map[public] = (record, addon_tool, public)

        return addon_records()


def addon_tool_definitions():
    """Return OpenAI-style function definitions for enabled addon tools."""
    with _lock:
        definitions = []
        for public, (record, addon_tool, _public) in _tool_map.items():
            description = addon_tool["description"] or (
                f"{record.name} addon tool"
            )
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": public,
                        "description": (
                            f"[{record.name}] {description}"
                        )[:1024],
                        "parameters": addon_tool["parameters"],
                    },
                }
            )
        return definitions


def is_addon_tool(name):
    with _lock:
        return str(name or "") in _tool_map


def _format_value(value):
    if value is None:
        return "Done."
    if isinstance(value, str):
        text = value
    elif isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            text = str(value)
    else:
        text = str(value)
    text = text.strip()
    return (text or "Done.")[:MAX_RESULT_CHARS]


def call_addon_tool(name, arguments=None):
    """Run an addon tool and return text for the chat model."""
    with _lock:
        entry = _tool_map.get(str(name or ""))
    if entry is None:
        return (
            f'Addon tool "{name}" is not available. '
            "Tell the user the addon is disabled or failed to load."
        )

    record, addon_tool, _public = entry
    handler = addon_tool["handler"]
    values = arguments if isinstance(arguments, dict) else {}
    try:
        signature = inspect.signature(handler)
        kwargs = dict(values)
        if "ctx" in signature.parameters:
            kwargs["ctx"] = record.context
        try:
            bound = signature.bind(**kwargs)
        except TypeError as error:
            return (
                f'Addon tool "{name}" got invalid arguments: {error}. '
                "Check the arguments and try again; do not invent a result."
            )
        if inspect.iscoroutinefunction(handler):
            import asyncio

            result = asyncio.run(handler(*bound.args, **bound.kwargs))
        else:
            result = handler(*bound.args, **bound.kwargs)
    except Exception as error:
        detail = _error_text(error).rstrip(".")
        if os.environ.get("MILKY_ADDON_DEBUG"):
            _log(traceback.format_exc().rstrip())
        else:
            _log(f"[addon:{record.addon_id}] {name}: {detail}")
        return (
            f'Addon tool "{name}" failed: {detail}. '
            "Tell the user the addon failed; do not invent a result."
        )
    return _format_value(result)


def addon_records():
    """Return metadata for the settings window."""
    with _lock:
        return [
            {
                "id": record.addon_id,
                "name": record.name,
                "version": record.version,
                "description": record.description,
                "path": str(record.path),
                "enabled": record.enabled,
                "error": record.error,
                "icon": str(record.icon_path) if record.icon_path else "",
                "assets": _asset_count(record.path),
                "tools": [tool["name"] for tool in record.tools],
                "settings_schema": copy.deepcopy(record.settings_schema),
                "settings": copy.deepcopy(record.settings),
            }
            for record in _records
        ]


def addons_directory():
    ADDONS_DIR.mkdir(parents=True, exist_ok=True)
    return ADDONS_DIR


def shutdown_addons():
    global _records, _records_by_id, _tool_map
    with _lock:
        _unload_all()
        _records = []
        _records_by_id = {}
        _tool_map = {}
