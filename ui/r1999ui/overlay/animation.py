import math
import time

from PySide6.QtCore import QEasingCurve, QTimer, QVariantAnimation


class Tween:
    """Animates one value from where it is now to a target, or jumps there when animations are off."""

    def __init__(self, parent, get, set_, on_done=None):
        self.get, self.set = get, set_
        self.on_done = on_done
        self.anim = QVariantAnimation(parent)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(lambda v: self.set(float(v)))
        if on_done:
            self.anim.finished.connect(on_done)

    @property
    def target(self):
        return self.anim.endValue()

    def run(self, target, ms, animate=True):
        self.anim.stop()
        if not animate:
            self.set(float(target))
            if self.on_done:
                self.on_done()
            return
        self.anim.setDuration(ms)
        self.anim.setStartValue(self.get())
        self.anim.setEndValue(float(target))
        self.anim.start()


class MenuSmoother:
    """Eases the menu selection bar, toggles and sliders toward the values of the current rows."""

    RATE = 16.0
    SETTLED = 0.002

    def __init__(self, parent, state, on_change):
        self.state = state
        self.on_change = on_change
        self._goal = (0.0, [], [])
        self._at = 0.0
        self._timer = QTimer(parent)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._step)

    def set_rows(self, rows, snap):
        st = self.state
        sel = next((i for i, r in enumerate(rows) if r["selected"]), 0)
        on = [1.0 if r.get("on") else 0.0 for r in rows]
        ratio = [r["ratio"] or 0.0 for r in rows]
        self._goal = (float(sel), on, ratio)
        if snap or len(st.row_on) != len(rows):
            st.sel_pos, st.row_on, st.row_ratio = float(sel), on, ratio
        else:
            self._at = time.monotonic()
            self._timer.start()

    def stop(self):
        self._timer.stop()

    def _step(self):
        now = time.monotonic()
        k = 1.0 - math.exp(-min(0.05, now - self._at) * self.RATE)
        self._at = now
        st, busy = self.state, False

        def ease(cur, goal):
            nonlocal busy
            if abs(goal - cur) < self.SETTLED:
                return goal
            busy = True
            return cur + (goal - cur) * k

        sel, on, ratio = self._goal
        st.sel_pos = ease(st.sel_pos, sel)
        st.row_on = [ease(c, g) for c, g in zip(st.row_on, on)]
        st.row_ratio = [ease(c, g) for c, g in zip(st.row_ratio, ratio)]
        self.on_change()
        if not busy:
            self._timer.stop()
