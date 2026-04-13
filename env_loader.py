from __future__ import annotations

import os
from pathlib import Path


ENV_PATH = Path(__file__).resolve().parent / ".env"
_LOADED = False


def load_env_file() -> None:
    global _LOADED
    if _LOADED or not ENV_PATH.exists():
        _LOADED = True
        return
    for raw_line in ENV_PATH.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    _LOADED = True
