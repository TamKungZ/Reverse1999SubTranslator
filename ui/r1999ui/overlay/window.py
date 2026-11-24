import time

from PySide6.QtCore import QRect, QTimer, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from .. import render, winutil
from .animation import MenuSmoother, Tween

VISIBLE_REVEAL = 0.01
PENDING_TICK_MS = 40
TOPMOST_MS = 1500


class OverlayWindow(QWidget):
    def __init__(self, ui):
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.NoDropShadowWindowHint
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.ui = ui
        self.state = render.RenderState(ui=ui.data, hotkeys=ui["hotkeys"])
        self.game = winutil.GameState()
        self._styled = False
        self._view_tween = self._tween("reveal", self._view_done)
        self._menu_tween = self._tween("menu_reveal", self._menu_done)
        self._toast_tween = self._tween("toast_alpha")
        self._smoother = MenuSmoother(self, self.state, self._sync)
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self._toast_tween.run(0.0, 300, self.ui["animations"]))
        self._pending_tick = QTimer(self)
        self._pending_tick.setInterval(PENDING_TICK_MS)
        self._pending_tick.timeout.connect(self._on_pending_tick)
        self._topmost = QTimer(self)
        self._topmost.setInterval(TOPMOST_MS)
        self._topmost.timeout.connect(self._reassert)

    def _tween(self, field, on_done=None):
        def set_(value):
            setattr(self.state, field, value)
            self._sync()

        return Tween(self, lambda: getattr(self.state, field), set_, on_done)

    def _animate(self, tween, target, ms):
        tween.run(target, ms, self.ui["animations"])

    def _view_done(self):
        if self.state.reveal <= VISIBLE_REVEAL:
            self.state.view = None
        self._sync()

    def _menu_done(self):
        if self.state.menu_reveal <= VISIBLE_REVEAL:
            self.state.menu_rows = None
            self._smoother.stop()
        self._sync()

    def set_game(self, game):
        self.game = game
        self._sync()

    def set_view(self, view):
        if view and view.get("kind") in ("sentence", "words"):
            first = self.state.view is None or self.state.reveal < 0.5
            self.state.view = view
            if first or self._view_tween.target != 1.0:
                self._animate(self._view_tween, 1.0, 240)
            self._sync()
        elif self.state.view is not None:
            self._animate(self._view_tween, 0.0, 170)

    def set_menu(self, rows):
        if rows is not None:
            was_closed = self.state.menu_rows is None
            self.state.menu_rows = rows
            self._smoother.set_rows(rows, snap=was_closed or not self.ui["animations"])
            if was_closed:
                self._animate(self._menu_tween, 1.0, 200)
            self._sync()
        elif self.state.menu_rows is not None:
            self._animate(self._menu_tween, 0.0, 150)

    def toast(self, text, ms=1600):
        self.state.toast = text
        self._animate(self._toast_tween, 1.0, 180)
        self._toast_timer.start(ms)

    def _wants_draw(self):
        st = self.state
        return (
            (st.view is not None and st.reveal > VISIBLE_REVEAL)
            or st.menu_rows is not None
            or st.toast_alpha > VISIBLE_REVEAL
        )

    def _sync(self):
        g = self.game
        if g.running and g.foreground and g.w > 0 and self._wants_draw():
            geometry = QRect(g.x, g.y, g.w, g.h)
            if self.geometry() != geometry:
                self.setGeometry(geometry)
            if not self.isVisible():
                self.show()
                self._pending_tick.start()
                self._topmost.start()
            if winutil.IS_WINDOWS and not self._styled:
                winutil.prepare_overlay_window(int(self.winId()))
                self._styled = True
            self.update()
        elif self.isVisible():
            self.hide()
            self._pending_tick.stop()
            self._topmost.stop()

    def _on_pending_tick(self):
        view = self.state.view
        if view is not None and view.get("pending"):
            self.update()

    def _reassert(self):
        if winutil.IS_WINDOWS and self.isVisible():
            winutil.keep_topmost(int(self.winId()))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        self.state.pulse = time.monotonic()
        render.paint(p, self.width(), self.height(), self.state)
        p.end()
