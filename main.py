"""Milky entry point.

The application lives in ``app/``. Adding that folder to ``sys.path`` keeps
Milky's modules and addon imports (``from addon_api import tool``) working
from source and from a PyInstaller build.
"""

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from application import run

if __name__ == "__main__":
    run()
