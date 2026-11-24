from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
    QTextCharFormat,
    QTextLayout,
    QTextOption,
)

ASSETS = Path(__file__).parent / "assets"
FAMILIES = ["Sarabun", "Leelawadee UI", "Yu Gothic UI", "Microsoft YaHei UI", "Malgun Gothic", "Segoe UI"]
THAI_FIRST = ["Kanit"]
thai_default = False

TEXT = QColor(236, 236, 238)
DIM = QColor(142, 142, 148)
FAINT = QColor(98, 98, 104)
SURFACE = QColor(24, 24, 26)
NAME_COLOR = QColor(255, 255, 255)
TERM_COLOR = QColor(176, 176, 184)
KIND_COLOR = {"name": NAME_COLOR, "term": TERM_COLOR}


@dataclass
class RenderState:
    view: dict = None
    reveal: float = 0.0
    ui: dict = field(default_factory=dict)
    menu_rows: list = None
    menu_reveal: float = 0.0
    sel_pos: float = 0.0
    row_on: list = field(default_factory=list)
    row_ratio: list = field(default_factory=list)
    toast: str = ""
    toast_alpha: float = 0.0
    pulse: float = 0.0
    hotkeys: dict = field(default_factory=dict)
    t: object = staticmethod(lambda key, **kw: key)


def load_fonts():
    for ttf in sorted(ASSETS.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(ttf))


def set_thai_default(on):
    global thai_default
    thai_default = bool(on)


def make_font(px, weight=QFont.Weight.Normal, italic=False, family=""):
    font = QFont()
    lead = [family] if family else (THAI_FIRST if thai_default else [])
    font.setFamilies(lead + FAMILIES)
    font.setPixelSize(max(6, int(round(px))))
    font.setWeight(weight)
    font.setItalic(italic)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def with_alpha(color, alpha):
    c = QColor(color)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


_px_cache = {}


def px_for_height(family, target, sample):
    key = (family, thai_default, sample, round(target, 1))
    if key not in _px_cache:
        px = max(8.0, target)
        for _ in range(3):
            h = QFontMetricsF(make_font(px, family=family)).tightBoundingRect(sample).height()
            if h <= 0:
                break
            px *= target / h
        _px_cache[key] = px
    return _px_cache[key]


def ink_ascent(font, sample):
    return -QFontMetricsF(font).tightBoundingRect(sample).top()


def _layout(text, ranges, font, width, min_pitch):
    tl = QTextLayout(text, font)
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    tl.setTextOption(option)
    formats = []
    for start, length, color in ranges:
        fr = QTextLayout.FormatRange()
        fr.start, fr.length = start, length
        fmt = QTextCharFormat()
        fmt.setForeground(QBrush(color))
        fr.format = fmt
        formats.append(fr)
    tl.setFormats(formats)
    tl.beginLayout()
    lines = []
    while True:
        line = tl.createLine()
        if not line.isValid():
            break
        line.setLineWidth(width)
        lines.append(line)
    pitch = max(min_pitch, (lines[0].height() * 1.04) if lines else 0.0)
    for i, line in enumerate(lines):
        line.setPosition(QPointF(0, i * pitch))
    tl.endLayout()
    return tl, lines, pitch


def _compose(segments, highlight):
    text, ranges = "", []
    for seg in segments:
        t = seg["t"]
        color = KIND_COLOR.get(seg.get("k")) if highlight else None
        if color is not None:
            ranges.append((len(text), len(t), color))
        text += t
    return text, ranges


def fit_text(segments, base_px, width, max_lines, family, highlight, min_pitch):
    text, ranges = _compose(segments, highlight)
    scale = 1.0
    while True:
        font = make_font(base_px * scale, family=family)
        tl, lines, pitch = _layout(text, ranges, font, width, min_pitch * scale)
        if len(lines) <= max_lines or scale <= 0.74:
            break
        scale *= 0.94
    if len(lines) > max_lines:
        cut = lines[max_lines - 1].textStart() + lines[max_lines - 1].textLength()
        clipped = text[:cut].rstrip(" \u200b")
        while True:
            body = clipped + "\u2026"
            r = [(a, min(n, len(clipped) - a), c) for a, n, c in ranges if a < len(clipped)]
            tl, lines, pitch = _layout(body, r, font, width, min_pitch * scale)
            if len(lines) <= max_lines or len(clipped) < 4:
                text, ranges = body, r
                break
            clipped = clipped[:-2].rstrip(" \u200b")
    return font, text, ranges, len(lines), pitch


