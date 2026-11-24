from PySide6.QtGui import QColor

TEXT = QColor(236, 236, 238)
DIM = QColor(142, 142, 148)
FAINT = QColor(98, 98, 104)
SURFACE = QColor(24, 24, 26)
NAME_COLOR = QColor(255, 255, 255)
TERM_COLOR = QColor(176, 176, 184)
KIND_COLOR = {"name": NAME_COLOR, "term": TERM_COLOR}

SHADOW = QColor(0, 0, 0, 170)
SHADOW_OFFSET = 1.5
HAIRLINE = QColor(255, 255, 255, 20)
TRACK = QColor(255, 255, 255, 30)


def with_alpha(color, alpha):
    c = QColor(color)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return QColor(*(int(a.getRgb()[i] + (b.getRgb()[i] - a.getRgb()[i]) * t) for i in range(3)))
