# Milky

An animated AI desktop pet: a transparent window, emotion animations, user memory, and support for local and cloud models.

![Milky](assets/gifs/milka_idle.gif)

## Features

- Transparent always-on-top window.
- Animations for different emotions: `idle`, `listening`, `thinking`, `speaking`, `happy`, `sad`, `confused`, `sleepy`, `passive`, `music`.
- Short, natural replies from Milky. The user can write in any language, and Milky can answer in whatever language and style feels natural to her.
- Memory of user facts in `memory.json`.
- Conversation history in `history.json`, with local compaction: ask **«сожми историю»**, **«прибери лишнее»**, or **«очисти историю»**.
- Built-in web search that reads titles, snippets, and short excerpts from result pages before answering; YouTube video search is included and needs no API key.
- Support for Ollama, OpenRouter, Groq, and other OpenAI-compatible APIs.
- Provider and model switching in the settings window.
- Request caching for OpenRouter.
- Opening links when the user explicitly asks.
- Detailed drawings: when asked to draw something, Milky saves the illustration to `svg_drawings/`, plays a drawing animation, and shows a notification above her face. With Cloudflare Workers AI configured, she uses FLUX.1 schnell for a polished raster JPEG; otherwise she uses the built-in SVG path. The SVG path includes a quality checklist for anatomy, shading, a background and highlights, and retries a bare illustration with a fresh, template-free prompt. If Cloudflare is unavailable, the app falls back to SVG automatically.
- Official self-portrait: plain selfie requests use her line-art portrait; scene requests such as **нарисуй себя в космосе** draw the full scene.
- AI-generated clothing and accessories: ask her to put on a hat, glasses, scarf, crown or other item and she generates a transparent SVG overlay. Body, neck and head items are layered behind her face line art so clothing cannot hide her eyes or smile; glasses and masks stay in front and are checked for eye clearance. A drawing request never adds clothing on its own. The outfit persists across restarts and can be managed in **Settings → Outfit**.
- Drawing gallery from the tray menu, with click-to-enlarge previews for SVG, PNG, JPEG and WebP drawings and a Delete button for each one. The gallery keeps existing SVG drawings and new Cloudflare raster drawings side by side.
- A small life cycle: every 10–30 minutes Milky may suggest a new accessory or sketch a random picture on her own. Both actions can be disabled in **Settings → Model and voice → Life cycle**.
- Screen vision: ask **что на экране?**, **что ты видишь?** or **what do you see?**; Milky asks what to look for, captures the current screen (through the D-Bus portal on Wayland), describes it with a vision model, and answers with her normal chat model. Groq's `qwen/qwen3.8-27b` works out of the box; local Ollama vision models are supported too.
- Text-to-speech replies through a Milka TTS server or Groq, with configurable endpoint and voice.
- Skills (addons) that add new tools to the model, installable from a public GitHub repository in **Settings → Skills**, with automatic visual settings declared by each skill.
- System tray icon and context menu.
- Linux and Windows installers with optional autostart.
- GitHub Actions build for a standalone Windows executable.

## Requirements

- Python 3.10–3.15 (tested on Python 3.14).
- Linux, Windows, or macOS.
- Ollama with a tool-calling model, or an API key for an OpenAI-compatible service.

## Quick Installation

Run the installer from the project root — the folder that contains `main.py`, `app/`, and `requirements.txt`.

### Linux

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

The installer creates a virtual environment, installs dependencies, adds an application menu shortcut, and installs the `milky` command into `~/.local/bin`.

Enable autostart immediately:

```bash
./scripts/install.sh --autostart
```

Or disable it:

```bash
./scripts/install.sh --no-autostart
```

Uninstall:

```bash
./scripts/install.sh --uninstall
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Enable autostart:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Autostart
```

