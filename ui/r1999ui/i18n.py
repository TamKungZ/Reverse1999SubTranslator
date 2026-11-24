from pathlib import Path

from .storage import data_dir, read_json

BUILTIN = Path(__file__).parent / "locales"


class Locale:
    def __init__(self, code="en"):
        self.fallback = read_json(BUILTIN / "en.json", {})
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
                name = (read_json(path, {}) or {}).get("_name")
                if name:
                    found[path.stem] = name
        return found

    def set(self, code):
        data = {}
        for folder in self.folders():
            data.update(read_json(folder / (code + ".json"), {}) or {})
        if not data:
            code, data = "en", {}
        self.code, self.data = code, data

    def t(self, key, /, **values):
        text = self.data.get(key) or self.fallback.get(key) or key
        try:
            return text.format(**values) if values else text
        except (KeyError, IndexError, ValueError):
            return text
