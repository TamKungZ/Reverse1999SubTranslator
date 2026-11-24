from PySide6.QtGui import QColor

from .fonts import px_for_height


def resolve_style(view, ui, W, H, s):
    """The text style to draw with: measured from the game's own subtitle when available, else from the settings."""
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
