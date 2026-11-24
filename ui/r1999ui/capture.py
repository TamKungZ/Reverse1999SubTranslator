import numpy as np


class ScreenGrabber:
    def __init__(self):
        self._sct = None

    def grab(self, state, region):
        import mss

        if self._sct is None:
            self._sct = mss.mss()
        x0 = state.x + int(region[0] * state.w)
        y0 = state.y + int(region[1] * state.h)
        x1 = state.x + int(region[2] * state.w)
        y1 = state.y + int(region[3] * state.h)
        if x1 - x0 < 50 or y1 - y0 < 20:
            return None
        shot = self._sct.grab({"left": x0, "top": y0, "width": x1 - x0, "height": y1 - y0})
        return np.ascontiguousarray(np.asarray(shot)[:, :, :3])