def resolve_style(view, ui, W, H, s):
    style = view.get("style") or {}
    family = ui.get("font_family") or ""
    adjust = ui.get("size_adjust", 1.0)
    if ui.get("match_original", True) and style:
        text_h = style["text_ink_h"] * H
        return {
            "family": family,
            "text_px": px_for_height(family, text_h, "Hgdp") * adjust,
            "name_px": px_for_height(family, style["name_cap"] * H, "H") * adjust,
            "text_color": QColor(style["text_color"]),
            "name_color": QColor(style["name_color"]),
            "text_left": style["text_left"] * W,
            "name_left": style["name_left"] * W,
            "name_to_text": style["name_to_text"] * H,
            "pitch": (style.get("pitch") or 0.0) * H,
        }
    color = QColor(ui.get("text_color", "#f4eee2"))
    px = 34 * s * adjust
    left = ui["panel_x"][0] * W
    return {
        "family": family, "text_px": px, "name_px": px * 1.2, "text_color": color, "name_color": color,
        "text_left": left, "name_left": left, "name_to_text": 76 * s, "pitch": 0.0,
    }


def draw_text(p, tl_args, x, y, color, shadow, s):
    text, ranges, font, width, pitch = tl_args
    if shadow:
        plain, _, _ = _layout(text, [], font, width, pitch)
        p.setPen(QColor(0, 0, 0, 170))
        plain.draw(p, QPointF(x + 1.5 * s, y + 1.5 * s))
    main, _, _ = _layout(text, ranges, font, width, pitch)
    p.setPen(color)
    main.draw(p, QPointF(x, y))


def word_rows(chips, font, width, max_rows, min_pitch, s):
    fm = QFontMetricsF(font)
    pitch = max(min_pitch, fm.height() * 1.04)
    gap = max(fm.horizontalAdvance(" ") * 1.4, 10 * s)
    rows, cur, cur_w = [], [], 0.0
    for chip in chips:
        w = max(fm.horizontalAdvance(chip["w"]), fm.horizontalAdvance(chip["m"]))
        if cur and cur_w + gap + w > width:
            rows.append((cur, cur_w))
            cur, cur_w = [], 0.0
        cur_w += (gap if cur else 0.0) + w
        cur.append((chip, w))
    if cur:
        rows.append((cur, cur_w))
    return [(cells, gap) for cells, _ in rows[:max_rows]] or [([({"w": "\u2014", "m": "", "k": "word"}, 20 * s)], gap)], pitch


def draw_word_rows(p, rows, font, style, text_top, pitch, highlight, shadow, s):
    fm = QFontMetricsF(font)
    base = text_top + ink_ascent(font, "Hgdp")
    p.setFont(font)
    for r, (cells, gap) in enumerate(rows):
        x = style["text_left"]
        top = base + r * pitch * 2.35
        for chip, w in cells:
            color = KIND_COLOR.get(chip["k"]) if highlight else None
            for line, text in enumerate((chip["w"], chip["m"])):
                if not text:
                    continue
                pos = QPointF(x + (w - fm.horizontalAdvance(text)) / 2, top + line * pitch)
                if shadow:
                    p.setPen(QColor(0, 0, 0, 170))
                    p.drawText(QPointF(pos.x() + 1.5 * s, pos.y() + 1.5 * s), text)
                p.setPen(color or style["text_color"])
                p.drawText(pos, text)
            x += w + gap


