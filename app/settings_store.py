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

DRAWING_PROVIDERS = [
    ("model", "AI model (SVG)"),
    ("cloudflare", "Cloudflare Workers AI (raster)"),
]

DRAWING_PROVIDER_VALUES = {value for value, _ in DRAWING_PROVIDERS}
SEARCH_SAFESEARCH_VALUES = ("on", "moderate", "off")

DEFAULT_CLOUDFLARE_IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"

DEFAULT_VISION_PROVIDER = os.environ.get(
    "VISION_PROVIDER", "Groq"
).strip()
DEFAULT_VISION_MODEL = os.environ.get(
    "VISION_MODEL", "qwen/qwen3.8-27b"
).strip()
DEFAULT_OLLAMA_VISION_MODEL = os.environ.get(
    "OLLAMA_VISION_MODEL", "qwen3-vl:8b"
).strip()

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


def _int_value(value, default, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


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


def default_drawing():
    provider = os.environ.get("DRAWING_PROVIDER", "").strip().lower()
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if api_token.lower().startswith("bearer "):
        api_token = api_token[7:].strip()

    # If credentials are supplied through .env, make Cloudflare the natural
    # default without overriding an explicit DRAWING_PROVIDER=model choice.
    if provider not in DRAWING_PROVIDER_VALUES:
        provider = "cloudflare" if account_id and api_token else "model"

    model = os.environ.get(
        "CLOUDFLARE_IMAGE_MODEL", DEFAULT_CLOUDFLARE_IMAGE_MODEL
    ).strip()
    return {
        "provider": provider,
        "cloudflare_account_id": account_id,
        "cloudflare_api_token": api_token,
        "cloudflare_model": model or DEFAULT_CLOUDFLARE_IMAGE_MODEL,
        "cloudflare_steps": _int_value(
            os.environ.get("CLOUDFLARE_IMAGE_STEPS", "4"), 4, 1, 8
        ),
    }


def default_vision():
    return {
        "enabled": _env_bool("VISION_ENABLED", True),
        "provider": DEFAULT_VISION_PROVIDER or "Groq",
        "model": DEFAULT_VISION_MODEL or "qwen/qwen3.8-27b",
        "max_width": _int_value(
            os.environ.get("VISION_MAX_WIDTH", "1600"), 1600, 640, 3840
        ),
        "jpeg_quality": _int_value(
            os.environ.get("VISION_JPEG_QUALITY", "82"), 82, 50, 95
        ),
    }


def normalize_vision(raw):
    defaults = default_vision()
    if not isinstance(raw, dict):
        return defaults

    provider = str(raw.get("provider", defaults["provider"])).strip()
    model = str(raw.get("model", defaults["model"])).strip()
    return {
        "enabled": bool(raw.get("enabled", defaults["enabled"])),
        "provider": provider or defaults["provider"],
        "model": model or defaults["model"],
        "max_width": _int_value(
            raw.get("max_width", defaults["max_width"]),
            defaults["max_width"],
            640,
            3840,
        ),
        "jpeg_quality": _int_value(
            raw.get("jpeg_quality", defaults["jpeg_quality"]),
            defaults["jpeg_quality"],
            50,
            95,
        ),
    }


def normalize_drawing(raw):
    defaults = default_drawing()
    if not isinstance(raw, dict):
        return defaults

    provider = str(raw.get("provider", defaults["provider"])).strip().lower()
    if provider not in DRAWING_PROVIDER_VALUES:
        provider = defaults["provider"]

    account_id = str(
        raw.get("cloudflare_account_id", defaults["cloudflare_account_id"])
    ).strip()
    api_token = str(
        raw.get("cloudflare_api_token", defaults["cloudflare_api_token"])
    ).strip()
    if api_token.lower().startswith("bearer "):
        api_token = api_token[7:].strip()
    model = str(
        raw.get("cloudflare_model", defaults["cloudflare_model"])
    ).strip()

    return {
        "provider": provider,
        "cloudflare_account_id": account_id,
        "cloudflare_api_token": api_token,
        "cloudflare_model": model or DEFAULT_CLOUDFLARE_IMAGE_MODEL,
        "cloudflare_steps": _int_value(
            raw.get("cloudflare_steps", defaults["cloudflare_steps"]),
            defaults["cloudflare_steps"],
            1,
            8,
        ),
    }


def default_life():
    return {
        "enabled": _env_bool("LIFE_ENABLED", True),
        "suggest_outfit": _env_bool("LIFE_SUGGEST_OUTFIT", True),
        "draw": _env_bool("LIFE_DRAW", True),
        "min_minutes": _int_value(
            os.environ.get("LIFE_MIN_MINUTES", "10"), 10, 1, 1440
        ),
        "max_minutes": _int_value(
            os.environ.get("LIFE_MAX_MINUTES", "30"), 30, 1, 1440
        ),
    }


def normalize_life(raw):
    defaults = default_life()
    if not isinstance(raw, dict):
        return defaults

    minimum = _int_value(
        raw.get("min_minutes", defaults["min_minutes"]),
        defaults["min_minutes"],
        1,
        1440,
    )
    maximum = _int_value(
        raw.get("max_minutes", defaults["max_minutes"]),
        defaults["max_minutes"],
        1,
        1440,
    )
    if maximum < minimum:
        maximum = minimum

    return {
        "enabled": bool(raw.get("enabled", defaults["enabled"])),
        "suggest_outfit": bool(
            raw.get("suggest_outfit", defaults["suggest_outfit"])
        ),
        "draw": bool(raw.get("draw", defaults["draw"])),
        "min_minutes": minimum,
        "max_minutes": maximum,
    }


def default_search():
    safesearch = os.environ.get("SEARCH_SAFESEARCH", "moderate").strip().lower()
    if safesearch not in SEARCH_SAFESEARCH_VALUES:
        safesearch = "moderate"
    return {
        "enabled": _env_bool("SEARCH_ENABLED", True),
        "max_results": _int_value(
            os.environ.get("SEARCH_MAX_RESULTS", "5"), 5, 1, 10
        ),
        "region": os.environ.get("SEARCH_REGION", "ru-ru").strip() or "ru-ru",
        "safesearch": safesearch,
        "google": _env_bool("SEARCH_GOOGLE", True),
        "youtube": _env_bool("SEARCH_YOUTUBE", True),
    }


def normalize_search(raw):
    defaults = default_search()
    if not isinstance(raw, dict):
        return defaults

    safesearch = str(
        raw.get("safesearch", defaults["safesearch"])
    ).strip().lower()
    if safesearch not in SEARCH_SAFESEARCH_VALUES:
        safesearch = defaults["safesearch"]
    region = str(raw.get("region", defaults["region"])).strip()
    return {
        "enabled": bool(raw.get("enabled", defaults["enabled"])),
        "max_results": _int_value(
            raw.get("max_results", defaults["max_results"]),
            defaults["max_results"],
            1,
            10,
        ),
        "region": region or defaults["region"],
        "safesearch": safesearch,
        "google": bool(raw.get("google", defaults["google"])),
        "youtube": bool(raw.get("youtube", defaults["youtube"])),
    }


def default_history():
    return {
        "limit": _int_value(
            os.environ.get("AI_HISTORY_LIMIT", "20"), 20, 2, 100
        ),
        "keep_recent": _int_value(
            os.environ.get("HISTORY_KEEP_RECENT", "6"), 6, 2, 20
        ),
    }


def normalize_history(raw):
    defaults = default_history()
    if not isinstance(raw, dict):
        return defaults
    return {
        "limit": _int_value(
            raw.get("limit", defaults["limit"]),
            defaults["limit"],
            2,
            100,
        ),
        "keep_recent": _int_value(
            raw.get("keep_recent", defaults["keep_recent"]),
            defaults["keep_recent"],
            2,
            20,
        ),
    }


def default_addons():
    return {"disabled": [], "settings": {}}


def normalize_addons(raw):
    if not isinstance(raw, dict):
        return default_addons()
    disabled = []
    for item in raw.get("disabled") or []:
        text = str(item).strip()
        if text and text not in disabled:
            disabled.append(text)
    raw_settings = raw.get("settings")
    per_addon = {}
    if isinstance(raw_settings, dict):
        for key, value in raw_settings.items():
            if isinstance(value, dict):
                per_addon[str(key)] = value
    return {"disabled": sorted(disabled), "settings": per_addon}


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
    vision = default_vision()
    if not any(provider["name"] == vision["provider"] for provider in providers):
        vision["provider"] = providers[0]["name"]
        if providers[0]["type"] == "ollama" and vision["model"] in (
            "",
            DEFAULT_VISION_MODEL,
        ):
            vision["model"] = DEFAULT_OLLAMA_VISION_MODEL

    return {
        "active": providers[0]["name"],
        "providers": providers,
        "autostart": False,
        "tts": default_tts(),
        "drawing": default_drawing(),
        "vision": vision,
        "life": default_life(),
        "search": default_search(),
        "history": default_history(),
        "addons": default_addons(),
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

    vision = normalize_vision(data.get("vision"))
    if vision["provider"] not in names:
        vision["provider"] = active
        raw_vision = data.get("vision")
        if (
            not isinstance(raw_vision, dict)
            or not str(raw_vision.get("model", "")).strip()
            or vision["model"] == DEFAULT_VISION_MODEL
        ):
            selected = next(
                (
                    provider
                    for provider in providers
                    if provider["name"] == vision["provider"]
                ),
                providers[0],
            )
            if selected["type"] == "ollama":
                vision["model"] = DEFAULT_OLLAMA_VISION_MODEL

    return {
        "active": active,
        "providers": providers,
        "autostart": bool(data.get("autostart", False)),
        "tts": normalize_tts(data.get("tts")),
        "drawing": normalize_drawing(data.get("drawing")),
        "vision": vision,
        "life": normalize_life(data.get("life")),
        "search": normalize_search(data.get("search")),
        "history": normalize_history(data.get("history")),
        "addons": normalize_addons(data.get("addons")),
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


def provider_named(settings, name):
    name = str(name or "").strip()
    for provider in settings.get("providers") or []:
        if provider["name"] == name:
            return provider
    return None


def active_provider(settings):
    providers = settings.get("providers") or []
    if not providers:
        return default_settings()["providers"][0]
    active = settings.get("active")
    for provider in providers:
        if provider["name"] == active:
            return provider
    return providers[0]


def vision_provider(settings):
    """Return the endpoint used to look at screenshots."""
    vision = settings.get("vision") or {}
    provider = provider_named(settings, vision.get("provider"))
    if provider is None:
        provider = active_provider(settings)
    result = dict(provider)
    model = str(vision.get("model") or "").strip()
    if model:
        result["model"] = model
    return result
