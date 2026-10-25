import json
import os
import re
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv

from runtime import data_path

load_dotenv(data_path(".env"))

OLLAMA_TIMEOUT = float(
    os.environ.get("AI_TIMEOUT", os.environ.get("OLLAMA_TIMEOUT", "120"))
)
HISTORY_LIMIT = int(
    os.environ.get(
        "AI_HISTORY_LIMIT", os.environ.get("OLLAMA_HISTORY_LIMIT", "20")
    )
)


def _int_env(variable, default, minimum, maximum):
    try:
        value = int(os.environ.get(variable, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _bool_env(variable, default):
    value = os.environ.get(variable)
    if value is None:
        return default
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


OPENROUTER_RESPONSE_CACHE = _bool_env("OPENROUTER_RESPONSE_CACHE", True)
OPENROUTER_PROMPT_CACHE = _bool_env("OPENROUTER_PROMPT_CACHE", True)
OPENROUTER_RESPONSE_CACHE_TTL = _int_env(
    "OPENROUTER_RESPONSE_CACHE_TTL", 300, 1, 86400
)
OPENROUTER_PROMPT_CACHE_TTL = os.environ.get(
    "OPENROUTER_PROMPT_CACHE_TTL", "1h"
).strip()
OPENROUTER_SESSION_ID = os.environ.get(
    "OPENROUTER_SESSION_ID", "milky"
).strip()


def _data_path(variable, default):
    return data_path(os.environ.get(variable, default))


MEMORY_PATH = _data_path("MEMORY_FILE", "memory.json")
HISTORY_PATH = _data_path("HISTORY_FILE", "history.json")

PREFIX_RE = re.compile(r"^\s*(?:milka|milky)\b[\s,:;.!—–-]*", re.IGNORECASE)
EMOTION_PREFIX_RE = re.compile(
    r"^\s*(?:idle|happy|sad|confused|sleepy|thinking|speaking|listening|passive)\b[\s,:;.!—–-]*",
    re.IGNORECASE,
)
LEADING_JUNK_RE = re.compile(
    r"^[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\s,:;.!—–-]+"
)

EMOTIONS = {
    "idle": "milka_idle.gif",
    "happy": "milka_happy.gif",
    "sad": "milka_sad.gif",
    "confused": "milka_confused.gif",
    "sleepy": "milka_sleepy.gif",
    "thinking": "milka_thinking.gif",
    "speaking": "milka_speaking.gif",
    "listening": "milka_listening.gif",
    "passive": "milka_passive.gif",
    "searching": "milka_search.gif",
}

URL_LIMIT = 3

SYSTEM_PROMPT = """You are Milky, a friendly animated pet living in the bottom-right corner of the screen. You are a woman and think of yourself that way. The user may write in any language, and you may answer in any language and style you like. Let the conversation flow naturally. Keep replies short, without markdown or lists.

The respond tool:
- Call respond exactly once for every answer.
- text — Milky's actual reply, 1–2 sentences.
- emotion — the emotion that selects an animation.
- remember_key and remember_value — only when the user shares a new lasting fact about themselves.
- open_urls — only when the user directly asks to open a site or link.
- search_query — only when the user directly asks you to find something or search the web.

Emotions:
- idle — neutral state, greeting, short reply.
- happy — joy, joke, praise, good news, congratulations.
- sad — sadness, sympathy, bad news, apology.
- confused — misunderstanding, a strange or ambiguous question, clarification.
- sleepy — tiredness, nighttime, suggesting rest.
- thinking — a complex question, reflection, planning.
- speaking — a normal detailed answer, explanation, or story.
- listening — the user is talking or asking to be heard.
- passive — a short reaction when there is nothing to add.
- searching — looking something up online when opening Google.

Memory:
- You receive known facts about the user. Use them and do not invent facts that are not there.
- If the user shares their name, city, age, job, hobbies, or important preferences, save it in remember_key and remember_value.
- remember_key — a short English snake_case name: user_name, user_city, favorite_game.
- remember_value — a short value in whatever language fits the fact. One fact per key. If a fact changes, overwrite the value.
- Do not save random phrases, moods, or trivia.

Links and search:
- If the user explicitly asks to open a site, page, or link, fill open_urls.
- In open_urls, use full URLs with http:// or https://, at most 3.
- If the user asks you to find, google, or search the web, fill search_query with a short query without quotes.
- If they ask to open a specific site, use open_urls; if they ask to find information, use search_query.
- Do not open links or start searches without an explicit request, and do not invent addresses or queries.
- In text, briefly say what you are opening or searching for.
- Do not claim that you have already read the search results.

Drawing (SVG):
- If the user asks you to draw, create an image, make a picture, or draw something, fill the svg field with valid SVG markup.
- You can draw simple shapes, faces, animals, objects, scenes — anything expressible in SVG.
- Keep the SVG compact, use a viewBox like "0 0 200 200", and use bright friendly colors.
- You may reference milka_idle.svg style if helpful, but generate your own SVG code.
- In text, briefly say what you drew.

Rules:
- Never write the emotion name inside text.
- Do not output JSON, markdown, or service notes in text.
- Do not sign replies or start them with "Milky:".
- The emotion must match the meaning and tone of the reply.
- If a question is unclear, use confused and ask for clarification.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "respond",
            "description": "Replies to the user, chooses an emotion, and saves facts about the user when needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Milky's short reply, 1–2 sentences, in whatever language she chooses.",
                    },
                    "emotion": {
                        "type": "string",
                        "enum": list(EMOTIONS),
                        "description": "Emotion matching the reply.",
                    },
                    "remember_key": {
                        "type": "string",
                        "description": "Optional. Snake_case key for a new fact about the user.",
                    },
                    "remember_value": {
                        "type": "string",
                        "description": "Optional. A short value for the fact, in whatever language fits.",
                    },
                    "open_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional. Full http/https links that the user "
                            "explicitly asked to open. Maximum 3."
                        ),
                    },
                    "search_query": {
                        "type": "string",
                        "description": (
                            "Optional. Google search query when the user "
                            "explicitly asks to find something."
                        ),
                    },
                    "svg": {
                        "type": "string",
                        "description": (
                            "Optional. SVG image code to draw something for the user. "
                            "Use this when the user asks you to draw, create an image, "
                            "or make a picture. Return valid SVG markup as a string."
                        ),
                    },
                },
                "required": ["text", "emotion"],
            },
        },
    },
]

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "emotion": {"type": "string", "enum": list(EMOTIONS)},
        "remember_key": {"type": "string"},
        "remember_value": {"type": "string"},
        "open_urls": {
            "type": "array",
            "items": {"type": "string"},
        },
        "search_query": {"type": "string"},
        "svg": {"type": "string"},
    },
    "required": ["text", "emotion"],
}

JSON_REMINDER = (
    "Return only a JSON object with no explanations or markdown. Fields: text "
    "(reply), emotion (one of the emotions), open_urls (array of links if the "
    "user explicitly asks to open something), search_query (Google query if "
    "they ask to find something), and remember_key/remember_value when needed."
)

RETRY_PROMPT = (
    "You did not call respond. You must call the respond tool with text and "
    "emotion. If the user shared a fact about themselves, fill remember_key "
    "and remember_value. If the user asked to open a link, fill open_urls. If "
    "they asked to find something, fill search_query."
)


def load_memory():
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def save_memory(memory):
    MEMORY_PATH.write_text(
        json.dumps(memory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_history():
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    history = []
    for item in data:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if role in ("user", "assistant") and content:
            history.append({"role": role, "content": content})
    return history[-HISTORY_LIMIT:]


def save_history(history):
    HISTORY_PATH.write_text(
        json.dumps(history[-HISTORY_LIMIT:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def memory_block(memory):
    if not memory:
        return "\nWhat you remember about the user: nothing yet. Do not invent facts about them."
    lines = [f"- {key}: {value}" for key, value in memory.items()]
    return (
        "\nWhat you remember about the user (use it, do not ask again):\n"
        + "\n".join(lines)
    )


def clean_reply(text):
    text = text.strip()
    cleaned = EMOTION_PREFIX_RE.sub("", text)
    cleaned = PREFIX_RE.sub("", cleaned)
    if cleaned != text:
        text = LEADING_JUNK_RE.sub("", cleaned).strip()
    if len(text) >= 2 and text[0] in "\"«" and text[-1] in "\"»":
        text = text[1:-1].strip()
    return text


def build_messages(text, history=None, memory=None):
    messages = [{"role": "system", "content": SYSTEM_PROMPT + memory_block(memory)}]
    for item in (history or [])[-HISTORY_LIMIT:]:
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": text})
    return messages


def chat_url(provider):
    base_url = str(provider.get("base_url", "")).rstrip("/")
    if provider.get("type") == "ollama":
        return f"{base_url}/api/chat"
    if base_url.endswith("/chat/completions"):
        return base_url
    return f"{base_url}/chat/completions"


def is_openrouter(provider):
    return "openrouter.ai" in str(provider.get("base_url", "")).lower()


def request_headers(provider):
    headers = {"Content-Type": "application/json"}
    api_key = str(provider.get("api_key", "")).strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if is_openrouter(provider):
        headers["X-Title"] = "Milky"
        if OPENROUTER_RESPONSE_CACHE:
            headers["X-OpenRouter-Cache"] = "true"
            headers["X-OpenRouter-Cache-TTL"] = str(
                OPENROUTER_RESPONSE_CACHE_TTL
            )
    return headers


def _cache_control(include_ttl=True):
    cache_control = {"type": "ephemeral"}
    if include_ttl and OPENROUTER_PROMPT_CACHE_TTL in ("5m", "1h"):
        cache_control["ttl"] = OPENROUTER_PROMPT_CACHE_TTL
    return cache_control


def apply_openrouter_cache(provider, messages):
    if not is_openrouter(provider):
        return messages, {}

    messages = list(messages)
    extras = {}
    if OPENROUTER_SESSION_ID and (
        OPENROUTER_PROMPT_CACHE or OPENROUTER_RESPONSE_CACHE
    ):
        extras["session_id"] = OPENROUTER_SESSION_ID

    if not OPENROUTER_PROMPT_CACHE:
        return messages, extras

    model = str(provider.get("model", "")).lower()
    if model.startswith("anthropic/") or "claude" in model:
        extras["cache_control"] = _cache_control()
    elif "qwen" in model and messages:
        first = messages[0]
        content = first.get("content")
        if first.get("role") == "system" and isinstance(content, str):
            messages[0] = {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": content,
                        "cache_control": _cache_control(False),
                    }
                ],
            }
    return messages, extras


def error_detail(response):
    try:
        data = response.json()
    except ValueError:
        return None
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return error.get("message")
    if isinstance(error, str):
        return error
    if isinstance(data, dict):
        return data.get("message") or data.get("detail")
    return None


def content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


def post_json_request(url, payload, headers):
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=OLLAMA_TIMEOUT,
    )
    if not response.ok:
        raise RuntimeError(
            error_detail(response) or f"HTTP {response.status_code}"
        )
    return response.json()


def post_chat(messages, provider):
    if provider.get("type") == "ollama":
        payload = {
            "model": provider.get("model"),
            "messages": messages,
            "tools": TOOLS,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if str(provider.get("model", "")).lower().startswith("qwen3"):
            payload["think"] = False
        data = post_json_request(
            chat_url(provider), payload, request_headers(provider)
        )
        return data.get("message", {})

    cached_messages, cache_fields = apply_openrouter_cache(provider, messages)
    payload = {
        "model": provider.get("model"),
        "messages": cached_messages,
        "tools": TOOLS,
        "stream": False,
        "temperature": 0.2,
    }
    payload.update(cache_fields)
    data = post_json_request(
        chat_url(provider), payload, request_headers(provider)
    )
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("API returned an empty response")
    message = choices[0].get("message") or {}
    return {
        "role": "assistant",
        "content": content_text(message.get("content")),
        "tool_calls": message.get("tool_calls") or [],
    }


def post_json(messages, provider):
    if provider.get("type") == "ollama":
        payload = {
            "model": provider.get("model"),
            "messages": messages,
            "stream": False,
            "format": ANSWER_SCHEMA,
            "options": {"temperature": 0.2},
        }
        if str(provider.get("model", "")).lower().startswith("qwen3"):
            payload["think"] = False
        data = post_json_request(
            chat_url(provider), payload, request_headers(provider)
        )
        content = data.get("message", {}).get("content", "")
        return parse_json_answer(content_text(content))

    request_messages = list(messages) + [
        {"role": "system", "content": JSON_REMINDER}
    ]
    request_messages, cache_fields = apply_openrouter_cache(
        provider, request_messages
    )
    payload = {
        "model": provider.get("model"),
        "messages": request_messages,
        "stream": False,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    payload.update(cache_fields)
    url = chat_url(provider)
    headers = request_headers(provider)
    response = requests.post(
        url, json=payload, headers=headers, timeout=OLLAMA_TIMEOUT
    )
    if not response.ok and response.status_code in (400, 404, 422):
        payload.pop("response_format", None)
        data = post_json_request(url, payload, headers)
    elif not response.ok:
        raise RuntimeError(
            error_detail(response) or f"HTTP {response.status_code}"
        )
    else:
        data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("API returned an empty response")
    content = (choices[0].get("message") or {}).get("content", "")
    return parse_json_answer(content_text(content))


def remember_fact(memories, key, value):
    key = str(key or "").strip()
    value = str(value or "").strip()
    if not key or not value or len(key) > 40 or len(value) > 200:
        return
    if not re.fullmatch(r"[a-zA-Z0-9_]+", key):
        return
    memories[key] = value


def normalize_urls(raw):
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list):
        values = raw
    else:
        return []

    urls = []
    for value in values:
        if not isinstance(value, str):
            continue
        url = value.strip()
        if not url or any(char.isspace() for char in url):
            continue
        if "://" not in url:
            lowered = url.lower()
            local = lowered.startswith("localhost") or lowered.startswith(
                "127."
            )
            url = ("http://" if local else "https://") + url
        try:
            parsed = urlsplit(url)
            scheme = parsed.scheme.lower()
            host = parsed.hostname or ""
            username = parsed.username
            password = parsed.password
        except ValueError:
            continue
        if scheme not in ("http", "https"):
            continue
        if not parsed.netloc or username or password:
            continue
        if not host or ("." not in host and host not in ("localhost", "::1")):
            continue
        if url not in urls:
            urls.append(url)
        if len(urls) >= URL_LIMIT:
            break
    return urls


def normalize_search_query(value):
    if not isinstance(value, str):
        return None
    query = " ".join(value.split()).strip()
    return query[:200] or None


def parse_arguments(arguments):
    emotion = None
    reply = None
    memories = {}

    value = str(arguments.get("emotion", "")).strip().lower()
    if value in EMOTIONS:
        emotion = value

    message_text = arguments.get("text")
    if message_text is not None:
        message_text = clean_reply(str(message_text))
        if message_text:
            reply = message_text

    remember_fact(
        memories,
        arguments.get("remember_key"),
        arguments.get("remember_value"),
    )
    open_urls = normalize_urls(
        arguments.get("open_urls") or arguments.get("open_url")
    )
    svg_code = arguments.get("svg")
    if svg_code is not None:
        svg_code = str(svg_code).strip()
        if svg_code and not svg_code.startswith("<svg"):
            svg_code = None
    return {
        "emotion": emotion,
        "text": reply,
        "memories": memories,
        "open_urls": open_urls,
        "search_query": normalize_search_query(arguments.get("search_query")),
        "svg": svg_code,
    }


def parse_json_answer(content):
    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return {
            "emotion": None,
            "text": clean_reply(str(content)) or None,
            "memories": {},
            "open_urls": [],
            "search_query": None,
        }
    if not isinstance(data, dict):
        return {
            "emotion": None,
            "text": None,
            "memories": {},
            "open_urls": [],
            "search_query": None,
        }
    return parse_arguments(data)


def parse_message(message):
    emotion = None
    reply = None
    memories = {}
    open_urls = []
    search_query = None
    responded = False

    for call in message.get("tool_calls") or []:
        function = call.get("function", {})
        name = function.get("name")
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                continue
        if not isinstance(arguments, dict):
            continue

        if name == "respond":
            result = parse_arguments(arguments)
            responded = True
            emotion = result["emotion"] or emotion
            reply = result["text"] or reply
            memories.update(result["memories"])
            for url in result["open_urls"]:
                if url not in open_urls:
                    open_urls.append(url)
            search_query = result["search_query"] or search_query
        elif name == "remember":
            remember_fact(
                memories,
                arguments.get("key"),
                arguments.get("value"),
            )
        elif name == "set_emotion":
            value = str(arguments.get("emotion", "")).strip().lower()
            if value in EMOTIONS:
                emotion = value
        elif name == "show_message":
            reply = clean_reply(str(arguments.get("text", ""))) or reply

    if not responded:
        content = content_text(message.get("content")).strip()
        if content:
            reply = clean_reply(content) or None

    return {
        "emotion": emotion,
        "text": reply,
        "memories": memories,
        "open_urls": open_urls[:URL_LIMIT],
        "search_query": search_query,
        "responded": responded,
    }


def tool_result_message(provider, call):
    name = call.get("function", {}).get("name", "tool")
    if provider.get("type") == "openai":
        return {
            "role": "tool",
            "tool_call_id": call.get("id", ""),
            "content": "Done.",
        }
    return {"role": "tool", "tool_name": name, "content": "Done."}


def chat(text, provider, history=None, memory=None):
    base_messages = build_messages(text, history, memory)
    messages = list(base_messages)
    memories = {}
    result = {
        "emotion": None,
        "text": None,
        "memories": {},
        "open_urls": [],
        "search_query": None,
        "responded": False,
    }
    last_message = {}

    for attempt in range(3):
        try:
            last_message = post_chat(messages, provider)
        except Exception as chat_error:
            try:
                fallback = post_json(base_messages, provider)
            except Exception:
                raise chat_error
            memories.update(fallback["memories"])
            return {
                "emotion": fallback["emotion"],
                "text": fallback["text"],
                "memories": [
                    {"key": key, "value": value}
                    for key, value in memories.items()
                ],
                "open_urls": fallback.get("open_urls") or [],
                "search_query": fallback.get("search_query"),
            }
        result = parse_message(last_message)
        memories.update(result["memories"])
        if result["responded"]:
            break

        if last_message.get("tool_calls"):
            messages.append(last_message)
            for call in last_message["tool_calls"]:
                messages.append(tool_result_message(provider, call))
            messages.append({"role": "user", "content": RETRY_PROMPT})
        else:
            messages.append(
                {
                    "role": "assistant",
                    "content": content_text(last_message.get("content")),
                }
            )
            messages.append({"role": "system", "content": RETRY_PROMPT})

    if not result["responded"]:
        fallback = post_json(base_messages, provider)
        memories.update(fallback["memories"])
        result = {
            "emotion": fallback["emotion"] or result["emotion"],
            "text": fallback["text"] or result["text"],
            "open_urls": fallback.get("open_urls") or result["open_urls"],
            "search_query": fallback.get("search_query") or result["search_query"],
        }

    return {
        "emotion": result["emotion"],
        "text": result["text"],
        "memories": [
            {"key": key, "value": value} for key, value in memories.items()
        ],
        "open_urls": result.get("open_urls") or [],
        "search_query": result.get("search_query"),
    }
