import time

from ..capture import ScreenGrabber

IDLE_SLEEP = 0.2
ERROR_SLEEP = 1.0


class FrameLoop:
    """Grabs the subtitle area while the game is in front and feeds it to the engine."""

    def __init__(self, ui, client, tracker, region, stop, emit_view):
        self.ui, self.client, self.tracker = ui, client, tracker
        self.region = region
        self.stop = stop
        self.emit_view = emit_view

    def _active(self):
        state = self.tracker.state if self.tracker else None
        return state if self.ui["enabled"] and state and state.foreground and state.w > 0 else None

    def _go_idle(self):
        try:
            self.client.reset()
        except OSError:
            pass
        self.emit_view(None)

    def run(self):
        grabber = ScreenGrabber()
        last = (-1, "none")
        idle = True
        while not self.stop.is_set():
            state = self._active()
            if state is None:
                if not idle:
                    idle = True
                    last = (-1, "none")
                    self._go_idle()
                time.sleep(IDLE_SLEEP)
                continue
            idle = False
            try:
                img = grabber.grab(state, self.region)
                if img is None:
                    time.sleep(IDLE_SLEEP)
                    continue
                view = self.client.frame(img, state.w, state.h, self.region)
            except OSError:
                time.sleep(ERROR_SLEEP)
                continue
            key = (view["seq"], view["kind"])
            if key != last:
                last = key
                self.emit_view(view)
            time.sleep(self.ui["poll_ms"] / 1000.0)
