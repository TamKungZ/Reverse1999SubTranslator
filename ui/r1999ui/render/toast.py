from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF

from .fonts import make_font
from .shapes import outline, rounded
from .theme import HAIRLINE, SURFACE, TEXT, with_alpha


def draw_toast(p, W, H, s, st):
    font = make_font(21 * s, QFont.Weight.Medium)
    w, h = QFontMetricsF(font).horizontalAdvance(st.toast) + 44 * s, 42 * s
    rect = QRectF((W - w) / 2, 0.07 * H, w, h)
    p.save()
    p.setOpacity(st.toast_alpha)
    p.translate(0, (1 - st.toast_alpha) * -8 * s)
    path = rounded(rect, h / 2)
    p.fillPath(path, with_alpha(SURFACE, 242))
    outline(p, path, with_alpha(HAIRLINE, 26), 1.0 * s)
    p.setFont(font)
    p.setPen(TEXT)
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, st.toast)
    p.restore()
