from pathlib import Path

from .storage import clone, data_dir, read_json, write_json

DEFAULTS = {
    "enabled": True,
    "game_exe": "reverse1999.exe",
    "engine_port": 47631,
    "poll_ms": 110,
    "locale": "en",
    "font_family": "",
    "size_adjust": 1.0,
    "match_original": True,
    "highlight_names": False,
    "text_shadow": False,
    "text_color": "#f4eee2",
    "max_lines": 3,
    "line_space": "grow",
    "offset_y": 0,
    "show_speaker": True,
    "animations": True,
    "auto_exit": False,
    "panel_x": [0.215, 0.895],
    "hotkeys": {"toggle": "F7", "mode": "F8", "menu": "F9"},
    "menu_keys": {"up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT", "enter": "ENTER", "back": "ESC", "pageup": "PAGEUP", "pagedown": "PAGEDOWN"},
}


class UiSettings:
    def __init__(self, path=None):
        self.path = Path(path) if path else data_dir() / "ui.json"
        self.data = clone(DEFAULTS)
        for key, value in (read_json(self.path, {}) or {}).items():
            if key not in DEFAULTS:
                continue
            if isinstance(DEFAULTS[key], dict) and isinstance(value, dict):
                self.data[key].update(value)
            else:
                self.data[key] = value

    def __getitem__(self, key):
        return self.data[key]

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        write_json(self.path, self.data, indent=2)
