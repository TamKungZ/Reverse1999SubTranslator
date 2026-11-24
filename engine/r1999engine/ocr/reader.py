import numpy as np

from ..textutil import clean_ocr
from .name import NameReader
from .rows import RowReader
from .text import read_text
from .types import DialogRead

NAME_ZONE_WIDTH = 0.45


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
        read = DialogRead(style={})
        text_rows = read_text(self.rows, img[nb1:, :, :]) if nb1 < rh else []
        if not text_rows:
            return read
        text_top = self._fill_text(read, text_rows, x0_px, y0_px + nb1, ch, cw)
        if nb1 > nb0:
            zone = img[nb0:nb1, : int(rw * NAME_ZONE_WIDTH), :]
            self._fill_name(read, self.names.read(zone, ch), x0_px, y0_px + nb0, text_top, ch, cw)
        return read

    @staticmethod
    def _fill_text(read, rows, x0_px, top_px, ch, cw):
        style = read.style
        read.text = clean_ocr(" ".join(r.text for r in rows))
        text_top = top_px + min(r.top for r in rows)
        read.top_y = text_top / ch
        style["text_ink_h"] = max(r.ink_h for r in rows) / ch
        style["text_left"] = float((x0_px + min(r.left for r in rows)) / cw)
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
