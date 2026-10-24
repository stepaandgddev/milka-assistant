import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

APP_NAME = "Milky"
APP_ID = "milky"
BASE_DIR = Path(__file__).resolve().parent


def _config_home():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def _windows_startup_dir():
    appdata = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
    return (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def autostart_paths():
    if sys.platform.startswith("linux"):
        return [_config_home() / "autostart" / f"{APP_ID}.desktop"]
    if sys.platform == "win32":
        startup = _windows_startup_dir()
        return [
            startup / f"{APP_ID}-autostart.cmd",
            startup / f"{APP_NAME}.lnk",
        ]
    if sys.platform == "darwin":
        return [
            Path.home()
            / "Library"
            / "LaunchAgents"
            / f"com.{APP_ID}.pet.plist"
        ]
    return []


def autostart_path():
    paths = autostart_paths()
    return paths[0] if paths else None


def autostart_supported():
    return bool(autostart_paths())


def autostart_enabled():
    return any(path.exists() for path in autostart_paths())


def _desktop_quote(value):
    value = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'


def _command():
    executable = Path(sys.executable).resolve()
    if sys.platform == "win32":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            executable = pythonw
    return [str(executable), str(BASE_DIR / "main.py")]


def _desktop_entry():
    python, main = _command()
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={APP_NAME}",
            "Comment=Animated AI pet",
            f"Exec={_desktop_quote(python)} {_desktop_quote(main)}",
            f"Path={BASE_DIR}",
            f"Icon={BASE_DIR / 'milka_idle.svg'}",
            "Terminal=false",
            "X-GNOME-Autostart-enabled=true",
            "",
        ]
    )


def _windows_command_file():
    python, main = _command()
    return "\n".join(
        [
            "@echo off",
            f'cd /d "{BASE_DIR}"',
            f'start "" "{python}" "{main}"',
            "",
        ]
    )


def _macos_plist():
    python, main = _command()
    return {
        "Label": f"com.{APP_ID}.pet",
        "ProgramArguments": [python, main],
        "WorkingDirectory": str(BASE_DIR),
        "RunAtLoad": True,
        "KeepAlive": False,
    }


def enable_autostart():
    paths = autostart_paths()
    if not paths:
        raise RuntimeError("Autostart is not supported on this system")
    path = paths[0]
    path.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform.startswith("linux"):
        path.write_text(_desktop_entry(), encoding="utf-8")
        path.chmod(0o644)
    elif sys.platform == "win32":
        path.write_text(_windows_command_file(), encoding="utf-8")
    elif sys.platform == "darwin":
        with path.open("wb") as file:
            plistlib.dump(_macos_plist(), file)
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", str(path)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return path


def disable_autostart():
    for path in autostart_paths():
        if path.exists():
            path.unlink()
    if sys.platform == "darwin":
        uid = os.getuid()
        for path in autostart_paths():
            subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}", str(path)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def set_autostart(enabled):
    if enabled:
        return enable_autostart()
    disable_autostart()
    return None


def _main():
    parser = argparse.ArgumentParser(
        description="Manage Milky autostart"
    )
    parser.add_argument(
        "action",
        choices=("enable", "disable", "status"),
        help="enable, disable, or check autostart",
    )
    args = parser.parse_args()

    if args.action == "enable":
        path = enable_autostart()
        print(f"Autostart enabled: {path}")
    elif args.action == "disable":
        disable_autostart()
        print("Autostart disabled")
    elif not autostart_supported():
        print("Autostart is not supported")
    elif autostart_enabled():
        print("Autostart enabled")
    else:
        print("Autostart disabled")


if __name__ == "__main__":
    _main()
