import threading
import time

import numpy as np

from ..textutil import similar, trim_partial_word
from .style import StyleTracker
from .tracker import TextTracker, grew
from .view import Request, build_view, none_view

SAMPLE = 8
FRAME_CHANGE = 0.8      # brightness change of the whole picture that makes the engine look again when no text is on screen
TEXT_CHANGE = 1.5       # the same inside the box of the text that is on screen
IDLE_INTERVAL = 0.2     # without text on screen the picture is read at most this often
REFRESH_INTERVAL = 0.8  # with text on screen it is read at least this often
SETTLE_INTERVAL = 0.25
BOX_PAD = 2             # in samples
HIDE_SIMILARITY = 0.9


class Session:
    def __init__(self, cfg, glossary, reader=None, translator=None, clock=time.monotonic):
        self.cfg = cfg
        self.glossary = glossary
        self.reader = reader
        self.translator = translator
        self.clock = clock
        self.lock = threading.RLock()
        self._ocr_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._seq = 0
        self._request = None
        self._view = none_view(0)
        self._small = None
        self._read_small = None
        self._box = None
        self._last_read = 0.0
        self.style = StyleTracker()
        self.text = TextTracker(self.style)
        self._reset_state()

    def _reset_state(self):
        self.text.reset()
        self.shown_norm = ""
        self.live_norm = ""
        self.live_t = 0.0

    @property
    def cur_top(self):
        return self.text.cur_top

    def start(self):
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def ready(self):
        return self.reader is not None and self.translator is not None

    def view(self):
        with self.lock:
            return self._view

    def reset(self):
        with self.lock:
            self._reset_state()
            self._read_small = None
            self._box = None
            self._hide()

    def wants_read(self):
        return self.text.wants_read()

    def process_frame(self, frame):
        if not self.ready():
            return self.view()
        if not self._ocr_lock.acquire(blocking=False):
            return self.view()
        try:
            now = self.clock()
            self._small = frame.img[::SAMPLE, ::SAMPLE].mean(axis=2).astype(np.float32)
            if self.wants_read() or self._should_read(now):
                self._read(frame, now)
            self.evaluate(now)
        finally:
            self._ocr_lock.release()
        return self.view()

    def _read(self, frame, now):
        self.reader.name_band = self.cfg["name_band"]
        read = self.reader.read(frame)
        self._read_small, self._last_read = self._small, now
        self._box = self._sample_box(read.box, self._small.shape) if read.text else None
        self.observe(read, now)

    @staticmethod
    def _sample_box(box, shape):
        """The part of the picture to watch: from the top of the text to the bottom and across the whole width,
        because text that is being typed grows to the right and onto new lines, outside the box it had when it was read."""
        if box is None:
            return None
        return 0, max(0, box[1] // SAMPLE - BOX_PAD), shape[1], shape[0]

    def _should_read(self, now):
        """Looks at the picture again only when something that matters changed: the text on screen, or any new text."""
        small, ref = self._small, self._read_small
        if ref is None or ref.shape != small.shape:
            return True
        elapsed = now - self._last_read
        if self._box is None:
            return elapsed >= IDLE_INTERVAL and float(np.abs(small - ref).mean()) > FRAME_CHANGE
        settling = now - self.text.last_change < self.cfg["stable_ms"] / 1000.0 + REFRESH_INTERVAL
        if elapsed >= (SETTLE_INTERVAL if settling else REFRESH_INTERVAL):
            return True
        x0, y0, x1, y1 = self._box
        return float(np.abs(small[y0:y1, x0:x1] - ref[y0:y1, x0:x1]).mean()) > TEXT_CHANGE

    def observe(self, read, now):
        with self.lock:
            self.text.observe(read, now)

    def evaluate(self, now):
        with self.lock:
            text = self.text
            if text.empty_since is not None:
                if now - text.empty_since >= self.cfg["hide_ms"] / 1000.0:
                    self._reset_state()
                    self._hide()
                return
            if not text.cur_norm:
                return
            n = text.cur_norm
            if self.shown_norm and similar(n, self.shown_norm) < HIDE_SIMILARITY:
                self.shown_norm = ""
                self._hide()
            if now - text.last_change >= self.cfg["stable_ms"] / 1000.0:
                if not self.shown_norm or grew(n, self.shown_norm):
                    self.shown_norm = n
                    self._submit(text.cur_text, True)
            elif self.cfg["timing"] == "live":
                self._submit_partial(n, now)

    def _submit_partial(self, n, now):
        interval = self.cfg["live_interval_ms"] / 1000.0
        if n == self.live_norm or now - self.live_t < interval:
            return
        partial = trim_partial_word(self.text.cur_text)
        if partial:
            self.live_norm = n
            self.live_t = now
            self._submit(partial, False)

    def _hide(self):
        self._seq += 1
        self._request = None
        self._view = none_view(self._seq)

    def _submit(self, text, final):
        speaker, known = self.text.speaker()
        self._seq += 1
        self._request = Request(self._seq, text, speaker, known, self.text.cur_top, final, self.style.snapshot())
        self._wake.set()

    def _worker(self):
        while not self._stop.is_set():
            self._wake.wait(0.5)
            self._wake.clear()
            with self.lock:
                req = self._request
                self._request = None
            if req is None:
                continue
            try:
                view = self.build_view(req)
            except Exception as exc:
                view = none_view(self._seq)
                view["error"] = str(exc)
            with self.lock:
                if req.seq == self._seq:
                    view["seq"] = req.seq
                    self._view = view

    def build_view(self, req):
        return build_view(req, self.cfg, self.translator)