def draw_translation(p, W, H, s, st):
    ui, view = st.ui, st.view
    style = resolve_style(view, ui, W, H, s)
    family = style["family"]
    highlight = ui.get("highlight_names", False)
    shadow = ui.get("text_shadow", False)
    right = ui["panel_x"][1] * W
    width = max(200.0, right - style["text_left"])
    words = view["kind"] == "words"
    if words:
        font = make_font(style["text_px"], family=family)
        rows, pitch = word_rows(view["chips"], font, width, ui.get("max_lines", 3), style["pitch"], s)
        nlines = 0
    else:
        font, text, ranges, nlines, pitch = fit_text(
            view["segments"], style["text_px"], width, ui.get("max_lines", 3), family, highlight, style["pitch"]
        )
    speaker = view.get("speaker") if ui.get("show_speaker", True) else None
    tight_h = QFontMetricsF(font).tightBoundingRect("Hgdp").height()
    if ui.get("line_space", "grow") == "reserve":
        count = max(1, int(ui.get("max_lines", 3)))
        n2t = style["name_to_text"]
    else:
        count = len(rows) if words else nlines
        n2t = style["name_to_text"] if speaker else 0.0
    block_h = (count - 1) * pitch * (2.35 if words else 1.0) + (pitch if words else 0.0) + tight_h
    anchor = view.get("anchor_top") or 0.80
    bottom = anchor * H - 0.022 * H - ui.get("offset_y", 0) * s
    block_top = max(6 * s, bottom - n2t - block_h)
    text_top = block_top + n2t
    first_line_ascent = QFontMetricsF(font).ascent()
    y = text_top + ink_ascent(font, "Hgdp") - first_line_ascent
    if words:
        draw_word_rows(p, rows, font, style, text_top, pitch, highlight, shadow, s)
    else:
        draw_text(p, (text, ranges, font, width, pitch), style["text_left"], y, style["text_color"], shadow, s)
    if speaker:
        name_font = make_font(style["name_px"], family=family)
        name_ascent = QFontMetricsF(name_font).ascent()
        ny = block_top + ink_ascent(name_font, "H") - name_ascent
        draw_text(p, (speaker["display"], [], name_font, 4000.0, 0.0), style["name_left"], ny, style["name_color"], shadow, s)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return QColor(*(int(a.getRgb()[i] + (b.getRgb()[i] - a.getRgb()[i]) * t) for i in range(3)))


def rounded(rect, radius):
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def draw_panel(p, rect, s, opacity):
    path = rounded(rect, 14 * s)
    p.fillPath(path, with_alpha(SURFACE, 255 * opacity))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 22), 1.0 * s))
    p.drawPath(path)


def draw_toast(p, W, H, s, st):
    font = make_font(21 * s, QFont.Weight.Medium)
    w, h = QFontMetricsF(font).horizontalAdvance(st.toast) + 44 * s, 42 * s
    rect = QRectF((W - w) / 2, 0.07 * H, w, h)
    p.save()
    p.setOpacity(st.toast_alpha)
    p.translate(0, (1 - st.toast_alpha) * -8 * s)
    path = rounded(rect, h / 2)
    p.fillPath(path, with_alpha(SURFACE, 242))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 26), 1.0 * s))
    p.drawPath(path)
    p.setFont(font)
    p.setPen(TEXT)
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, st.toast)
    p.restore()


def _at(values, i, default):
    return values[i] if i < len(values) else default


def draw_toggle(p, right, cy, s, amount):
    tw, th = 38 * s, 20 * s
    track = QRectF(right - tw, cy - th / 2, tw, th)
    p.fillPath(rounded(track, th / 2), mix(QColor(66, 66, 70), QColor(226, 226, 230), amount))
    r = th / 2 - 3 * s
    kx = track.left() + th / 2 + (tw - th) * amount
    p.setBrush(mix(QColor(168, 168, 174), SURFACE, amount))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(kx, cy), r, r)
    p.setBrush(Qt.BrushStyle.NoBrush)


