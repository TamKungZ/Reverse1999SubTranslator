from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPen

from .fonts import make_font
from .shapes import draw_panel, draw_slider, draw_toggle, rounded
from .theme import DIM, FAINT, HAIRLINE, TEXT, mix, with_alpha

ROW_H, HEAD_H, FOOT_H = 36, 64, 76
WIDTH = 640
PAD = 36
LABEL_COLOR = QColor(190, 190, 196)
SELECTION = QColor(255, 255, 255, 18)
LEFT = Qt.AlignmentFlag.AlignLeft
RIGHT = Qt.AlignmentFlag.AlignRight
VCENTER = Qt.AlignmentFlag.AlignVCenter


def _at(values, i, default):
    return values[i] if i < len(values) else default


def _hairline(p, rect, y, s):
    p.setPen(QPen(HAIRLINE, 1.0 * s))
    p.drawLine(QPointF(rect.left() + PAD * s, y), QPointF(rect.right() - PAD * s, y))


def _draw_header(p, rect, s, title):
    p.setFont(make_font(24 * s, QFont.Weight.Normal, ui=True))
    p.setPen(TEXT)
    p.drawText(QRectF(rect.left() + PAD * s, rect.top() + 14 * s, rect.width() - 2 * PAD * s, 40 * s), VCENTER, title)
    _hairline(p, rect, rect.top() + (HEAD_H - 4) * s, s)


def _draw_selection(p, rect, top, sel, s):
    pill = QRectF(rect.left() + 16 * s, top + sel * ROW_H * s + 2 * s, rect.width() - 32 * s, (ROW_H - 4) * s)
    p.fillPath(rounded(pill, 10 * s), SELECTION)
    marker = QRectF(pill.left() + 8 * s, pill.center().y() - 8 * s, 2.5 * s, 16 * s)
    p.fillPath(rounded(marker, 1.2 * s), TEXT)


def _draw_row(p, st, i, row, r, near, s, fonts):
    f_label, f_value = fonts
    right = r.right() - 18 * s
    p.setFont(f_label)
    p.setPen(mix(LABEL_COLOR, TEXT, near))
    p.drawText(QRectF(r.left() + 24 * s, r.top(), r.width() * 0.55, r.height()), VCENTER, row["label"])
    if row["kind"] == "toggle":
        draw_toggle(p, right, r.center().y(), s, _at(st.row_on, i, 1.0 if row.get("on") else 0.0))
        return
    p.setFont(f_value)
    if row["kind"] == "action":
        p.setPen(mix(FAINT, DIM, near))
        p.drawText(QRectF(r.left(), r.top(), r.width() - 18 * s, r.height()), VCENTER | RIGHT, st.t("menu.enter"))
        return
    arrow = 22 * s
    text = row["value"]
    tw = QFontMetricsF(f_value).horizontalAdvance(text)
    vx = right - arrow
    p.setPen(mix(DIM, TEXT, near))
    p.drawText(QRectF(vx - tw - 4 * s, r.top(), tw + 8 * s, r.height()), VCENTER | RIGHT, text)
    p.setPen(with_alpha(DIM, 200 * near))
    p.drawText(QRectF(right - arrow + 6 * s, r.top(), arrow, r.height()), VCENTER, "›")
    p.drawText(QRectF(vx - tw - arrow, r.top(), arrow, r.height()), VCENTER | LEFT, "‹")
    if row["kind"] == "number" and row["ratio"] is not None:
        bw = 96 * s
        bar = QRectF(vx - tw - arrow - 14 * s - bw, r.center().y() - 1.5 * s, bw, 3 * s)
        draw_slider(p, bar, _at(st.row_ratio, i, row["ratio"]), s, mix(DIM, TEXT, near))


def _draw_footer(p, st, rect, y, s):
    _hairline(p, rect, y + 6 * s, s)
    p.setFont(make_font(16 * s, QFont.Weight.Light, ui=True))
    p.setPen(DIM)
    p.drawText(QRectF(rect.left(), y + 12 * s, rect.width(), 26 * s), Qt.AlignmentFlag.AlignCenter, st.t("menu.hint"))
    hk = st.hotkeys
    p.setPen(FAINT)
    p.drawText(QRectF(rect.left(), y + 40 * s, rect.width(), 26 * s), Qt.AlignmentFlag.AlignCenter,
               st.t("menu.keys", toggle=hk.get("toggle", ""), mode=hk.get("mode", ""), menu=hk.get("menu", "")))


def draw_menu(p, W, H, s, st):
    rows = st.menu_rows
    p.save()
    p.fillRect(QRectF(0, 0, W, H), QColor(0, 0, 0, int(110 * st.menu_reveal)))
    p.setOpacity(st.menu_reveal)
    width = WIDTH * s
    height = (HEAD_H + ROW_H * len(rows) + FOOT_H) * s
    rect = QRectF((W - width) / 2, (H - height) / 2 + (1 - st.menu_reveal) * 14 * s, width, height)
    draw_panel(p, rect, s, 0.97)
    _draw_header(p, rect, s, st.t("menu.title"))
    top = rect.top() + HEAD_H * s
    sel = min(max(st.sel_pos, 0.0), max(0, len(rows) - 1))
    _draw_selection(p, rect, top, sel, s)
    fonts = make_font(20 * s, QFont.Weight.Light, ui=True), make_font(20 * s, QFont.Weight.Normal, ui=True)
    for i, row in enumerate(rows):
        r = QRectF(rect.left() + 16 * s, top + i * ROW_H * s + 2 * s, width - 32 * s, (ROW_H - 4) * s)
        _draw_row(p, st, i, row, r, max(0.0, 1.0 - abs(i - sel)), s, fonts)
    _draw_footer(p, st, rect, top + ROW_H * s * len(rows), s)
    p.restore()
