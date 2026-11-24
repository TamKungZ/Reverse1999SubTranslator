import json
import os
import threading
from pathlib import Path

APP_NAME = "R1999Translator"

LANGUAGES = {
    "th": {"name": "ไทย", "nllb": "tha_Thai", "join": " ", "native_names": True},
    "ja": {"name": "日本語", "nllb": "jpn_Jpan", "join": "", "native_names": True},
    "zh": {"name": "中文", "nllb": "zho_Hans", "join": "", "native_names": True},
    "ko": {"name": "한국어", "nllb": "kor_Hang", "join": " ", "native_names": True},
    "id": {"name": "Indonesia", "nllb": "ind_Latn", "join": " ", "native_names": False},
    "vi": {"name": "Tiếng Việt", "nllb": "vie_Latn", "join": " ", "native_names": False},
}

DEFAULTS = {
    "mode": "sentence",
    "timing": "wait",
    "target_lang": "th",
    "name_style": "native",
    "word_level": "basic",
    "stable_ms": 450,
    "live_interval_ms": 300,
    "hide_ms": 450,
    "model_repo": "skywood/nllb-200-distilled-600M-ct2-int8",
    "threads": 4,
    "device": "cpu",
    "region": [0.19, 0.78, 0.90, 1.0],
    "name_band": [0.80, 0.86],
}

CHOICES = {
    "mode": ("sentence", "word"),
    "timing": ("wait", "live"),
    "target_lang": tuple(LANGUAGES),
    "name_style": ("native", "original", "both"),
    "word_level": ("off", "basic", "medium"),
}

RANGES = {
    "stable_ms": (150, 2000),
    "live_interval_ms": (120, 2000),
    "hide_ms": (150, 3000),
    "threads": (1, 32),
}


def data_dir():
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    path = root / APP_NAME / "engine"
    path.mkdir(parents=True, exist_ok=True)
    return path


class EngineConfig:
    def __init__(self, path=None):
        self.path = Path(path) if path else data_dir() / "config.json"
        self.data = json.loads(json.dumps(DEFAULTS))
        self._lock = threading.Lock()
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            self.update(stored, save=False)
        except (OSError, ValueError):
            pass

    def __getitem__(self, key):
        return self.data[key]

    def snapshot(self):
        with self._lock:
            return json.loads(json.dumps(self.data))

    def update(self, values, save=True):
        changed = {}
        with self._lock:
            for key, value in values.items():
                if key not in DEFAULTS:
                    continue
                if key in CHOICES and value not in CHOICES[key]:
                    continue
                if key in RANGES:
                    if not isinstance(value, (int, float)):
                        continue
                    lo, hi = RANGES[key]
                    value = int(min(hi, max(lo, value)))
                if key in ("region", "name_band"):
                    if not (isinstance(value, list) and len(value) == (4 if key == "region" else 2)):
                        continue
                    value = [float(v) for v in value]
                if key in ("model_repo", "device") and not isinstance(value, str):
                    continue
                if self.data[key] != value:
                    self.data[key] = value
                    changed[key] = value
        if changed and save:
            self.save()
        return changed

    def save(self):
        try:
            self.path.write_text(
                json.dumps(self.snapshot(), indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass
