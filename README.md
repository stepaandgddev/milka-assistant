# Milky

An animated AI desktop pet: a transparent window, emotion animations, user memory, and support for local and cloud models.

![Milky](gifs/milka_idle.gif)

## Features

- Transparent always-on-top window.
- Animations for different emotions: `idle`, `listening`, `thinking`, `speaking`, `happy`, `sad`, `confused`, `sleepy`, `passive`, `music`.
- Short, natural replies from Milky. The user can write in any language, and Milky can answer in whatever language and style feels natural to her.
- Memory of user facts in `memory.json`.
- Conversation history in `history.json`.
- Support for Ollama, OpenRouter, Groq, and other OpenAI-compatible APIs.
- Provider and model switching in the settings window.
- Request caching for OpenRouter.
- Opening links when the user explicitly asks.
- Detailed drawings: when asked to draw something, Milky saves the illustration to `svg_drawings/`, plays a drawing animation, and shows a notification above her face. With Cloudflare Workers AI configured, she uses FLUX.1 schnell for a polished raster JPEG; otherwise she uses the built-in SVG path. The SVG path includes a quality checklist for anatomy, shading, a background and highlights, and retries a bare illustration with a fresh, template-free prompt. If Cloudflare is unavailable, the app falls back to SVG automatically.
- Official self-portrait: plain selfie requests use her line-art portrait; scene requests such as **нарисуй себя в космосе** draw the full scene.
- AI-generated clothing and accessories: ask her to put on a hat, glasses, scarf, crown or other item and she generates a transparent SVG overlay. Body, neck and head items are layered behind her face line art so clothing cannot hide her eyes or smile; glasses and masks stay in front and are checked for eye clearance. A drawing request never adds clothing on its own. The outfit persists across restarts and can be managed in **Settings → Outfit**.
- Drawing gallery from the tray menu, with click-to-enlarge previews for SVG, PNG, JPEG and WebP drawings and a Delete button for each one. The gallery keeps existing SVG drawings and new Cloudflare raster drawings side by side.
- Screen vision: ask **что на экране?**, **что ты видишь?** or **what do you see?** and Milky captures the current screen, describes it with a vision model, and answers with her normal chat model. Groq's `qwen/qwen3.8-27b` works out of the box; local Ollama vision models are supported too.
- Text-to-speech replies through a Milka TTS server or Groq, with configurable endpoint and voice.
- System tray icon and context menu.
- Linux and Windows installers with optional autostart.
- GitHub Actions build for a standalone Windows executable.

## Requirements

- Python 3.10–3.15 (tested on Python 3.14).
- Linux, Windows, or macOS.
- Ollama with a tool-calling model, or an API key for an OpenAI-compatible service.

## Quick Installation

Run the installer from the project root — the folder that contains `main.py` and `requirements.txt`.

### Linux

```bash
chmod +x install.sh
./install.sh
```

The installer creates a virtual environment, installs dependencies, adds an application menu shortcut, and installs the `milky` command into `~/.local/bin`.

Enable autostart immediately:

```bash
./install.sh --autostart
```

Or disable it:

```bash
./install.sh --no-autostart
```

Uninstall:

```bash
./install.sh --uninstall
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Enable autostart:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Autostart
```

Uninstall:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall
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

To use the experimental `web_search.py` module, install its dependencies separately:

```bash
pip install -r requirements-search.txt
```

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

Milky can look at the current screen when you ask. The screenshot is captured only for that request, sent to the selected vision endpoint, and is not written to disk.

1. Open **Settings → Screen vision**.
2. Keep **Let Milky look at the screen when asked** enabled.
3. Select the **Groq** endpoint.
4. Set **Vision model** to `qwen/qwen3.8-27b`.

Groq lists this model with image input support, and it can be used even when the active chat model is text-only such as `openai/gpt-oss-20b`. The vision model produces a description first; Milky's active chat model then answers with her normal personality, emotions, tools and memory.

Ask **что на экране?**, **что ты видишь?**, **посмотри на экран**, **what do you see?** or use **Look at screen** in the right-click/tray menu.

For a local vision model with Ollama:

```bash
ollama pull qwen3-vl:8b
```

