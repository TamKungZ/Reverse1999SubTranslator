from PySide6.QtGui import QPainter

from .fonts import families_for, load_fonts, make_font, set_languages
from .menu import draw_menu
from .state import RenderState
from .style import resolve_style
from .toast import draw_toast
from .translation import draw_translation

VISIBLE = 0.01

__all__ = ["RenderState", "families_for", "load_fonts", "make_font", "paint", "resolve_style", "set_languages"]


def paint(p, W, H, st):
    s = H / 1080.0
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    view = st.view
    if view and view.get("kind") in ("sentence", "words") and st.reveal > VISIBLE:
        p.save()
        p.setOpacity(st.reveal)
        p.translate(0, (1 - st.reveal) * 10 * s)
        draw_translation(p, W, H, s, st)
        p.restore()
    if st.menu_rows is not None and st.menu_reveal > VISIBLE:
        draw_menu(p, W, H, s, st)
    if st.toast and st.toast_alpha > VISIBLE:
        draw_toast(p, W, H, s, st)
