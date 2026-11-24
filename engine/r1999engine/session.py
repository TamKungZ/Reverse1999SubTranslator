import threading
import time
from collections import Counter, deque
from dataclasses import dataclass

import numpy as np

from .textutil import norm, similar, trim_partial_word
from .translate import add_breaks


DEFAULT_STYLE = {
    "text_ink_h": 33 / 1080,
    "name_cap": 31 / 1080,
    "text_left": 412 / 1920,
    "name_left": 426 / 1920,
    "name_to_text": 76 / 1080,
    "pitch": None,
    "text_color": "#e1dedc",
    "name_color": "#b4aba4",
}


RECENT_READS = 5
STYLE_WINDOW = 9
SAME_TEXT = 0.9
MEDIAN_STYLE = ("name_cap", "name_to_text", "text_left", "name_left", "pitch")


def _median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _grew(new, old):
    return len(new) > len(old) and new.startswith(old[: max(1, len(old) - 2)])


@dataclass
class _Request:
    seq: int
    text: str
    speaker: str
    speaker_known: bool
    top: float
    final: bool
    style: dict


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
        self._view = self._none_view()
        self._prev_small = None
        self._measured_h = None
        self._style_hist = {}
        self.style = dict(DEFAULT_STYLE)
        self._reset_state()

    def _merge_style(self, new):
        for key, value in (new or {}).items():
            if key == "text_ink_h":
                if 0.02 <= value <= 0.05:
                    self._measured_h = max(self._measured_h or 0.0, value)
                    self.style[key] = self._measured_h
            elif key in MEDIAN_STYLE:
                if value and value > 0:
                    hist = self._style_hist.setdefault(key, deque(maxlen=STYLE_WINDOW))
                    hist.append(value)
                    self.style[key] = _median(hist)
            else:
                self.style[key] = value

    def _reset_state(self):
        self.cur_norm = ""
        self.cur_text = ""
        self.cur_top = 0.0
        self.tops = deque(maxlen=RECENT_READS)
        self.recent = deque(maxlen=RECENT_READS)
        self.pending_norm = ""
        self.pending_n = 0
        self.votes = Counter()
        self.known = set()
        self.last_change = 0.0
        self.empty_since = None
        self.shown_norm = ""
        self.live_norm = ""
        self.live_t = 0.0

    def _none_view(self):
        return {
            "seq": self._seq,
            "kind": "none",
            "pending": False,
            "speaker": None,
            "segments": [],
            "chips": [],
            "anchor_top": 0.0,
            "source": "",
        }

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
            self._prev_small = None
            self._hide()

    def process_frame(self, frame):
        if not self.ready():
            return self.view()
        if not self._ocr_lock.acquire(blocking=False):
            return self.view()
        try:
            now = self.clock()
            small = frame.img[::8, ::8].mean(axis=2).astype(np.float32)
            prev = self._prev_small
            changed = prev is None or prev.shape != small.shape or float(np.abs(small - prev).mean()) > 0.8
            changed = changed or self.wants_read()
            self._prev_small = small
            if changed:
                self.reader.name_band = self.cfg["name_band"]
                self.observe(self.reader.read(frame), now)
            self.evaluate(now)
        finally:
            self._ocr_lock.release()
        return self.view()

    def wants_read(self):
        return self.pending_n > 0

    def observe(self, read, now):
        with self.lock:
            if not read.text:
                if self.empty_since is None:
                    self.empty_since = now
                return
            self.empty_since = None
            n = norm(read.text)
            if not n:
                return
            if not self.cur_norm:
                self._commit(read, n, now, keep_speaker=False)
            elif _grew(n, self.cur_norm):
                self._commit(read, n, now, keep_speaker=True)
            elif similar(n, self.cur_norm) >= SAME_TEXT:
                self.pending_norm, self.pending_n = "", 0
                self.recent.append(read.text)
                self._track(read)
            else:
                # a different text must show up in two reads in a row, so one garbled frame cannot hide a translation
                if self.pending_n and similar(n, self.pending_norm) >= SAME_TEXT:
                    self.pending_n += 1
                else:
                    self.pending_norm, self.pending_n = n, 1
                if self.pending_n >= 2:
                    self._commit(read, n, now, keep_speaker=False)

    def _commit(self, read, n, now, keep_speaker):
        self.cur_norm = n
        self.last_change = now
        self.pending_norm, self.pending_n = "", 0
        self.recent.clear()
        self.tops.clear()
        if not keep_speaker:
            self.votes = Counter()
            self.known = set()
        self.recent.append(read.text)
        self._track(read)

    def _track(self, read):
        counts = Counter(self.recent)
        self.cur_text = max(reversed(self.recent), key=lambda t: counts[t])
        self.tops.append(read.top_y)
        self.cur_top = _median(self.tops)
        self._merge_style(read.style)
        if read.speaker:
            self.votes[read.speaker] += 1
            if read.speaker_known:
                self.known.add(read.speaker)

    def evaluate(self, now):
        with self.lock:
            if self.empty_since is not None:
                if now - self.empty_since >= self.cfg["hide_ms"] / 1000.0:
                    self._reset_state()
                    self._hide()
                return
            if not self.cur_norm:
                return
            n = self.cur_norm
            if self.shown_norm and similar(n, self.shown_norm) < 0.9:
                self.shown_norm = ""
                self._hide()
            settled = now - self.last_change >= self.cfg["stable_ms"] / 1000.0
            if settled:
                if not self.shown_norm or _grew(n, self.shown_norm):
                    self.shown_norm = n
                    self._submit(self.cur_text, True)
            elif self.cfg["timing"] == "live":
                interval = self.cfg["live_interval_ms"] / 1000.0
                if n != self.live_norm and now - self.live_t >= interval:
                    partial = trim_partial_word(self.cur_text)
                    if partial:
                        self.live_norm = n
                        self.live_t = now
                        self._submit(partial, False)

    def _hide(self):
        self._seq += 1
        self._request = None
        self._view = self._none_view()

    def _speaker(self):
        if not self.votes:
            return "", False
        known = [(c, s) for s, c in self.votes.items() if s in self.known]
        pool = known or [(c, s) for s, c in self.votes.items()]
        pool.sort(reverse=True)
        speaker = pool[0][1]
        return speaker, speaker in self.known

    def _submit(self, text, final):
        speaker, known = self._speaker()
        self._seq += 1
        self._request = _Request(self._seq, text, speaker, known, self.cur_top, final, dict(self.style))
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
                view = self._none_view()
                view["error"] = str(exc)
            with self.lock:
                if req.seq == self._seq:
                    view["seq"] = req.seq
                    self._view = view

    def build_view(self, req):
        lang = self.cfg["target_lang"]
        tr = self.translator
        speaker = None
        if req.speaker:
            if req.speaker_known:
                shown = tr.speaker_display(req.speaker, lang, self.cfg["name_style"])
            else:
                shown = req.speaker
            speaker = {"raw": req.speaker, "display": shown, "known": req.speaker_known}
        view = {
            "seq": req.seq,
            "kind": "sentence" if self.cfg["mode"] == "sentence" else "words",
            "pending": not req.final,
            "speaker": speaker,
            "segments": [],
            "chips": [],
            "anchor_top": req.top,
            "source": req.text,
            "style": req.style,
        }
        if view["kind"] == "sentence":
            view["segments"] = [{"t": t, "k": k} for t, k in add_breaks(tr.sentence(req.text, lang), lang)]
        else:
            view["chips"] = tr.chips(req.text, lang, self.cfg["word_level"])
        return view
