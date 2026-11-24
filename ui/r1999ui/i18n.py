import json
from pathlib import Path

from .settings import data_dir

BUILTIN = Path(__file__).parent / "locales"


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class Locale:
    def __init__(self, code="en"):
        self.fallback = _read(BUILTIN / "en.json")
        self.data = {}
        self.code = "en"
        self.set(code)

    @staticmethod
    def folders():
        return [BUILTIN, data_dir() / "locales"]

    def available(self):
        found = {}
        for folder in self.folders():
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                name = _read(path).get("_name")
                if name:
                    found[path.stem] = name
        return found

    def set(self, code):
        data = {}
        for folder in self.folders():
            data.update(_read(folder / (code + ".json")))
        if not data:
            code, data = "en", {}
        self.code, self.data = code, data

    def t(self, key, **values):
        text = self.data.get(key) or self.fallback.get(key) or key
        try:
            return text.format(**values) if values else text
        except (KeyError, IndexError, ValueError):
            return text
