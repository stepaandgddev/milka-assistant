#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Milky"
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${MILKY_INSTALL_DIR:-$HOME/.local/share/milky}"
BIN_DIR="${MILKY_BIN_DIR:-$HOME/.local/bin}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
APPLICATIONS_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
ICON_FILE="$ICON_DIR/milky.svg"
DESKTOP_FILE="$APPLICATIONS_DIR/milky.desktop"
AUTOSTART_FILE="$CONFIG_HOME/autostart/milky.desktop"
PYTHON_BIN="${PYTHON_BIN:-python3}"

AUTOSTART_MODE="ask"
ASSUME_YES=0
UNINSTALL=0

usage() {
    cat <<EOF
$APP_NAME installer

Usage:
  ./install.sh [--autostart|--no-autostart] [--install-dir PATH] [--yes]
  ./install.sh --uninstall [--yes]

Options:
  --autostart      enable autostart
  --no-autostart   disable autostart
  --install-dir    install directory (default: ~/.local/share/milky)
  --yes, -y        do not ask questions
  --uninstall      remove the application
  --help, -h       show this help
EOF
}

desktop_quote() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '"%s"' "$value"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --autostart)
            AUTOSTART_MODE="enable"
            ;;
        --no-autostart)
            AUTOSTART_MODE="disable"
            ;;
        --install-dir)
            if [ $# -lt 2 ]; then
                echo "The --install-dir option requires a path" >&2
                exit 1
            fi
            INSTALL_DIR="$2"
            shift
            ;;
        --install-dir=*)
            INSTALL_DIR="${1#*=}"
            ;;
        --yes|-y)
            ASSUME_YES=1
            ;;
        --uninstall)
            UNINSTALL=1
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
    shift
done

case "$INSTALL_DIR" in
    ""|"/"|"$HOME"|"$HOME/"|"$DATA_HOME"|"$DATA_HOME/"|"$HOME/.local"|"$HOME/.config")
        echo "Invalid install directory: $INSTALL_DIR" >&2
        exit 1
        ;;
esac

if [ "$UNINSTALL" -eq 1 ]; then
    if [ "$ASSUME_YES" -eq 0 ]; then
        if [ ! -t 0 ]; then
            echo "Use --yes to uninstall without confirmation" >&2
            exit 1
        fi
        read -r -p "Remove $APP_NAME from $INSTALL_DIR? [y/N] " answer || true
        case "${answer:-}" in
            y|Y|yes|YES) ;;
            *) echo "Cancelled"; exit 0 ;;
        esac
    fi
    if [ -x "$INSTALL_DIR/venv/bin/python" ] && [ -f "$INSTALL_DIR/autostart.py" ]; then
        "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/autostart.py" disable >/dev/null 2>&1 || true
    fi
    rm -f -- "$BIN_DIR/milky" "$DESKTOP_FILE" "$AUTOSTART_FILE" "$ICON_FILE"
    rm -rf -- "$INSTALL_DIR"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
    fi
    echo "$APP_NAME has been removed"
    exit 0
fi

REQUIRED_FILES=(
    main.py
    ai_client.py
    settings_dialog.py
    settings_store.py
    autostart.py
    runtime.py
    tts.py
    svg_art.py
    requirements.txt
    milka_idle.svg
)

if [ "$SOURCE_DIR" = "$INSTALL_DIR" ]; then
    SOURCE_CHECK_DIR="$INSTALL_DIR"
else
    SOURCE_CHECK_DIR="$SOURCE_DIR"
fi

MISSING=()
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$SOURCE_CHECK_DIR/$file" ]; then
        MISSING+=("$file")
    fi
done

if [ ! -d "$SOURCE_CHECK_DIR/gifs" ]; then
    MISSING+=("gifs/")
fi

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "Cannot install: missing required files in $SOURCE_CHECK_DIR:" >&2
    printf '  - %s\n' "${MISSING[@]}" >&2
    echo "Run install.sh from the project root (the folder that contains main.py and requirements.txt)." >&2
    exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python $PYTHON_BIN was not found. Install Python 3.10+." >&2
    exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)' >/dev/null 2>&1; then
    echo "Python 3.10 or newer is required." >&2
    exit 1
