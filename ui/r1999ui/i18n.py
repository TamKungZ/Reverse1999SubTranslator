from pathlib import Path

from .storage import data_dir, read_json

BUILTIN = Path(__file__).parent / "locales"


class Locale:
    def __init__(self, code="en", usable=lambda script: True):
        self.fallback = read_json(BUILTIN / "en.json", {})
        self.usable = usable
        self.data = {}
        self.code = "en"
        self.set(code)

    def _fits(self, data):
        script = data.get("_script")
        return not script or self.usable(script)

    @staticmethod
    def folders():
        return [BUILTIN, data_dir() / "locales"]

    def available(self):
        found = {}
        for folder in self.folders():
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                data = read_json(path, {}) or {}
                if data.get("_name") and self._fits(data):
                    found[path.stem] = data["_name"]
        return found

    def set(self, code):
        data = {}
        for folder in self.folders():
            data.update(read_json(folder / (code + ".json"), {}) or {})
        if not data or not self._fits(data):
            code, data = "en", {}
        self.code, self.data = code, data

    def t(self, key, /, **values):
        text = self.data.get(key) or self.fallback.get(key) or key
        try:
            return text.format(**values) if values else text
        except (KeyError, IndexError, ValueError):
            return text