Uninstall:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Uninstall
```

To skip all prompts, add `-Yes`. The default install directory is `%LOCALAPPDATA%\Milky`.

After installation, autostart can be enabled or disabled in the settings window.

### macOS

Use the manual installation below. Enabling autostart in the settings window creates a LaunchAgent.

## Windows Build

The repository includes a GitHub Actions workflow that builds a standalone Windows executable with PyInstaller.

To build it:

1. Open the **Actions** tab on GitHub.
2. Select **Build Windows**.
3. Click **Run workflow**.
4. Download the `Milky-Windows` artifact after the job finishes.

The workflow also runs on every push to `master` and publishes `Milky-Windows.zip` as a GitHub Release when a `v*` tag is pushed.

The built app is portable: extract the archive to a writable folder and run `Milky.exe`. Place `.env` and the generated `settings.json`, `memory.json`, `history.json`, and `outfit.json` next to the executable. The executable is unsigned, so Windows SmartScreen may show a warning.

## Manual Installation

```bash
git clone <repository-url>
cd milky

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Web search dependencies are included in `requirements.txt`; no separate installation step is needed.

## Ollama Setup

Install Ollama and download a model:

```bash
ollama pull qwen2.5:3b
ollama serve
```

By default, the app uses `http://127.0.0.1:11434` and the `qwen2.5:3b` model. You can change these values in `.env` or in the settings window.

## API Setup

Any OpenAI-compatible endpoint is supported. For OpenRouter or Groq, add the key to `.env`:

```dotenv
OPENROUTER_API_KEY=your_key
OPENROUTER_MODEL=openai/gpt-4o-mini

GROQ_API_KEY=your_key
GROQ_MODEL=llama-3.3-70b-versatile
```

After startup, the app reads settings from `settings.json`. If you changed `.env` after settings were already saved, update the endpoint in the settings window or delete `settings.json`.

## Screen Vision

Milky can look at the current screen when you ask. Before taking the screenshot, she asks **What should I look for on the screen?** so the vision model knows what detail matters. The screenshot is captured only for that request, sent to the selected vision endpoint, and is not kept on disk.

1. Open **Settings → Screen vision**.
2. Keep **Let Milky look at the screen when asked** enabled.
3. Select an endpoint that has a multimodal model.
4. Set **Vision model** to a model with image input support.

On Groq, `qwen/qwen3.8-27b` accepts images and works with text-only chat models such as `openai/gpt-oss-20b`. If it returns empty or incorrect descriptions, select a stronger multimodal model on another configured endpoint, for example Baseten `deepseek-ai/DeepSeek-V4.1-Flash-Fast`, a Gemini model, `openai/gpt-4o-mini`, or a Qwen-VL model. The vision model produces a description first; Milky's active chat model then answers with her normal personality, emotions, tools and memory.

Ask **что на экране?**, **что ты видишь?**, **посмотри на экран**, **what do you see?** or use **Look at screen** in the right-click/tray menu. Enter your follow-up question when prompted, or press Enter with an empty field to just describe the screen. Press Escape or click Milky to cancel.

On Wayland, Milky captures through the freedesktop screenshot portal over D-Bus. The portal may briefly write the image to `~/Pictures`; Milky reads it, sends only the JPEG payload, and deletes the temporary file. Allow screen capture when the desktop asks for permission.

For a local vision model with Ollama:

```bash
ollama pull qwen3-vl:8b
```

Then select the **Ollama** endpoint in **Settings → Screen vision** and set the vision model to `qwen3-vl:8b`. Other Ollama vision models can be used by entering their model name.

## Web Search and Conversation History

Milky has built-in web search and YouTube search. No API key is required: the app uses DuckDuckGo, with Google as an optional fallback. For web searches it reads the result titles, snippets, and short excerpts from the top pages, then answers from that content instead of only opening a search page. Found links open in the browser and are never read aloud.

Configure search in **Settings → Search and history**:

- **Allow Milky to search the web and YouTube** turns the search tools on or off.
- **Results per search** controls how many results are passed to the model.
- **Region** and **Safe search** control the search locale.
- **Try Google as a last-resort source** enables the optional Google fallback.
- **Search YouTube for videos** enables video results for requests such as **найди видео про котиков**.

Conversation compaction keeps the last few messages verbatim and turns older messages into a short local summary. It does not call the model and does not use tokens. Ask Milky:

- **«сожми историю»**, **«прибери лишнее»**, **«почисти историю»** — compact the dialog.
- **«очисти историю»**, **«удали историю»** — clear the dialog. Saved facts in `memory.json` are kept.

The same options are in **Settings → Search and history** under **Conversation history**. `AI_HISTORY_LIMIT` controls how many messages are sent to the model, and `HISTORY_KEEP_RECENT` controls how many recent messages stay verbatim during compaction.

