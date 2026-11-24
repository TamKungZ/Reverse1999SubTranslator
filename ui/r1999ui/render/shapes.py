from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen

from .theme import SURFACE, TRACK, mix, with_alpha

TOGGLE_OFF_TRACK = QColor(66, 66, 70)
TOGGLE_ON_TRACK = QColor(226, 226, 230)
TOGGLE_OFF_KNOB = QColor(168, 168, 174)
PANEL_BORDER = QColor(255, 255, 255, 22)


def rounded(rect, radius):
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def outline(p, path, color, width):
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(color, width))
    p.drawPath(path)


def draw_panel(p, rect, s, opacity):
    path = rounded(rect, 14 * s)
    p.fillPath(path, with_alpha(SURFACE, 255 * opacity))
    outline(p, path, PANEL_BORDER, 1.0 * s)


def draw_toggle(p, right, cy, s, amount):
    tw, th = 38 * s, 20 * s
    track = QRectF(right - tw, cy - th / 2, tw, th)
    p.fillPath(rounded(track, th / 2), mix(TOGGLE_OFF_TRACK, TOGGLE_ON_TRACK, amount))
    r = th / 2 - 3 * s
    kx = track.left() + th / 2 + (tw - th) * amount
    p.setBrush(mix(TOGGLE_OFF_KNOB, SURFACE, amount))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(kx, cy), r, r)
    p.setBrush(Qt.BrushStyle.NoBrush)


def draw_slider(p, bar, ratio, s, color):
    p.fillPath(rounded(bar, 1.5 * s), TRACK)
    fill = QRectF(bar.left(), bar.top(), max(3 * s, bar.width() * ratio), bar.height())
    p.fillPath(rounded(fill, 1.5 * s), color)
