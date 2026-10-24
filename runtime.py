import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))

if FROZEN:
    EXECUTABLE_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(
        getattr(sys, "_MEIPASS", EXECUTABLE_DIR)
    ).resolve()
else:
    EXECUTABLE_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = EXECUTABLE_DIR

DATA_DIR = EXECUTABLE_DIR


def resource_path(relative):
    path = Path(relative)
    return path if path.is_absolute() else RESOURCE_DIR / path


def data_path(relative):
    path = Path(relative)
    return path if path.is_absolute() else DATA_DIR / path
