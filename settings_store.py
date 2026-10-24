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