## Cloudflare Workers AI Drawings

Environment defaults:

```dotenv
VISION_ENABLED=true
VISION_PROVIDER=Groq
VISION_MODEL=qwen/qwen3.8-27b
VISION_MAX_WIDTH=1600
VISION_JPEG_QUALITY=82
```

If the screen is not captured on Linux, make sure `xdg-desktop-portal` is running and allow screen capture when the desktop asks. On Wayland, Milky uses the portal over D-Bus instead of Qt's direct framebuffer grab.

## Cloudflare Workers AI Drawings

Milky can render drawings with **Cloudflare Workers AI** and **FLUX.1 schnell**. This is optional; when it is not configured, the original SVG drawing path is used.

1. Open the [Workers AI page](https://dash.cloudflare.com/?to=/:account/ai/workers-ai) in the Cloudflare dashboard. Sign up first if needed.
2. Select **Use REST API**.
3. Select **Create a Workers AI API Token**, review the prefilled permissions, then select **Create API Token**. The token secret is shown only once, so copy it immediately.
4. Copy the **Account ID** shown next to the token instructions on the same page.
5. Enter the account ID, token and model in **Settings → Model and voice → Drawings**, or put them in `.env`:

If you create a custom token instead of using the template, grant both **Workers AI - Read** and **Workers AI - Edit** for the account, as required by the Workers AI REST API.

```dotenv
DRAWING_PROVIDER=cloudflare
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_workers_ai_token
CLOUDFLARE_IMAGE_MODEL=@cf/black-forest-labs/flux-1-schnell
CLOUDFLARE_IMAGE_STEPS=4
```

If both Cloudflare credentials are present and `DRAWING_PROVIDER` is unset, Milky selects Cloudflare automatically. Set `DRAWING_PROVIDER=model` to keep the SVG path. Ask **нарисуй котика**, **draw a cat** or **нарисуй себя в космосе** to test it.

The free plan includes **10,000 Neurons per day**, resetting daily at **00:00 UTC**. The default 1024×1024 image at 4 steps costs about 58 Neurons, which is roughly 170 images per day. The **Test Cloudflare** button reports credential, quota and network errors immediately and also consumes a small amount of the daily allocation. During a chat, Cloudflare errors are logged and Milky falls back to the SVG path.

FLUX is text-to-image only, so it cannot read Milky's SVG reference or guarantee her exact appearance. A short English description of her face and ears is included when she appears in a scene. Non-English drawing requests are translated to English with the active chat provider before they go to FLUX; if translation fails, the original text is sent. All generated raster drawings are saved in `svg_drawings/` and appear in the same gallery as SVG files.

## Running

```bash
python main.py
```

## Controls

- Left click — open the input field.
- Drag — move the pet.
- Enter — send a message.
- Esc — close the input field.
- Right click — open the context menu (Settings, Look at screen, Show / Hide, Quit).
- Tray menu — Show / Hide, Settings, Look at screen, Show drawing gallery, Quit.
- Double-click the tray icon — show or hide the window.

Ask Milky to **draw a cat**, **draw a sun**, **нарисуй котика** or **нарисуй цветок**. Milky keeps her face animation, plays `milka_drawing.gif` and shows a **«Новый рисунок в галерее!»** notification above her. The drawing is saved in `svg_drawings/`; click the notification or open the tray menu → **Show drawing gallery** to browse previews and click any drawing to enlarge it. The gallery shows both SVG and raster drawings. Each drawing has a **Delete** button.

Ask **нарисуй себя**, **селфи**, **автопортрет** or **draw yourself** and she will use her official line-art self-portrait. If you ask for a scene with her, such as **нарисуй себя в космосе** or **draw yourself with a cat**, she draws the full scene instead of only the portrait.

Ask **одень шапку**, **надень очки**, **put on a scarf** or **wear a crown** and Milky generates a transparent clothing overlay. Body, neck and head items are layered behind her face line art, so a scarf or hat cannot cover her eyes or smile; glasses and masks are layered in front and must leave her eyes visible. She can wear several items at once in different slots (for example, a hat, glasses and a scarf). The outfit is saved in `outfit.json` and is restored every time the app starts. Open **Settings → Outfit** to remove an individual item or click **Remove all**. Outfit changes are written when you click **Save**.

## Life Cycle

Milky can do small things on her own while you are not talking to her. A timer fires at a random interval and picks one of the enabled actions:

- **Suggest a new outfit** — a small question appears above her, for example “Want me to put on a warm hat?”, with **Sure** and **Not now** buttons. If you agree, she puts on that accessory right away.
- **Draw something on her own** — she makes a small sketch (cat, sun, flower, rainbow, and so on), saves it to `svg_drawings/`, plays her drawing animation, and shows the usual gallery notification.

She never interrupts an active conversation, an open input field, a visible reply bubble, or a running request, and she stays quiet while the window is hidden. The first check happens a few minutes after startup; later checks use the configured interval.

Open **Settings → Model and voice → Life cycle** to turn the whole behavior off, disable only one of the two actions, or change the interval. The settings are saved in `settings.json` and also accept environment defaults:

```dotenv
LIFE_ENABLED=true
LIFE_SUGGEST_OUTFIT=true
LIFE_DRAW=true
LIFE_MIN_MINUTES=10
LIFE_MAX_MINUTES=30
```

Spontaneous sketches use the built-in SVG illustrations, so they work offline and do not spend API requests or Cloudflare Neurons.

## Skills (Addons)

A skill is a Milky addon: a folder with an `addon.json` manifest and a Python entry module. Skills add tools that the chat model can call, such as checking the weather, controlling music, or reading local data.

Open **Settings → Skills** to see installed skills, enable or disable them, reload them after editing, or open the skills folder.

### Visual settings

A skill can describe its configuration in `addon.json`. Select the skill in **Settings → Skills** and Milky builds the controls automatically. Values are passed to the skill as `ctx.settings` and saved under `addons.settings.<id>` in `settings.json`.

```json
{
  "id": "weather",
  "name": "Weather",
  "version": "1.0.0",
  "api": 1,
  "description": "Current weather and a short forecast.",
  "entry": "addon.py",
  "settings": [
    {
      "key": "city",
      "label": "Default city",
      "type": "string",
      "default": "Berlin",
      "description": "Used when the user does not name a city."
    },
    {
      "key": "units",
      "label": "Units",
      "type": "select",
      "default": "metric",
      "options": [
        {"value": "metric", "label": "Celsius"},
        {"value": "imperial", "label": "Fahrenheit"}
      ]
    },
    {
      "key": "forecast_days",
      "label": "Forecast days",
      "type": "int",
      "default": 3,
      "min": 1,
      "max": 7
    },
    {
      "key": "show_wind",
      "label": "Include wind",
      "type": "bool",
      "default": true
    }
  ]
}
```

Supported field types:

- `string` — single-line text. Add `"multiline": true` for a larger text box.
- `path` — a file or folder picker. Use `"pick": "file"` for files; folders are the default.
- `int` — whole number with optional `min`, `max` and `step`.
- `number` — decimal number with optional `min`, `max`, `step` and `decimals`.
- `bool` — checkbox.
- `select` — dropdown with `options` as a list of `{"value": "...", "label": "..."}` objects (or a dictionary of values to labels).

Every field needs a unique `key`. Optional keys are `label`, `description`, `placeholder`, `default` and `suffix`. Set `"secret": true` to hide a text value behind dots. Secrets are still stored as plain text in `settings.json`; use `.env` for credentials whenever possible.

Read the values in the addon:

```python
from addon_api import tool


@tool("current", "Return the current weather for a city.")
def current(ctx, city: str = ""):
    settings = getattr(ctx, "settings", {})
    city = city or settings.get("city", "Berlin")
    units = settings.get("units", "metric")
    return {"city": city, "units": units, "temperature": "20"}
```

Defaults declared in the manifest are applied automatically. Saved values override them, and unknown keys already present in `settings.json` are preserved. Changes take effect when you click **Save** or **Reload skills**.

### Install from GitHub

1. Put the skill folder in a **public** GitHub repository. The repository can be the skill itself, or it can contain one or more skill folders.
2. Open **Settings → Skills**, paste a link, and click **Install skill**.
3. Confirm the security prompt. Milky downloads the repository archive, validates `addon.json`, copies the skill and its assets into the skills folder, and reloads it.
4. Click **Save** to keep the enabled/disabled state in `settings.json`.

Supported links:

```text
https://github.com/owner/repo
https://github.com/owner/repo/tree/main/path/to/skill
owner/repo
```

A `/tree/<branch>/<folder>` link installs only that folder. A repository link installs every addon found up to four levels deep, unless the repository root is itself an addon. If two folders use the same `id`, the install is rejected. Reinstalling a skill with the same `id` replaces it.

Private repositories, GitHub tokens and git submodules are not supported. The archive limit is 30 MB, and the unpacked size limit is 80 MB.

> **Security:** skills are ordinary Python code and run in the same process as Milky, with the same permissions. They can read files, use the network and control the computer. Only install repositories you trust.

### Skill format

```text
my_skill/
├── addon.json
├── addon.py
└── assets/
    ├── icon.svg
    └── sounds/
        └── done.ogg
```

`addon.json`:

```json
{
  "id": "weather",
  "name": "Weather",
  "version": "1.0.0",
  "api": 1,
  "description": "Current weather and a short forecast.",
  "entry": "addon.py",
  "icon": "assets/icon.svg"
}
```

`addon.py`:

```python
from addon_api import tool


@tool("current", "Return the current weather for a city.")
def current(city: str):
    return {"city": city, "temperature": "20 °C", "condition": "clear"}
```

Each decorated function becomes a tool named `addon__<id>__<tool>` (long ids may be shortened in the public name) and appears in the model's tool list automatically. Tool arguments use a JSON Schema generated from the function signature; add explicit defaults to make arguments optional, or pass an explicit schema as the third `@tool` argument. A parameter named `ctx` receives the addon context and is hidden from the model. An addon can also define `setup(ctx)` and `shutdown(ctx)` functions.

### Assets

Asset files are copied together with the addon by the GitHub installer. Put read-only files in an `assets/` folder:

```python
from addon_api import tool


@tool("help", "Return the addon help text.")
def help_text(ctx):
    return ctx.read_asset("help.txt")


@tool("asset_list", "List files bundled with this addon.")
def asset_list(ctx):
    return ctx.list_assets()
```

`ctx.assets_dir` points to the addon's `assets/` folder. `ctx.asset_path(*parts)` returns an absolute path and rejects paths that escape `assets/`. `ctx.read_asset(*parts)` reads UTF-8 text, or bytes with `binary=True`. `ctx.list_assets()` returns relative file names. Use `ctx.path(*parts)` for other files inside the addon folder.

The optional `icon` manifest field sets the image shown in **Settings → Skills**. SVG, PNG, JPEG and GIF files work. The icon must stay inside the addon folder.

### Animations

Addons can ask Milky's avatar to play a GIF:

```python
ctx.play_animation("assets/music.gif")  # while the addon needs it
ctx.stop_animation()
```

A bare filename such as `milka_idle.gif` is looked up in Milky's `assets/gifs/` folder. A path such as `assets/music.gif` is resolved inside the addon. Use the optional `duration_ms` argument to clear the animation automatically:

```python
ctx.play_animation("milka_happy.gif", duration_ms=4000)
```

The addon animation is shown while Milky is idle. Chat replies, the input field and drawing animations temporarily take priority, then the addon animation returns automatically. Multiple addons can request animations; the most recent request wins, and `stop_animation()` only clears the animation owned by the calling addon.

A tool can receive the addon context by declaring a parameter named `ctx`:

```python
@tool("save_note", "Save a short note.")
def save_note(text: str, ctx):
    path = ctx.data_dir / "notes.txt"
    path.write_text(text, encoding="utf-8")
    return "Saved."
```

Use `ctx.data_dir` for persistent files. It is stored in `addons/.data/<id>/`. Use `ctx.log("message")` to write to Milky's console. Manifest fields: `id` (unique slug), `name`, `version`, `api` (currently `1`), `description`, `entry` (defaults to `addon.py`), and optional `icon`. Addon-specific settings can be placed in `settings.json` under `addons.settings.<id>` and are available as `ctx.settings`.

### Managing skills

- **Disable** a skill with its checkbox and click **Save**. Disabled skills stay on disk but their tools are not offered to the model.
- **Update** a skill by installing the same repository again; the folder is replaced.
- **Uninstall** a skill by opening the skills folder and deleting its folder. Persistent data in `addons/.data/<id>/` is kept unless you delete it too.
- **Debug** a skill by clicking **Reload skills** after editing it. Load errors and the registered tool names are shown in the skill's tooltip. Set `MILKY_ADDON_DEBUG=1` before launching Milky for full Python tracebacks.

## Autostart

Autostart is controlled by the **Launch Milky at login** checkbox in the app settings.

The autostart entry is created at:

- Linux: `~/.config/autostart/milky.desktop`.
- Windows: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\milky-autostart.cmd`.
- macOS: `~/Library/LaunchAgents/com.milky.pet.plist`.

When installing with `scripts/install.sh` or `scripts/install.ps1`, autostart can be enabled immediately or left disabled.

## Environment Variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `OLLAMA_URL` | Ollama address | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | Ollama model | `qwen2.5:3b` |
| `OPENROUTER_API_KEY` | OpenRouter API key | empty |
| `OPENROUTER_MODEL` | OpenRouter model | `openai/gpt-4o-mini` |
| `GROQ_API_KEY` | Groq API key | empty |
| `GROQ_MODEL` | Groq model | `llama-3.3-70b-versatile` |
| `VISION_ENABLED` | Allow screen capture when asked | `true` |
| `VISION_PROVIDER` | Endpoint name used for screen vision | `Groq` |
| `VISION_MODEL` | Vision model | `qwen/qwen3.8-27b` |
| `VISION_MAX_WIDTH` | Maximum screenshot dimension in pixels | `1600` |
| `VISION_JPEG_QUALITY` | Screenshot JPEG quality | `82` |
| `SEARCH_ENABLED` | Allow web and YouTube searches | `true` |
| `SEARCH_MAX_RESULTS` | Results passed to the model per search | `5` |
| `SEARCH_REGION` | Search region, for example `ru-ru` | `ru-ru` |
| `SEARCH_SAFESEARCH` | Safe search: `on`, `moderate`, or `off` | `moderate` |
| `SEARCH_TIMEOUT` | Search request timeout in seconds | `6` |
| `SEARCH_PAGE_TIMEOUT` | Timeout for reading a result page | `8` |
| `SEARCH_GOOGLE` | Try Google as a last-resort source | `true` |
| `SEARCH_YOUTUBE` | Enable YouTube video search | `true` |
| `AI_TIMEOUT` | Request timeout in seconds | `120` |
| `AI_HISTORY_LIMIT` | Number of messages kept in history | `20` |
| `HISTORY_KEEP_RECENT` | Recent messages kept verbatim when compacting | `6` |
| `SETTINGS_FILE` | Path to the settings file | `settings.json` |
| `MEMORY_FILE` | Path to the memory file | `memory.json` |
| `HISTORY_FILE` | Path to the history file | `history.json` |
| `OUTFIT_FILE` | Path to the saved outfit | `outfit.json` |
| `TTS_ENABLED` | Enable spoken replies | `true` |
| `TTS_PROVIDER` | TTS backend (`milka` or `groq`) | `milka` |
| `MILKY_TTS_URL` | Milka TTS server address | `http://192.168.1.100:8765` |
| `MILKY_TTS_VOICE` | Milka TTS voice | `sveta` |
| `MILKY_TTS_SPEED` | Milka TTS speed | `1.0` |
| `GROQ_TTS_MODEL` | Groq TTS model | `canopylabs/orpheus-v1-english` |
| `GROQ_TTS_VOICE` | Groq TTS voice | `hannah` |
| `DRAWING_PROVIDER` | Drawing engine (`model` or `cloudflare`) | auto: `cloudflare` when credentials exist, otherwise `model` |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID | empty |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token with Workers AI access | empty |
| `CLOUDFLARE_IMAGE_MODEL` | Cloudflare image model | `@cf/black-forest-labs/flux-1-schnell` |
| `CLOUDFLARE_IMAGE_STEPS` | FLUX sampling steps (1–8) | `4` |
| `CLOUDFLARE_IMAGE_TIMEOUT` | Image request timeout in seconds | `120` |
| `LIFE_ENABLED` | Let Milky act on her own between conversations | `true` |
| `LIFE_SUGGEST_OUTFIT` | Allow spontaneous outfit suggestions | `true` |
| `LIFE_DRAW` | Allow spontaneous drawings | `true` |
| `LIFE_MIN_MINUTES` | Shortest life-cycle interval in minutes | `10` |
| `LIFE_MAX_MINUTES` | Longest life-cycle interval in minutes | `30` |
| `MILKY_ADDON_DEBUG` | Show full addon tracebacks in the console | empty |

## Project Structure

```text
milky/
├── main.py                  # entry point; puts app/ on sys.path and starts the UI
├── app/
│   ├── application.py       # window, animations, tray, and app startup
│   ├── ai_client.py         # model requests, memory, history and search tools
│   ├── addon_api.py         # public @tool decorator and addon context
│   ├── addon_manager.py     # skill discovery, loading and tool execution
│   ├── github_skills.py     # install skills from public GitHub repositories
│   ├── drawing_skill.py     # SVG drawing quality guide
│   ├── settings_dialog.py   # endpoint, voice, drawing, outfit and skill settings
│   ├── settings_store.py    # loading and saving settings.json
│   ├── image_service.py     # Cloudflare Workers AI image generation
│   ├── screen_vision.py     # screen capture and JPEG encoding for vision
│   ├── outfit_store.py      # loading and saving outfit.json
│   ├── clothing_art.py      # clothing prompt guide and fallback overlays
│   ├── clothing_overlay.py  # clothing validation and face overlay rendering
│   ├── autostart.py         # system autostart management
│   ├── runtime.py           # source/frozen resource and data paths
│   ├── tts.py               # Milka/Groq speech synthesis and playback
│   ├── svg_art.py           # detailed fallback SVG illustrations
│   └── web_search.py        # web/YouTube search and page excerpt reader
├── assets/
│   ├── gifs/                # Milky animations
│   ├── milka_idle.svg       # application icon
│   └── milka_idle.ico       # Windows executable icon
├── scripts/
│   ├── install.sh           # Linux installer
│   └── install.ps1          # Windows installer
├── addons/                  # installed skills (created automatically)
├── .github/workflows/       # GitHub Actions build workflow
├── .env.example             # environment variable template
├── .gitattributes           # line ending and binary file rules
├── requirements.txt         # core dependencies
├── requirements-search.txt  # compatibility alias for requirements.txt
└── LICENSE
```

Runtime files (`.env`, `settings.json`, `memory.json`, `history.json`, `outfit.json`, `svg_drawings/`) stay next to `main.py`, so an installed or portable build keeps its data in one place.

## Limitations

- Web search depends on public search providers and page availability. DuckDuckGo may occasionally rate-limit requests; Milky retries through an alternate reader and skips pages it cannot load. Results and page excerpts are untrusted web data.
- Drawing quality depends on the selected engine and model. Cloudflare uses FLUX.1 schnell and returns a 1024×1024 JPEG; it is text-to-image, so it cannot exactly reproduce Milky's official line-art portrait. The SVG path uses the full drawing skill in `app/drawing_skill.py`: composition, anatomy recipes, lighting, SVG technique and a finishing checklist. The model creates its own SVG without subject templates. If the first SVG illustration is too bare, Milky asks for one fresh, more detailed drawing; the built-in illustrations are only a last-resort fallback when the provider returns no valid SVG. Drawing-only requests never create clothing overlays.
- Clothing quality depends on the selected model. Common accessories (hat, crown, glasses, mask, scarf, necklace, bow and earrings) have built-in fallbacks. An overlay with a background or face is rejected, neck items must sit below the smile, and face items must keep the eyes visible.
- TTS needs a running Milka TTS server or a valid Groq API key.
- Screen vision needs a vision-capable model and captures the whole screen. The description comes from the selected vision model, so fine details it misses will not be available to the chat model. On Wayland, the desktop screenshot portal must be available and screen-capture permission must be granted.
- Cloud providers require a working API key and internet access. Cloudflare image generation also needs its account ID and a Workers AI token; the free daily Neuron limit can be exhausted by frequent drawing.
- Response speed depends on the selected model and hardware. Local models on a weak CPU may answer slowly.

## Pre-Commit Checks

```bash
python -m compileall -q main.py app
bash -n scripts/install.sh
```

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE) for details.
