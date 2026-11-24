import json
import os
from pathlib import Path

APP_NAME = "R1999Translator"


def data_dir():
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    path = root / APP_NAME / "engine"
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path, data, indent=None):
    try:
        Path(path).write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")
        return True
    except OSError:
        return False


def clone(data):
    return json.loads(json.dumps(data))