def draw_menu(p, W, H, s, st):
    rows = st.menu_rows
    p.save()
    p.fillRect(QRectF(0, 0, W, H), QColor(0, 0, 0, int(110 * st.menu_reveal)))
    p.setOpacity(st.menu_reveal)
    row_h, head_h, foot_h = 36 * s, 64 * s, 76 * s
    width = 640 * s
    height = head_h + row_h * len(rows) + foot_h
    rect = QRectF((W - width) / 2, (H - height) / 2 + (1 - st.menu_reveal) * 14 * s, width, height)
    draw_panel(p, rect, s, 0.97)
    pad = 36 * s
    hair = QPen(QColor(255, 255, 255, 20), 1.0 * s)
    p.setFont(make_font(24 * s, QFont.Weight.DemiBold))
    p.setPen(TEXT)
    p.drawText(QRectF(rect.left() + pad, rect.top() + 14 * s, width - 2 * pad, 40 * s), Qt.AlignmentFlag.AlignVCenter, st.t("menu.title"))
    p.setPen(hair)
    p.drawLine(QPointF(rect.left() + pad, rect.top() + head_h - 4 * s), QPointF(rect.right() - pad, rect.top() + head_h - 4 * s))
    top = rect.top() + head_h
    sel = min(max(st.sel_pos, 0.0), max(0, len(rows) - 1))
    pill = QRectF(rect.left() + 16 * s, top + sel * row_h + 2 * s, width - 32 * s, row_h - 4 * s)
    p.fillPath(rounded(pill, 10 * s), QColor(255, 255, 255, 18))
    p.fillPath(rounded(QRectF(pill.left() + 8 * s, pill.center().y() - 8 * s, 2.5 * s, 16 * s), 1.2 * s), TEXT)
    f_label = make_font(20 * s, QFont.Weight.Normal)
    f_value = make_font(20 * s, QFont.Weight.Medium)
    fm = QFontMetricsF(f_value)
    arrow = 22 * s
    for i, row in enumerate(rows):
        near = max(0.0, 1.0 - abs(i - sel))
        r = QRectF(rect.left() + 16 * s, top + i * row_h + 2 * s, width - 32 * s, row_h - 4 * s)
        right = r.right() - 18 * s
        p.setFont(f_label)
        p.setPen(mix(QColor(190, 190, 196), TEXT, near))
        p.drawText(QRectF(r.left() + 24 * s, r.top(), r.width() * 0.55, r.height()), Qt.AlignmentFlag.AlignVCenter, row["label"])
        if row["kind"] == "toggle":
            draw_toggle(p, right, r.center().y(), s, _at(st.row_on, i, 1.0 if row.get("on") else 0.0))
            continue
        p.setFont(f_value)
        if row["kind"] == "action":
            p.setPen(mix(FAINT, DIM, near))
            p.drawText(QRectF(r.left(), r.top(), r.width() - 18 * s, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, st.t("menu.enter"))
            continue
        text = row["value"]
        tw = fm.horizontalAdvance(text)
        vx = right - arrow
        p.setPen(mix(DIM, TEXT, near))
        p.drawText(QRectF(vx - tw - 4 * s, r.top(), tw + 8 * s, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, text)
        p.setPen(with_alpha(DIM, 200 * near))
        p.drawText(QRectF(right - arrow + 6 * s, r.top(), arrow, r.height()), Qt.AlignmentFlag.AlignVCenter, "›")
        p.drawText(QRectF(vx - tw - arrow, r.top(), arrow, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "‹")
        if row["kind"] == "number" and row["ratio"] is not None:
            bw = 96 * s
            bar = QRectF(vx - tw - arrow - 14 * s - bw, r.center().y() - 1.5 * s, bw, 3 * s)
            p.fillPath(rounded(bar, 1.5 * s), QColor(255, 255, 255, 30))
            ratio = _at(st.row_ratio, i, row["ratio"])
            fill = QRectF(bar.left(), bar.top(), max(3 * s, bar.width() * ratio), bar.height())
            p.fillPath(rounded(fill, 1.5 * s), mix(DIM, TEXT, near))
    y = top + row_h * len(rows)
    p.setPen(hair)
    p.drawLine(QPointF(rect.left() + pad, y + 6 * s), QPointF(rect.right() - pad, y + 6 * s))
    p.setFont(make_font(16 * s, QFont.Weight.Normal))
    p.setPen(DIM)
    p.drawText(QRectF(rect.left(), y + 12 * s, width, 26 * s), Qt.AlignmentFlag.AlignCenter, st.t("menu.hint"))
    hk = st.hotkeys
    p.setPen(FAINT)
    p.drawText(QRectF(rect.left(), y + 40 * s, width, 26 * s), Qt.AlignmentFlag.AlignCenter,
               st.t("menu.keys", toggle=hk.get("toggle", ""), mode=hk.get("mode", ""), menu=hk.get("menu", "")))
    p.restore()


def paint(p, W, H, st):
    s = H / 1080.0
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    view = st.view
    if view and view.get("kind") in ("sentence", "words") and st.reveal > 0.01:
        p.save()
        p.setOpacity(st.reveal)
        p.translate(0, (1 - st.reveal) * 10 * s)
        draw_translation(p, W, H, s, st)
        p.restore()
    if st.menu_rows is not None and st.menu_reveal > 0.01:
        draw_menu(p, W, H, s, st)
    if st.toast and st.toast_alpha > 0.01:
        draw_toast(p, W, H, s, st)
