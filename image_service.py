"""Cloudflare Workers AI image generation.

The drawing path uses FLUX.1 schnell through the Workers AI REST API.  The
service is optional: when it is not configured, Milky keeps using the existing
SVG drawing path.
"""

import base64
import binascii
import os
import re
from urllib.parse import quote

import requests

DEFAULT_MODEL = "@cf/black-forest-labs/flux-1-schnell"
DEFAULT_STEPS = 4
MAX_PROMPT_LENGTH = 2048
MAX_IMAGE_BYTES = 20 * 1024 * 1024
CLOUDFLARE_API = "https://api.cloudflare.com/client/v4/accounts"

# The official portrait is line art, but a short description still helps the
# image model keep the important features when Milky appears in a scene.
MILKY_APPEARANCE = (
    "Milky is a cute cat-eared girl with a round white face, two large "
    "rounded ears, big friendly eyes, rosy cheeks, and a small gentle smile. "
    "Keep her face clear and visible. Do not add clothing, hats, glasses, "
    "scarves, or other accessories unless the request explicitly asks for "
    "them."
)


class ImageServiceError(RuntimeError):
    """A readable error returned by the image service."""


def _float_env(variable, default, minimum, maximum):
    try:
        value = float(os.environ.get(variable, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _int_env(variable, default, minimum, maximum):
    try:
        value = int(os.environ.get(variable, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def cloudflare_configured(settings):
    """Return True when Cloudflare is selected and has both credentials."""
    if not isinstance(settings, dict):
        return False
    provider = str(settings.get("provider", "")).strip().lower()
    if provider != "cloudflare":
        return False
    account_id = str(settings.get("cloudflare_account_id", "")).strip()
    api_token = str(settings.get("cloudflare_api_token", "")).strip()
    return bool(account_id and api_token)


def build_image_prompt(subject, milky=False, selfie=False):
    """Build a concise English prompt for FLUX from a drawing request."""
    subject = " ".join(str(subject or "").split())
    if not subject:
        subject = "a small cheerful scene"
    subject = subject[:1200]

    if selfie:
        opening = (
            "Create a complete, polished 2D illustration of Milky and the "
            f"scene described here: {subject}. "
            "Milky is the main character. "
        )
    elif milky:
        opening = (
            "Create a complete, polished 2D illustration for this request: "
            f"{subject}. Include Milky in the scene. "
        )
    else:
        opening = (
            "Create a complete, polished 2D illustration for this request: "
            f"{subject}. The requested subject must be the main focus. "
            "Do not replace it with Milky or an unrelated character. "
        )

    details = (
        "Make a full scene rather than a flat icon: a clear subject, a "
        "background, a ground plane or setting, soft lighting, shading, "
        "highlights, and a few small finishing details. Cute, warm, "
        "storybook animation style, harmonious pastel colors, clean shapes, "
        "square composition, subject centered with breathing room. "
        "No text, letters, captions, signatures, watermarks, borders, frames, "
        "UI elements, or logos. Do not copy an existing artwork. "
    )
    if milky or selfie:
        details += MILKY_APPEARANCE
    return (opening + details)[:MAX_PROMPT_LENGTH]


def _error_text(response, data=None):
    parts = []
    if isinstance(data, dict):
        for error in data.get("errors") or []:
            if isinstance(error, dict):
                message = error.get("message") or error.get("detail")
                if message:
                    parts.append(str(message))
            elif error:
                parts.append(str(error))
        if not parts and data.get("success") is False:
            message = data.get("message") or data.get("error")
            if message:
                parts.append(str(message))
    if not parts:
        text = " ".join(str(getattr(response, "text", "") or "").split())
        if text:
            parts.append(text)
    if not parts:
        status = getattr(response, "status_code", "?")
        parts.append(f"HTTP {status}")
    message = "; ".join(parts)
    return message[:600]


def _decode_base64_image(value):
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    text = str(value or "").strip()
    if text.startswith("data:"):
        _, _, text = text.partition(",")
    text = re.sub(r"\s+", "", text)
    if not text:
        raise ImageServiceError("Cloudflare returned an empty image.")
    try:
        return base64.b64decode(text, validate=False)
    except (ValueError, binascii.Error) as error:
        raise ImageServiceError("Cloudflare returned invalid image data.") from error


def _image_type(raw):
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise ImageServiceError(
        "Cloudflare returned an unsupported image format."
    )


def generate_image(prompt, account_id, api_token, model=None, steps=None):
    """Generate one raster image with Cloudflare Workers AI.

    Returns a dictionary with the raw image bytes, mime type, extension and
    model name.  Raises ImageServiceError for credential, quota, and response
    errors so the caller can fall back to the SVG path.
    """
    account_id = str(account_id or "").strip()
    api_token = str(api_token or "").strip()
    if api_token.lower().startswith("bearer "):
        api_token = api_token[7:].strip()
    if not account_id or not api_token:
        raise ImageServiceError(
            "Cloudflare account ID and API token are required."
        )

    model = str(model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if steps is None:
        steps = _int_env("CLOUDFLARE_IMAGE_STEPS", DEFAULT_STEPS, 1, 8)
    try:
        steps = max(1, min(8, int(steps)))
    except (TypeError, ValueError):
        steps = DEFAULT_STEPS

    prompt = " ".join(str(prompt or "").split())[:MAX_PROMPT_LENGTH]
    if not prompt:
        raise ImageServiceError("The drawing prompt is empty.")

    url = (
        f"{CLOUDFLARE_API}/{quote(account_id, safe='')}/ai/run/"
        f"{quote(model, safe='@/')}"
    )
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    payload = {"prompt": prompt, "steps": steps}
    timeout = _float_env("CLOUDFLARE_IMAGE_TIMEOUT", 120, 10, 300)

    try:
        response = requests.post(
            url, json=payload, headers=headers, timeout=timeout
        )
    except requests.RequestException as error:
        raise ImageServiceError(f"Cloudflare request failed: {error}") from error

    data = None
    content_type = str(response.headers.get("Content-Type", "")).lower()
    if response.ok and content_type.startswith("image/"):
        raw = response.content
    else:
        try:
            data = response.json()
        except ValueError:
            data = None

    if not response.ok:
        raise ImageServiceError(
            f"Cloudflare error: {_error_text(response, data)}"
        )

    if data is None:
        if not response.ok or not response.content:
            raise ImageServiceError("Cloudflare returned an empty response.")
        raw = response.content
    else:
        if isinstance(data, dict) and data.get("success") is False:
            raise ImageServiceError(
                f"Cloudflare error: {_error_text(response, data)}"
            )
        result = data.get("result") if isinstance(data, dict) else None
        if isinstance(result, dict):
            image = result.get("image") or result.get("data")
        elif isinstance(result, str):
            image = result
        else:
            image = data.get("image") if isinstance(data, dict) else None
        raw = _decode_base64_image(image)

    if not raw:
        raise ImageServiceError("Cloudflare returned an empty image.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ImageServiceError("Cloudflare returned an image that is too large.")

    mime, extension = _image_type(raw)
    return {
        "data": raw,
        "mime": mime,
        "ext": extension,
        "model": model,
        "provider": "Cloudflare Workers AI",
    }
