import numpy as np

from ..textutil import clean_ocr, norm, similar
from .name import NameReader
from .rows import RowReader
from .text import read_text
from .types import DialogRead

NAME_ZONE_WIDTH = 0.45
READ_X0 = 0.19   # where the usual reading area starts, left of it are portraits and icons
EDGE_PX = 10
DIALOG_LEFT = 0.2146   # where in-game dialog lines start, the main menu centers its lines
DIALOG_TOLERANCE = 0.012
CENTER_TOLERANCE = 0.02
EDGE_INK = 40      # how much brighter than the line's background a pixel at the edge must be to count as ink
EDGE_MIN_PIXELS = 6
WIDE_MIN_SCORE = 0.3   # a long line is recognised with less confidence, it is checked against the first reading instead
WIDE_SAME = 0.8


def is_centered(left, right, cw):
    """Dialog lines start at a fixed place, the lines of the main menu are centered on the screen."""
    if abs(left - DIALOG_LEFT * cw) <= DIALOG_TOLERANCE * cw:
        return False
    return abs((left + right) / 2 - cw / 2) <= CENTER_TOLERANCE * cw


class DialogReader:
    def __init__(self, glossary):
        self.rows = RowReader()
        self.names = NameReader(self.rows)
        self.glossary = glossary
        self.name_band = (0.80, 0.86)

    def read(self, frame):
        img = frame.img
        ch, cw = float(frame.client_h), float(frame.client_w)
        y0_px = frame.region[1] * ch
        x0_px = frame.region[0] * cw
        rh, rw = img.shape[:2]
        nb0 = int(max(0, self.name_band[0] * ch - y0_px))
        nb1 = int(min(rh, self.name_band[1] * ch - y0_px))
        start = max(0, int((READ_X0 - frame.region[0]) * cw))
        read = DialogRead(style={})
        text_rows, offset = self._text_rows(img, nb1, start) if nb1 < rh else ([], 0)
        if not text_rows:
            return read
        text_top = self._fill_text(read, text_rows, x0_px + offset, y0_px + nb1, ch, cw)
        read.box = (
            offset + min(r.x0 for r in text_rows), nb1 + min(r.y0 for r in text_rows),
            offset + max(r.x1 for r in text_rows), nb1 + max(r.y1 for r in text_rows),
        )
        if nb1 > nb0:
            zone = img[nb0:nb1, start : start + int((rw - start) * NAME_ZONE_WIDTH), :]
            self._fill_name(read, self.names.read(zone, ch), x0_px + start, y0_px + nb0, text_top, ch, cw)
        return read

    def _text_rows(self, img, nb1, start):
        """Reads the usual area, and the whole picture only when a line runs past its left edge (centered lines)."""
        zone = img[nb1:, start:, :]
        rows = read_text(self.rows, zone)
        if rows and start > 0 and self._runs_past_left_edge(zone, rows):
            wide = read_text(self.rows, img[nb1:, :, :], WIDE_MIN_SCORE)
            if wide and self._extends(rows, wide):
                return wide, 0
        return rows, start

    @staticmethod
    def _extends(rows, wide):
        """The wide reading is the first one with more words, not something else that happened to be in the picture."""
        first, second = (norm(" ".join(r.text for r in group)) for group in (rows, wide))
        return len(second) >= len(first) and similar(first, second) >= WIDE_SAME

    @staticmethod
    def _runs_past_left_edge(zone, rows):
        """A line cut at the left edge leaves ink there, even a faint one while the text is fading in."""
        if min(r.left for r in rows) <= EDGE_PX:
            return True
        top, bottom = min(r.y0 for r in rows), max(r.y1 for r in rows)
        lum = zone[top:bottom].mean(axis=2)
        return int((lum[:, :EDGE_PX] > np.median(lum) + EDGE_INK).sum()) >= EDGE_MIN_PIXELS

    @staticmethod
    def _fill_text(read, rows, x0_px, top_px, ch, cw):
        style = read.style
        read.text = clean_ocr(" ".join(r.text for r in rows))
        text_top = top_px + min(r.top for r in rows)
        read.top_y = text_top / ch
        style["text_ink_h"] = max(r.ink_h for r in rows) / ch
        left, right = x0_px + min(r.left for r in rows), x0_px + max(r.x1 for r in rows)
        style["text_left"] = float(left / cw)
        style["text_align"] = "center" if is_centered(left, right, cw) else "left"
        style["text_center"] = float((left + right) / 2 / cw)
        style["text_color"] = rows[0].color
        if len(rows) >= 2:
            tops = sorted(r.top for r in rows)
            style["pitch"] = float(np.median(np.diff(tops)) / ch)
        return text_top

    def _fill_name(self, read, name, x0_px, top_px, text_top, ch, cw):
        style = read.style
        if name.bbox is not None:
            read.name_ink = True
            name_top = top_px + name.bbox[1]
            read.top_y = min(read.top_y, name_top / ch)
            if name.info and name.info["cap"]:
                style["name_cap"] = name.info["cap"] / ch
                style["name_color"] = name.info["color"]
            style["name_left"] = (x0_px + name.bbox[0]) / cw
            style["name_to_text"] = float((text_top - name_top) / ch)
        canon = self.glossary.canonical_speaker(name.text) if name.text else None
        if canon:
            read.speaker, read.speaker_known = canon, True
        elif len(name.text) >= 2:
            read.speaker = name.text
