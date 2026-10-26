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
- Detailed SVG drawings: when asked to draw something, Milky saves a polished SVG illustration to `svg_drawings/`, plays a drawing animation, and shows a notification above her face.
- Official self-portrait: ask her to draw herself, a selfie or her portrait and she uses her line-art artwork.
- SVG selfie and drawing gallery from the tray menu, with sharp click-to-enlarge previews.
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

The built app is portable: extract the archive to a writable folder and run `Milky.exe`. Place `.env` and the generated `settings.json`, `memory.json`, and `history.json` next to the executable. The executable is unsigned, so Windows SmartScreen may show a warning.

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

## Running

```bash
python main.py
```

## Controls

- Left click — open the input field.
- Drag — move the pet.
- Enter — send a message.
- Esc — close the input field.
- Right click — open the context menu (Settings, Selfie, Show SVG gallery, Quit).
- Double-click the tray icon — show or hide the window.

Ask Milky to **draw a cat**, **draw a sun**, **нарисуй котика** or **нарисуй цветок**. Milky keeps her face animation, plays `milka_drawing.gif` and shows a **«Новый рисунок в галерее!»** notification above her. The drawing is saved in `svg_drawings/`; click the notification or open the tray menu → **Show SVG gallery** to browse sharp previews and click any drawing to enlarge it.

Ask **нарисуй себя**, **селфи**, **автопортрет** or **draw yourself** and she will use her official line-art self-portrait instead of generating a new one.

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
| `AI_TIMEOUT` | Request timeout in seconds | `120` |
| `AI_HISTORY_LIMIT` | Number of messages kept in history | `20` |
| `SETTINGS_FILE` | Path to the settings file | `settings.json` |
| `MEMORY_FILE` | Path to the memory file | `memory.json` |
| `HISTORY_FILE` | Path to the history file | `history.json` |
| `TTS_ENABLED` | Enable spoken replies | `true` |
| `TTS_PROVIDER` | TTS backend (`milka` or `groq`) | `milka` |
| `MILKY_TTS_URL` | Milka TTS server address | `http://192.168.1.100:8765` |
| `MILKY_TTS_VOICE` | Milka TTS voice | `sveta` |
| `MILKY_TTS_SPEED` | Milka TTS speed | `1.0` |
| `GROQ_TTS_MODEL` | Groq TTS model | `canopylabs/orpheus-v1-english` |
| `GROQ_TTS_VOICE` | Groq TTS voice | `hannah` |

## Project Structure

```text
milky/
├── main.py                 # window, animations, tray, and app startup
├── ai_client.py            # model requests, memory, and history
├── settings_dialog.py      # endpoint settings window
├── settings_store.py       # loading and saving settings.json
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
- Drawing quality depends on the selected model. If the model does not return SVG, Milky falls back to her own detailed illustrations.
- TTS needs a running Milka TTS server or a valid Groq API key.
- Cloud providers require a working API key and internet access.
- Response speed depends on the selected model and hardware. Local models on a weak CPU may answer slowly.

## Pre-Commit Checks

```bash
python -m py_compile ai_client.py autostart.py main.py runtime.py settings_dialog.py settings_store.py svg_art.py tts.py web_search.py
bash -n install.sh
```

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE) for details.
