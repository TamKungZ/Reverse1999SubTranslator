from PySide6.QtGui import QFontMetricsF

from .fonts import ink_ascent, make_font
from .style import resolve_style
from .text import ROW_GAP_FACTOR, draw_text, draw_word_rows, fit_text, word_rows

DEFAULT_ANCHOR = 0.80
ANCHOR_GAP = 0.022
TOP_MARGIN = 6


def _block_height(count, pitch, tight_h, words):
    if words:
        return (count - 1) * pitch * ROW_GAP_FACTOR + pitch + tight_h
    return (count - 1) * pitch + tight_h


def draw_translation(p, W, H, s, st):
    ui, view = st.ui, st.view
    style = resolve_style(view, ui, W, H, s)
    family = style["family"]
    highlight = ui.get("highlight_names", False)
    shadow = ui.get("text_shadow", False)
    max_lines = ui.get("max_lines", 3)
    centered = style["align"] == "center"
    if centered:
        width = max(200.0, (ui["panel_x"][1] - ui["panel_x"][0]) * W)
        left = style["center"] - width / 2
    else:
        width = max(200.0, ui["panel_x"][1] * W - style["text_left"])
        left = style["text_left"]
    align = "center" if centered else "left"
    words = view["kind"] == "words"
    if words:
        font = make_font(style["text_px"], family=family)
        rows, pitch = word_rows(view["chips"], font, width, max_lines, style["pitch"], s)
        count = len(rows)
    else:
        font, text, ranges, count, pitch = fit_text(
            view["segments"], style["text_px"], width, max_lines, family, highlight, style["pitch"], align
        )
    speaker = view.get("speaker") if ui.get("show_speaker", True) else None
    if ui.get("line_space", "grow") == "reserve":
        count = max(1, int(max_lines))
        name_to_text = style["name_to_text"]
    else:
        name_to_text = style["name_to_text"] if speaker else 0.0
    tight_h = QFontMetricsF(font).tightBoundingRect("Hgdp").height()
    block_h = _block_height(count, pitch, tight_h, words)
    anchor = view.get("anchor_top") or DEFAULT_ANCHOR
    bottom = anchor * H - ANCHOR_GAP * H - ui.get("offset_y", 0) * s
    block_top = max(TOP_MARGIN * s, bottom - name_to_text - block_h)
    text_top = block_top + name_to_text
    if words:
        draw_word_rows(p, rows, font, style, text_top, pitch, highlight, shadow, s)
    else:
        y = text_top + ink_ascent(font, "Hgdp") - QFontMetricsF(font).ascent()
        draw_text(p, (text, ranges, font, width, pitch, align), left, y, style["text_color"], shadow, s)
    if speaker:
        name_font = make_font(style["name_px"], family=family)
        ny = block_top + ink_ascent(name_font, "H") - QFontMetricsF(name_font).ascent()
        draw_text(p, (speaker["display"], [], name_font, 4000.0, 0.0), style["name_left"], ny, style["name_color"], shadow, s)
