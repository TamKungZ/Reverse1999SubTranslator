from collections import deque

DEFAULT_STYLE = {
    "text_ink_h": 33 / 1080,
    "name_cap": 31 / 1080,
    "text_left": 412 / 1920,
    "text_align": "left",
    "text_center": 0.5,
    "name_left": 426 / 1920,
    "name_to_text": 76 / 1080,
    "pitch": None,
    "text_color": "#e1dedc",
    "name_color": "#b4aba4",
}

STYLE_WINDOW = 9
MEDIAN_KEYS = ("text_ink_h", "name_cap", "name_to_text", "text_left", "name_left", "pitch")
LAYOUT_KEYS = ("text_left", "name_left", "name_to_text")   # these belong to one subtitle, the next one may be laid out differently
INK_HEIGHT_RANGE = (0.02, 0.05)


def median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


class StyleTracker:
    """Keeps the subtitle style measured from the game, smoothing out OCR noise."""

    def __init__(self):
        self.values = dict(DEFAULT_STYLE)
        self._history = {}

    def merge(self, new):
        for key, value in (new or {}).items():
            if key == "text_ink_h" and not INK_HEIGHT_RANGE[0] <= value <= INK_HEIGHT_RANGE[1]:
                continue
            if key in MEDIAN_KEYS:
                if value and value > 0:
                    hist = self._history.setdefault(key, deque(maxlen=STYLE_WINDOW))
                    hist.append(value)
                    self.values[key] = median(hist)
            else:
                self.values[key] = value

    def new_text(self):
        for key in LAYOUT_KEYS:
            self._history.pop(key, None)

    def snapshot(self):
        return dict(self.values)