Then select the **Ollama** endpoint in **Settings → Screen vision** and set the vision model to `qwen3-vl:8b`. Other Ollama vision models can be used by entering their model name.

Environment defaults:

```dotenv
VISION_ENABLED=true
VISION_PROVIDER=Groq
VISION_MODEL=qwen/qwen3.8-27b
VISION_MAX_WIDTH=1600
VISION_JPEG_QUALITY=82
```

If the screen is not captured on Linux, try an X11 or XWayland session. On Wayland, desktop screenshot permission can also block capture depending on the compositor.

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

## Autostart

Autostart is controlled by the **Launch Milky at login** checkbox in the app settings.

The autostart entry is created at:

- Linux: `~/.config/autostart/milky.desktop`.
- Windows: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\milky-autostart.cmd`.
- macOS: `~/Library/LaunchAgents/com.milky.pet.plist`.

When installing with `install.sh` or `install.ps1`, autostart can be enabled immediately or left disabled.

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
| `AI_TIMEOUT` | Request timeout in seconds | `120` |
| `AI_HISTORY_LIMIT` | Number of messages kept in history | `20` |
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

## Project Structure

```text
milky/
├── main.py                 # window, animations, tray, and app startup
├── ai_client.py            # model requests, memory, and history
├── drawing_skill.py        # SVG drawing quality guide
├── settings_dialog.py      # endpoint, voice, drawing and outfit settings
├── settings_store.py       # loading and saving settings.json
├── image_service.py        # Cloudflare Workers AI image generation
├── screen_vision.py        # screen capture and JPEG encoding for vision
├── outfit_store.py         # loading and saving outfit.json
├── clothing_art.py         # clothing prompt guide and fallback overlays
├── clothing_overlay.py     # clothing validation and face overlay rendering
├── autostart.py            # system autostart management
├── runtime.py              # source/frozen resource and data paths
├── tts.py                  # Milka/Groq speech synthesis and playback
├── svg_art.py              # detailed fallback SVG illustrations
├── web_search.py           # experimental search module
├── install.sh              # Linux installer
├── install.ps1             # Windows installer
├── .github/workflows/      # GitHub Actions build workflow
├── gifs/                   # Milky animations
├── milka_idle.svg          # application icon
├── milka_idle.ico          # Windows executable icon
├── .env.example            # environment variable template
├── .gitattributes          # line ending and binary file rules
├── requirements.txt        # core dependencies
├── requirements-search.txt # experimental search dependencies
└── LICENSE
```

## Limitations

- Built-in web search is not connected to the interface yet. `web_search.py` remains an experimental module.
- Drawing quality depends on the selected engine and model. Cloudflare uses FLUX.1 schnell and returns a 1024×1024 JPEG; it is text-to-image, so it cannot exactly reproduce Milky's official line-art portrait. The SVG path uses the full drawing skill in `drawing_skill.py`: composition, anatomy recipes, lighting, SVG technique and a finishing checklist. The model creates its own SVG without subject templates. If the first SVG illustration is too bare, Milky asks for one fresh, more detailed drawing; the built-in illustrations are only a last-resort fallback when the provider returns no valid SVG. Drawing-only requests never create clothing overlays.
- Clothing quality depends on the selected model. Common accessories (hat, crown, glasses, mask, scarf, necklace, bow and earrings) have built-in fallbacks. An overlay with a background or face is rejected, neck items must sit below the smile, and face items must keep the eyes visible.
- TTS needs a running Milka TTS server or a valid Groq API key.
- Screen vision needs a vision-capable model and captures only the screen under the mouse cursor. The description comes from the selected vision model, so fine details it misses will not be available to the chat model. On Wayland, screenshot permission can prevent capture.
- Cloud providers require a working API key and internet access. Cloudflare image generation also needs its account ID and a Workers AI token; the free daily Neuron limit can be exhausted by frequent drawing.
- Response speed depends on the selected model and hardware. Local models on a weak CPU may answer slowly.

## Pre-Commit Checks

```bash
python -m py_compile ai_client.py autostart.py clothing_art.py clothing_overlay.py drawing_skill.py image_service.py main.py outfit_store.py runtime.py screen_vision.py settings_dialog.py settings_store.py svg_art.py tts.py web_search.py
bash -n install.sh
```

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE) for details.
