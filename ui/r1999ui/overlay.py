import math
import time

from PySide6.QtCore import QEasingCurve, QRect, QTimer, QVariantAnimation, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from . import render, winutil


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
        self._view_anim = self._make_anim(lambda v: self._set("reveal", v), self._view_done)
        self._menu_anim = self._make_anim(lambda v: self._set("menu_reveal", v), self._menu_done)
        self._toast_anim = self._make_anim(lambda v: self._set("toast_alpha", v), None)
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self._run(self._toast_anim, 0.0, 300))
        self._tick = QTimer(self)
        self._tick.setInterval(40)
        self._tick.timeout.connect(self._on_tick)
        self._smooth = QTimer(self)
        self._smooth.setInterval(16)
        self._smooth.timeout.connect(self._smooth_step)
        self._smooth_at = 0.0
        self._goal = (0.0, [], [])
        self._topmost = QTimer(self)
        self._topmost.setInterval(1500)
        self._topmost.timeout.connect(self._reassert)

    def _make_anim(self, on_value, on_done):
        anim = QVariantAnimation(self)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(on_value)
        if on_done:
            anim.finished.connect(on_done)
        return anim

    def _set(self, name, value):
        setattr(self.state, name, float(value))
        self._sync()

    def _run(self, anim, target, ms):
        current = {"reveal": self.state.reveal, "menu_reveal": self.state.menu_reveal, "toast_alpha": self.state.toast_alpha}
        key = {id(self._view_anim): "reveal", id(self._menu_anim): "menu_reveal", id(self._toast_anim): "toast_alpha"}[id(anim)]
        anim.stop()
        if not self.ui["animations"]:
            setattr(self.state, key, float(target))
            self._sync()
            if anim is self._view_anim:
                self._view_done()
            elif anim is self._menu_anim:
                self._menu_done()
            return
        anim.setDuration(ms)
        anim.setStartValue(current[key])
        anim.setEndValue(float(target))
        anim.start()

    def _view_done(self):
        if self.state.reveal <= 0.01:
            self.state.view = None
        self._sync()

    def _menu_done(self):
        if self.state.menu_reveal <= 0.01:
            self.state.menu_rows = None
            self._smooth.stop()
        self._sync()

    def set_game(self, game):
        self.game = game
        self._sync()

    def set_view(self, view):
        if view and view.get("kind") in ("sentence", "words"):
            first = self.state.view is None or self.state.reveal < 0.5
            self.state.view = view
            if first or self._view_anim.endValue() != 1.0:
                self._run(self._view_anim, 1.0, 240)
            self._sync()
        elif self.state.view is not None:
            self._run(self._view_anim, 0.0, 170)

    def set_menu(self, rows):
        if rows is not None:
            st = self.state
            was_closed = st.menu_rows is None
            st.menu_rows = rows
            sel = next((i for i, r in enumerate(rows) if r["selected"]), 0)
            on = [1.0 if r.get("on") else 0.0 for r in rows]
            ratio = [r["ratio"] or 0.0 for r in rows]
            self._goal = (float(sel), on, ratio)
            if was_closed or not self.ui["animations"] or len(st.row_on) != len(rows):
                st.sel_pos, st.row_on, st.row_ratio = float(sel), on, ratio
            else:
                self._smooth_at = time.monotonic()
                self._smooth.start()
            if was_closed:
                self._run(self._menu_anim, 1.0, 200)
            self._sync()
        elif self.state.menu_rows is not None:
            self._run(self._menu_anim, 0.0, 150)

    def _smooth_step(self):
        now = time.monotonic()
        k = 1.0 - math.exp(-min(0.05, now - self._smooth_at) * 16.0)
        self._smooth_at = now
        st, busy = self.state, False

        def ease(cur, goal):
            nonlocal busy
            if abs(goal - cur) < 0.002:
                return goal
            busy = True
            return cur + (goal - cur) * k

        sel, on, ratio = self._goal
        st.sel_pos = ease(st.sel_pos, sel)
        st.row_on = [ease(c, g) for c, g in zip(st.row_on, on)]
        st.row_ratio = [ease(c, g) for c, g in zip(st.row_ratio, ratio)]
        self._sync()
        if not busy:
            self._smooth.stop()

    def toast(self, text, ms=1600):
        self.state.toast = text
        self._run(self._toast_anim, 1.0, 180)
        self._toast_timer.start(ms)

    def _wants_draw(self):
        st = self.state
        return (st.view is not None and st.reveal > 0.01) or (st.menu_rows is not None) or st.toast_alpha > 0.01

    def _sync(self):
        g = self.game
        visible_ok = g.running and g.foreground and g.w > 0
        if visible_ok and self._wants_draw():
            geometry = QRect(g.x, g.y, g.w, g.h)
            if self.geometry() != geometry:
                self.setGeometry(geometry)
            if not self.isVisible():
                self.show()
                self._tick.start()
                self._topmost.start()
            if winutil.IS_WINDOWS and not self._styled:
                winutil.prepare_overlay_window(int(self.winId()))
                self._styled = True
            self.update()
        elif self.isVisible():
            self.hide()
            self._tick.stop()
            self._topmost.stop()

    def _on_tick(self):
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
