import json
import os

from dotenv import load_dotenv

from runtime import data_path

load_dotenv(data_path(".env"))

SETTINGS_PATH = data_path(os.environ.get("SETTINGS_FILE", "settings.json"))

PROVIDER_TYPES = [
    ("ollama", "Ollama"),
    ("openai", "OpenAI-compatible"),
]

TYPE_LABELS = dict(PROVIDER_TYPES)

TTS_PROVIDERS = [
    ("milka", "Milka TTS"),
    ("groq", "Groq"),
]

TTS_PROVIDER_VALUES = {value for value, _ in TTS_PROVIDERS}

DEFAULT_MILKA_TTS_URL = os.environ.get(
    "MILKA_TTS_URL", "http://192.168.1.100:8765"
).strip()
DEFAULT_MILKA_TTS_VOICE = os.environ.get(
    "MILKA_TTS_VOICE", "sveta"
).strip()
DEFAULT_MILKA_TTS_SPEED = os.environ.get("MILKA_TTS_SPEED", "1.0")
DEFAULT_GROQ_TTS_MODEL = os.environ.get(
    "GROQ_TTS_MODEL", "canopylabs/orpheus-v1-english"
).strip()
DEFAULT_GROQ_TTS_VOICE = os.environ.get(
    "GROQ_TTS_VOICE", "hannah"
).strip()


def _env_bool(variable, default):
    value = os.environ.get(variable)
    if value is None:
        return default
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def _float_value(value, default, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


SCREEN_READING_LANGUAGES = [
    ("eng", "English"),
    ("rus", "Russian"),
]


def default_tts():
    provider = os.environ.get("TTS_PROVIDER", "milka").strip().lower()
    if provider not in TTS_PROVIDER_VALUES:
        provider = "milka"
    return {
        "enabled": _env_bool("TTS_ENABLED", True),
        "provider": provider,
        "milka_url": DEFAULT_MILKA_TTS_URL,
        "milka_voice": DEFAULT_MILKA_TTS_VOICE or "sveta",
        "milka_speed": _float_value(
            DEFAULT_MILKA_TTS_SPEED, 1.0, 0.5, 2.0
        ),
        "groq_api_key": os.environ.get("GROQ_API_KEY", "").strip(),
        "groq_model": DEFAULT_GROQ_TTS_MODEL or "canopylabs/orpheus-v1-english",
        "groq_voice": DEFAULT_GROQ_TTS_VOICE or "hannah",
    }


def default_screen_reading():
    return {
        "enabled": _env_bool("SCREEN_READING_ENABLED", False),
        "language": os.environ.get("SCREEN_READING_LANGUAGE", "eng").strip(),
        "interval": _float_value(
            os.environ.get("SCREEN_READING_INTERVAL", "10"), 10.0, 1.0, 60.0
        ),
    }


def normalize_tts(raw):
    defaults = default_tts()
    if not isinstance(raw, dict):
        return defaults

    provider = str(raw.get("provider", defaults["provider"])).strip().lower()
    if provider not in TTS_PROVIDER_VALUES:
        provider = defaults["provider"]

    milka_url = str(
        raw.get("milka_url", defaults["milka_url"])
    ).strip().rstrip("/")
    milka_voice = str(
        raw.get("milka_voice", defaults["milka_voice"])
    ).strip()
    groq_api_key = str(
        raw.get("groq_api_key", defaults["groq_api_key"])
    ).strip()
    groq_model = str(
        raw.get("groq_model", defaults["groq_model"])
    ).strip()
    groq_voice = str(
        raw.get("groq_voice", defaults["groq_voice"])
    ).strip()

    return {
        "enabled": bool(raw.get("enabled", defaults["enabled"])),
        "provider": provider,
        "milka_url": milka_url,
        "milka_voice": milka_voice or defaults["milka_voice"],
        "milka_speed": _float_value(
            raw.get("milka_speed", defaults["milka_speed"]),
            defaults["milka_speed"],
            0.5,
            2.0,
        ),
        "groq_api_key": groq_api_key,
        "groq_model": groq_model or defaults["groq_model"],
        "groq_voice": groq_voice or defaults["groq_voice"],
    }


def normalize_screen_reading(raw):
    defaults = default_screen_reading()
    if not isinstance(raw, dict):
        return defaults

    language = str(raw.get("language", defaults["language"])).strip()
    lang_values = {v for v, _ in SCREEN_READING_LANGUAGES}
    if language not in lang_values:
        language = defaults["language"]

    return {
        "enabled": bool(raw.get("enabled", defaults["enabled"])),
        "language": language,
        "interval": _float_value(
            raw.get("interval", defaults["interval"]),
            defaults["interval"],
            1.0,
            60.0,
        ),
    }


def default_settings():
    providers = [
        {
            "name": "Ollama",
            "type": "ollama",
            "base_url": os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"),
            "model": os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"),
            "api_key": "",
        },
        {
            "name": "OpenRouter",
            "type": "openai",
            "base_url": "https://openrouter.ai/api/v1",
            "model": os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
        },
    ]
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        providers.append(
            {
                "name": "Groq",
                "type": "openai",
                "base_url": "https://api.groq.com/openai/v1",
                "model": os.environ.get(
                    "GROQ_MODEL", "llama-3.3-70b-versatile"
                ),
                "api_key": groq_key,
            }
        )
    return {
        "active": providers[0]["name"],
        "providers": providers,
        "autostart": False,
        "tts": default_tts(),
        "screen_reading": default_screen_reading(),
    }


def normalize_provider(raw):
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    provider_type = str(raw.get("type", "openai")).strip().lower()
    if provider_type not in TYPE_LABELS:
        provider_type = "openai"
    base_url = str(raw.get("base_url", "")).strip()
    model = str(raw.get("model", "")).strip()
    api_key = str(raw.get("api_key", "")).strip()
    if not name:
        return None
    return {
        "name": name,
        "type": provider_type,
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
    }


def load_settings():
    data = None
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None

    if not isinstance(data, dict):
        return default_settings()

    providers = []
    for raw in data.get("providers") or []:
        provider = normalize_provider(raw)
        if provider is not None:
            providers.append(provider)

    if not providers:
        return default_settings()

    names = {provider["name"] for provider in providers}
    active = str(data.get("active", "")).strip()
    if active not in names:
        active = providers[0]["name"]

    return {
        "active": active,
        "providers": providers,
        "autostart": bool(data.get("autostart", False)),
        "tts": normalize_tts(data.get("tts")),
        "screen_reading": normalize_screen_reading(data.get("screen_reading")),
    }


def save_settings(settings):
    SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(SETTINGS_PATH, 0o600)
    except OSError:
        pass


def active_provider(settings):
    providers = settings.get("providers") or []
    if not providers:
        return default_settings()["providers"][0]
    active = settings.get("active")
    for provider in providers:
        if provider["name"] == active:
            return provider
    return providers[0]
