"""Public API for Milky addons.

An addon is a folder inside the ``addons`` directory with an ``addon.json``
manifest and an entry Python module (``addon.py`` by default). Expose
functions to Milky with the ``tool`` decorator:

    from addon_api import tool

    @tool("current_track", "Return the track Spotify is playing now.")
    def current_track():
        return "Artist - Title"

Tool arguments are keyword arguments described by a JSON Schema.

Addons can ship read-only files in an ``assets/`` folder. Tool functions that
receive ``ctx`` can read them with ``ctx.asset_path()``, ``ctx.read_asset()``
and ``ctx.list_assets()``. They can also ask Milky's avatar to play a GIF with
``ctx.play_animation()`` and ``ctx.stop_animation()``.

An addon can declare visual settings in ``addon.json`` as a ``settings`` array.
Milky renders the fields in **Settings → Skills** and passes the current values
to the addon as ``ctx.settings``. Supported types include string, multiline
text, path, integer, number, boolean and select.
"""

from __future__ import annotations

import inspect
import types
import typing
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AddonContext:
    """Runtime information passed to an addon tool as ``ctx``."""

    addon_id: str
    addon_dir: Path
    data_dir: Path
    settings: dict = field(default_factory=dict)
    _animation_callback: object = field(default=None, repr=False)
    _animation_enabled: bool = field(default=True, repr=False)

    @property
    def assets_dir(self):
        """Read-only folder for files shipped with the addon."""
        return self.addon_dir / "assets"

    def log(self, message):
        try:
            print(f"[addon:{self.addon_id}] {message}", flush=True)
        except Exception:
            pass

    def path(self, *parts):
        return self.addon_dir.joinpath(*parts)

    def asset_path(self, *parts):
        """Return a path inside ``assets/`` and reject path traversal."""
        root = self.assets_dir.resolve()
        path = self.assets_dir.joinpath(*parts).resolve()
        try:
            path.relative_to(root)
        except ValueError as error:
            raise ValueError(
                "Asset paths must stay inside the addon assets folder."
            ) from error
        return path

    def read_asset(self, *parts, binary=False):
        """Read a bundled asset as UTF-8 text or as bytes."""
        path = self.asset_path(*parts)
        if binary:
            return path.read_bytes()
        return path.read_text(encoding="utf-8")

    def list_assets(self):
        """Return relative paths of all files in the assets folder."""
        root = self.assets_dir
        if not root.is_dir():
            return []
        return [
            path.relative_to(root).as_posix()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        ]

    def play_animation(self, source, duration_ms=0):
        """Ask Milky to show a GIF until ``stop_animation`` or a timeout.

        A bare filename such as ``milka_idle.gif`` is looked up in Milky's
        ``assets/gifs/`` folder. A path such as ``assets/music.gif`` is resolved
        inside this addon. Animation is paused while chat replies, input and
        drawing animations are active, then returns automatically.
        """
        callback = self._animation_callback
        if not callable(callback) or not self._animation_enabled:
            return
        source = str(source or "").strip()
        if not source:
            return
        try:
            path = Path(source)
            if path.parts and path.parts[0] == "assets":
                path = self.asset_path(*path.parts[1:])
            elif not path.is_absolute() and (
                len(path.parts) > 1 or source.startswith(".")
            ):
                path = self.path(source)
        except Exception as error:
            self.log(f"animation path rejected: {error}")
            return
        try:
            duration = int(duration_ms)
        except (TypeError, ValueError):
            duration = 0
        try:
            callback(
                self.addon_id,
                str(path),
                max(0, min(duration, 3600000)),
            )
        except Exception as error:
            self.log(f"animation request failed: {error}")

    def stop_animation(self):
        """Remove the animation requested by this addon."""
        callback = self._animation_callback
        if not callable(callback) or not self._animation_enabled:
            return
        try:
            callback(self.addon_id, "", 0)
        except Exception as error:
            self.log(f"animation stop failed: {error}")


def tool(name=None, description=None, parameters=None):
    """Expose a function as a Milky tool.

    Can be used as ``@tool`` or ``@tool(...)``. When ``parameters`` is
    omitted, a JSON Schema is generated from the function signature. The
    generated schema always describes an object; the default is a tool
    without arguments. A parameter named ``ctx`` receives the addon context
    and is not exposed to the model.
    """

    def decorate(function):
        if not callable(function):
            raise TypeError("tool() expects a callable")

        tool_name = str(name or getattr(function, "__name__", "")).strip()
        if not tool_name:
            raise ValueError("Addon tool name cannot be empty")

        schema = parameters
        if not isinstance(schema, dict):
            schema = _schema_for_function(function)
        else:
            schema = dict(schema)
        if schema.get("type") != "object":
            schema = {"type": "object", "properties": {}}
        if not isinstance(schema.get("properties"), dict):
            schema["properties"] = {}
        required = schema.get("required")
        if not isinstance(required, list):
            schema.pop("required", None)

        description_text = " ".join(
            str(
                description
                if description is not None
                else (function.__doc__ or "")
            ).split()
        )
        function.__milky_tool__ = {
            "name": tool_name,
            "description": description_text,
            "parameters": schema,
        }
        return function

    if callable(name):
        function = name
        name = None
        return decorate(function)
    return decorate


def _schema_for_function(function):
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return {"type": "object", "properties": {}}
    try:
        hints = typing.get_type_hints(function, include_extras=True)
    except Exception:
        hints = {}

    properties = {}
    required = []
    for parameter_name, parameter in signature.parameters.items():
        if parameter_name == "ctx":
            continue
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        annotation = hints.get(parameter_name, parameter.annotation)
        schema = {}
        json_type = _json_type(annotation)
        if json_type:
            schema["type"] = json_type
        if parameter.default is inspect.Parameter.empty:
            required.append(parameter_name)
        elif parameter.default is not None and _json_value(parameter.default):
            schema["default"] = parameter.default
        properties[parameter_name] = schema

    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _json_type(annotation):
    if annotation is inspect.Parameter.empty:
        return None
    if isinstance(annotation, str):
        text = annotation.strip().strip("'\"")
        text = text.replace("typing.", "")
        if text in ("str", "str | None", "Optional[str]"):
            return "string"
        if text in ("int", "int | None", "Optional[int]"):
            return "integer"
        if text in ("float", "float | None", "Optional[float]"):
            return "number"
        if text in ("bool", "bool | None", "Optional[bool]"):
            return "boolean"
        if text.startswith(("list", "List", "tuple", "Tuple", "set", "Set")):
            return "array"
        if text.startswith(("dict", "Dict")):
            return "object"
        return None
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        members = [
            item
            for item in typing.get_args(annotation)
            if item is not type(None)
        ]
        if len(members) == 1:
            return _json_type(members[0])
        return None
    if origin in (list, tuple, set):
        return "array"
    if origin is dict:
        return "object"
    if annotation is bool:
        return "boolean"
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is str:
        return "string"
    if isinstance(annotation, type):
        if issubclass(annotation, bool):
            return "boolean"
        if issubclass(annotation, int):
            return "integer"
        if issubclass(annotation, float):
            return "number"
        if issubclass(annotation, (list, tuple, set)):
            return "array"
        if issubclass(annotation, dict):
            return "object"
    return None


def _json_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, (list, tuple)):
        return all(_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _json_value(item)
            for key, item in value.items()
        )
    return False


__all__ = ["AddonContext", "tool"]
