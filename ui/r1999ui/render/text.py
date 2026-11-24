from PySide6.QtCore import QPointF
from PySide6.QtGui import QBrush, QFontMetricsF, QTextCharFormat, QTextLayout, QTextOption

from .fonts import ink_ascent, make_font
from .theme import KIND_COLOR, SHADOW, SHADOW_OFFSET

ROW_GAP_FACTOR = 2.35
MIN_FIT_SCALE = 0.74
ELLIPSIS = "…"


def layout(text, ranges, font, width, min_pitch, align="left"):
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
        x = (width - line.naturalTextWidth()) / 2 if align == "center" else 0.0
        line.setPosition(QPointF(x, i * pitch))
    tl.endLayout()
    return tl, lines, pitch


def compose(segments, highlight):
    text, ranges = "", []
    for seg in segments:
        t = seg["t"]
        color = KIND_COLOR.get(seg.get("k")) if highlight else None
        if color is not None:
            ranges.append((len(text), len(t), color))
        text += t
    return text, ranges


def fit_text(segments, base_px, width, max_lines, family, highlight, min_pitch, align="left"):
    """Shrinks the text a little, then cuts it with an ellipsis, until it fits in `max_lines`."""
    text, ranges = compose(segments, highlight)
    scale = 1.0
    while True:
        font = make_font(base_px * scale, family=family)
        tl, lines, pitch = layout(text, ranges, font, width, min_pitch * scale, align)
        if len(lines) <= max_lines or scale <= MIN_FIT_SCALE:
            break
        scale *= 0.94
    if len(lines) > max_lines:
        cut = lines[max_lines - 1].textStart() + lines[max_lines - 1].textLength()
        clipped = text[:cut].rstrip(" ​")
        while True:
            body = clipped + ELLIPSIS
            r = [(a, min(n, len(clipped) - a), c) for a, n, c in ranges if a < len(clipped)]
            tl, lines, pitch = layout(body, r, font, width, min_pitch * scale, align)
            if len(lines) <= max_lines or len(clipped) < 4:
                text, ranges = body, r
                break
            clipped = clipped[:-2].rstrip(" ​")
    return font, text, ranges, len(lines), pitch


def draw_text(p, tl_args, x, y, color, shadow, s):
    text, ranges, font, width, pitch, *rest = tl_args
    align = rest[0] if rest else "left"
    if shadow:
        plain, _, _ = layout(text, [], font, width, pitch, align)
        p.setPen(SHADOW)
        plain.draw(p, QPointF(x + SHADOW_OFFSET * s, y + SHADOW_OFFSET * s))
    main, _, _ = layout(text, ranges, font, width, pitch, align)
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
    return [(cells, gap) for cells, _ in rows[:max_rows]] or [([({"w": "—", "m": "", "k": "word"}, 20 * s)], gap)], pitch


def draw_word_rows(p, rows, font, style, text_top, pitch, highlight, shadow, s):
    fm = QFontMetricsF(font)
    base = text_top + ink_ascent(font, "Hgdp")
    p.setFont(font)
    for r, (cells, gap) in enumerate(rows):
        x = style["text_left"]
        if style["align"] == "center":
            x = style["center"] - (sum(w for _, w in cells) + gap * (len(cells) - 1)) / 2
        top = base + r * pitch * ROW_GAP_FACTOR
        for chip, w in cells:
            color = KIND_COLOR.get(chip["k"]) if highlight else None
            for line, text in enumerate((chip["w"], chip["m"])):
                if not text:
                    continue
                pos = QPointF(x + (w - fm.horizontalAdvance(text)) / 2, top + line * pitch)
                if shadow:
                    p.setPen(SHADOW)
                    p.drawText(QPointF(pos.x() + SHADOW_OFFSET * s, pos.y() + SHADOW_OFFSET * s), text)
                p.setPen(color or style["text_color"])
                p.drawText(pos, text)
            x += w + gap