fi

if [ "$AUTOSTART_MODE" = "ask" ]; then
    if [ ! -t 0 ]; then
        AUTOSTART_MODE="keep"
    elif [ -f "$AUTOSTART_FILE" ]; then
        read -r -p "Autostart is already enabled. Keep it? [Y/n] " answer || true
        case "${answer:-}" in
            n|N|no|NO) AUTOSTART_MODE="disable" ;;
            *) AUTOSTART_MODE="keep" ;;
        esac
    else
        read -r -p "Add $APP_NAME to autostart? [y/N] " answer || true
        case "${answer:-}" in
            y|Y|yes|YES) AUTOSTART_MODE="enable" ;;
            *) AUTOSTART_MODE="keep" ;;
        esac
    fi
fi

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$APPLICATIONS_DIR" "$ICON_DIR"

if [ "$SOURCE_DIR" != "$INSTALL_DIR" ]; then
    for file in \
        main.py ai_client.py settings_dialog.py settings_store.py \
        autostart.py runtime.py tts.py svg_art.py web_search.py \
        milka_idle.svg requirements.txt \
        requirements-search.txt README.md LICENSE .env.example
    do
        if [ -f "$SOURCE_DIR/$file" ]; then
            cp -f "$SOURCE_DIR/$file" "$INSTALL_DIR/"
        fi
    done
    if [ -d "$SOURCE_DIR/gifs" ]; then
        mkdir -p "$INSTALL_DIR/gifs"
        cp -R "$SOURCE_DIR/gifs/." "$INSTALL_DIR/gifs/"
    fi
fi

if [ ! -f "$INSTALL_DIR/.env" ] && [ -f "$INSTALL_DIR/.env.example" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
fi

if [ -f "$INSTALL_DIR/milka_idle.svg" ]; then
    cp -f "$INSTALL_DIR/milka_idle.svg" "$ICON_FILE"
fi

if [ ! -x "$INSTALL_DIR/venv/bin/python" ]; then
    echo "Creating virtual environment..."
    "$PYTHON_BIN" -m venv "$INSTALL_DIR/venv"
fi

echo "Installing dependencies..."
"$INSTALL_DIR/venv/bin/python" -m pip install --disable-pip-version-check -r "$INSTALL_DIR/requirements.txt"

{
    printf '%s\n' '#!/usr/bin/env bash'
    printf 'cd %q || exit 1\n' "$INSTALL_DIR"
    printf 'exec %q %q "$@"\n' "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/main.py"
} > "$BIN_DIR/milky"
chmod 755 "$BIN_DIR/milky"

{
    printf '%s\n' '[Desktop Entry]'
    printf '%s\n' 'Type=Application'
    printf 'Name=%s\n' "$APP_NAME"
    printf '%s\n' 'Comment=Animated AI pet'
    printf 'Exec=%s\n' "$(desktop_quote "$BIN_DIR/milky")"
    printf 'Path=%s\n' "$INSTALL_DIR"
    printf 'Icon=milky\n'
    printf '%s\n' 'Terminal=false'
    printf '%s\n' 'Categories=Utility;'
    printf '%s\n' 'StartupNotify=false'
} > "$DESKTOP_FILE"
chmod 644 "$DESKTOP_FILE"

if [ "$AUTOSTART_MODE" = "enable" ]; then
    "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/autostart.py" enable
elif [ "$AUTOSTART_MODE" = "disable" ]; then
    "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/autostart.py" disable
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

echo
echo "$APP_NAME has been installed to $INSTALL_DIR"
echo "Run from a terminal: $BIN_DIR/milky"
echo "The app is also available in the application menu."

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo
        echo "Add $BIN_DIR to PATH so the milky command works from anywhere."
        ;;
esac

if [ "$AUTOSTART_MODE" = "enable" ]; then
    echo "Autostart enabled."
elif [ "$AUTOSTART_MODE" = "disable" ]; then
    echo "Autostart disabled."
fi
