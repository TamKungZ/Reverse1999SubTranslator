import threading
from pathlib import Path

from .languages import LANGUAGES
from .storage import clone, data_dir, read_json, write_json

DEFAULTS = {
    "mode": "sentence",
    "timing": "wait",
    "translator": "nllb",
    "target_lang": "th",
    "name_style": "native",
    "word_level": "basic",
    "stable_ms": 450,
    "live_interval_ms": 300,
    "hide_ms": 450,
    "model_repo": "skywood/nllb-200-distilled-600M-ct2-int8",
    "threads": 0,
    "beam_size": 2,
    "device": "cpu",
    "region": [0.08, 0.78, 0.90, 1.0],
    "name_band": [0.80, 0.86],
}

CHOICES = {
    "mode": ("sentence", "word"),
    "timing": ("wait", "live"),
    "translator": ("nllb", "argos"),
    "target_lang": tuple(LANGUAGES),
    "name_style": ("native", "original", "both"),
    "word_level": ("off", "basic", "medium"),
}

RANGES = {
    "stable_ms": (150, 2000),
    "live_interval_ms": (120, 2000),
    "hide_ms": (150, 3000),
    "threads": (0, 32),
    "beam_size": (1, 5),
}

LEGACY_DEFAULTS = {"region": [0.19, 0.78, 0.9, 1.0], "threads": 4}   # saved by earlier versions, now replaced by better defaults
BOXES = {"region": 4, "name_band": 2}
STRINGS = ("model_repo", "device")
REJECT = object()


def coerce(key, value):
    if key in CHOICES:
        return value if value in CHOICES[key] else REJECT
    if key in RANGES:
        if not isinstance(value, (int, float)):
            return REJECT
        lo, hi = RANGES[key]
        return int(min(hi, max(lo, value)))
    if key in BOXES:
        if not (isinstance(value, list) and len(value) == BOXES[key]):
            return REJECT
        return [float(v) for v in value]
    if key in STRINGS and not isinstance(value, str):
        return REJECT
    return value


class EngineConfig:
    def __init__(self, path=None):
        self.path = Path(path) if path else data_dir() / "config.json"
        self.data = clone(DEFAULTS)
        self._lock = threading.Lock()
        stored = read_json(self.path, {})
        for key, old in LEGACY_DEFAULTS.items():
            if stored.get(key) == old:
                del stored[key]
        self.update(stored, save=False)

    def __getitem__(self, key):
        return self.data[key]

    def snapshot(self):
        with self._lock:
            return clone(self.data)

    def update(self, values, save=True):
        changed = {}
        with self._lock:
            for key, raw in values.items():
                if key not in DEFAULTS:
                    continue
                value = coerce(key, raw)
                if value is REJECT or self.data[key] == value:
                    continue
                self.data[key] = value
                changed[key] = value
        if changed and save:
            self.save()
        return changed

    def save(self):
        write_json(self.path, self.snapshot(), indent=2)
