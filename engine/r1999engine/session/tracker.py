from collections import Counter, deque

from ..textutil import norm, similar
from .style import median

RECENT_READS = 5
SAME_TEXT = 0.9


def grew(new, old):
    return len(new) > len(old) and new.startswith(old[: max(1, len(old) - 2)])


class TextTracker:
    """Follows the text on screen across OCR reads and tells when it changed, grew or only looked different."""

    def __init__(self, style):
        self.style = style
        self.reset()

    def reset(self):
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

    def wants_read(self):
        return self.pending_n > 0

    def observe(self, read, now):
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
        elif grew(n, self.cur_norm):
            self._commit(read, n, now, keep_speaker=True)
        elif similar(n, self.cur_norm) >= SAME_TEXT:
            self.pending_norm, self.pending_n = "", 0
            self.recent.append(read.text)
            self._track(read)
        else:
            self._note_different(read, n, now)

    def _note_different(self, read, n, now):
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
        self.cur_top = median(self.tops)
        self.style.merge(read.style)
        if read.speaker:
            self.votes[read.speaker] += 1
            if read.speaker_known:
                self.known.add(read.speaker)

    def speaker(self):
        if not self.votes:
            return "", False
        known = [(c, s) for s, c in self.votes.items() if s in self.known]
        pool = known or [(c, s) for s, c in self.votes.items()]
        pool.sort(reverse=True)
        speaker = pool[0][1]
        return speaker, speaker in self.known
