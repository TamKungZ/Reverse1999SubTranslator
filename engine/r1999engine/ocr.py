import re
from dataclasses import dataclass

import cv2
import numpy as np

from .textutil import clean_ocr


@dataclass
class Frame:
    img: np.ndarray
    client_w: int
    client_h: int
    region: tuple


@dataclass
class DialogRead:
    text: str = ""
    speaker: str = ""
    speaker_known: bool = False
    top_y: float = 0.0
    name_ink: bool = False
    style: dict = None


def _hex(bgr):
    b, g, r = (int(round(float(v))) for v in bgr)
    return "#%02x%02x%02x" % (r, g, b)


def _first_glyph_height(mask):
    cols = mask.any(axis=0)
    if not cols.any():
        return 0
    start = int(np.argmax(cols))
    rest = ~cols[start:]
    end = start + (int(np.argmax(rest)) if rest.any() else len(rest))
    rows = np.where(mask[:, start:end].any(axis=1))[0]
    return int(rows.max() - rows.min() + 1) if len(rows) else 0


MIN_LINE_W = 500
NAME_MIN_CAP = 0.015   # of client height: a real speaker name has glyphs about 0.028 tall


def plausible_name(bbox, info, ch):
    """Scenery in the name band (bright floor, lamps) can produce an ink box and even a guessed name."""
    if bbox is None or not info:
        return False
    return info["cap"] >= NAME_MIN_CAP * ch


def line_cuts(mask):
    """Row indices that separate text lines in an ink mask, so the detector cannot merge close or wavy lines."""
    profile = mask.sum(axis=1).astype(float)
    if profile.max() <= 0:
        return []
    inked = profile >= 2
    spans, start = [], None
    for y, on in enumerate(inked):
        if on and start is None:
            start = y
        elif not on and start is not None:
            spans.append((start, y))
            start = None
    if start is not None:
        spans.append((start, len(inked)))
    tallest = max(b - a for a, b in spans)
    spans = [sp for sp in spans if (sp[1] - sp[0]) >= 0.4 * tallest]
    return [(a[1] + b[0]) // 2 for a, b in zip(spans, spans[1:])]


class DialogReader:
    def __init__(self, glossary):
        from rapidocr_onnxruntime import RapidOCR

        self.eng = RapidOCR()
        self.glossary = glossary
        self._name_key = None
        self._name_cache = ("", False, 0.0)

    def _recognize(self, crop):
        res, _ = self.eng.text_recognizer([np.ascontiguousarray(crop)])
        return res[0][0], float(res[0][1])

    def _rows(self, img):
        result, _ = self.eng(img, text_score=0.2)
        if not result:
            return []
        boxes = []
        for box, text, score in result:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            boxes.append([min(xs), min(ys), max(xs), max(ys), text, float(score)])
        boxes.sort(key=lambda b: (b[1] + b[3]) / 2)
        groups = []
        for b in boxes:
            cy = (b[1] + b[3]) / 2
            h = b[3] - b[1]
            if groups and abs(cy - groups[-1]["cy"]) < 0.6 * min(h, groups[-1]["h"]):
                groups[-1]["boxes"].append(b)
            else:
                groups.append({"cy": cy, "h": h, "boxes": [b]})
        rows = []
        for g in groups:
            bs = g["boxes"]
            x0 = int(max(0, min(b[0] for b in bs) - 3))
            y0 = int(max(0, min(b[1] for b in bs) - 3))
            x1 = int(min(img.shape[1], max(b[2] for b in bs) + 3))
            y1 = int(min(img.shape[0], max(b[3] for b in bs) + 3))
            if len(bs) > 1:
                text, score = self._recognize(img[y0:y1, x0:x1])
            else:
                text, score = bs[0][4], bs[0][5]
            rows.append((text, score, x0, y0, x1, y1))
        return rows

    def _text_rows(self, crop, mask):
        edges = [0] + line_cuts(mask) + [crop.shape[0]]
        rows = []
        for top, bottom in zip(edges, edges[1:]):
            cols = np.where(mask[top:bottom].any(axis=0))[0]
            if not len(cols):
                continue
            left = max(0, int(cols.min()) - 24)
            right = min(crop.shape[1], max(int(cols.max()) + 25, left + MIN_LINE_W))  # the detector misses short, narrow crops
            for t, s, a, b, c, d in self._rows(crop[top:bottom, left:right]):
                rows.append((t, s, a + left, b + top, c + left, d + top))
        return rows

    def _read_text(self, zone):
        lum = zone.mean(axis=2)
        peak = float(np.percentile(lum, 99.5))
        if peak < 90:
            return []
        mask = lum > max(90.0, peak * 0.55)
        if int(mask.sum()) < 80:
            return []
        ys, xs = np.where(mask)
        y0, y1 = max(0, ys.min() - 8), min(zone.shape[0], ys.max() + 9)
        x0, x1 = max(0, xs.min() - 8), min(zone.shape[1], xs.max() + 9)
        rows = self._text_rows(zone[y0:y1, x0:x1], mask[y0:y1, x0:x1])
        out = []
        for t, s, a, b, c, d in rows:
            if s < 0.5 or not re.search(r"[A-Za-z]", t):
                continue
            ax, ay, bx, by = x0 + a, y0 + b, x0 + c, y0 + d
            sub = zone[ay:by, ax:bx]
            sub_lum = sub.mean(axis=2)
            pk = float(sub_lum.max())
            ink = sub_lum > max(90.0, pk * 0.6)
            ys = np.where(ink.sum(axis=1) >= 2)[0]
            xs = np.where(ink.any(axis=0))[0]
            if not len(ys) or not len(xs):
                continue
            color = sub[sub_lum > pk * 0.85].mean(axis=0)
            out.append((t, s, ax, ay, bx, by, int(ys.max() - ys.min() + 1), ay + int(ys.min()), ax + int(xs.min()), _hex(color)))
        return out

    def _read_name(self, zone):
        lum = zone.mean(axis=2)
        peak = float(lum.max())
        if peak < 120:
            return "", 0.0, None, None
        mask = lum > max(110.0, peak * 0.5)
        if int(mask.sum()) < 25:
            return "", 0.0, None, None
        ys, xs = np.where(mask)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        info = {
            "cap": _first_glyph_height(mask[y0 : y1 + 1, x0 : x1 + 1]),
            "color": _hex(zone[lum > peak * 0.85].mean(axis=0)),
        }
        sub = lum[y0 : y1 + 1, x0 : x1 + 1]
        gray = np.clip((sub - lum.min()) / max(1.0, peak - lum.min()) * 255, 0, 255)
        inv = (255 - gray).astype(np.uint8)
        h, w = inv.shape
        single = w <= 1.3 * h
        if single:
            gap = max(2, w // 2)
            tiled = np.full((h, w * 3 + gap * 2), 255, np.uint8)
            for i in range(3):
                tiled[:, i * (w + gap) : i * (w + gap) + w] = inv
            inv = tiled
        rows = []
        for scale in (2, 3):  # the detector is sensitive to glyph size, some names only read at 3x
            big = cv2.resize(inv, (inv.shape[1] * scale, inv.shape[0] * scale), interpolation=cv2.INTER_LANCZOS4)
            pad = 30
            canvas = cv2.copyMakeBorder(big, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)
            canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
            rows = self._rows(canvas)
            if rows:
                break
        bbox = (int(x0), int(y0), int(x1), int(y1))
        if not rows:
            return "", 0.0, bbox, info
        text = " ".join(r[0] for r in rows).strip()
        score = min(r[1] for r in rows)
        if single:
            letters = re.findall(r"[A-Za-z]", text)
            text = letters[0].upper() if letters else ""
        text = re.sub(r"[^A-Za-z0-9 .'\-?!]", "", text).strip()
        return text, score, bbox, info

    def read(self, frame):
        img = frame.img
        ch, cw = float(frame.client_h), float(frame.client_w)
        y0_px = frame.region[1] * ch
        x0_px = frame.region[0] * cw
        rh, rw = img.shape[:2]
        nb0 = int(max(0, self.name_band[0] * ch - y0_px))
        nb1 = int(min(rh, self.name_band[1] * ch - y0_px))
        read = DialogRead(style={})
        style = read.style
        text_rows = self._read_text(img[nb1:, :, :]) if nb1 < rh else []
        text_top = None
        if text_rows:
            read.text = clean_ocr(" ".join(r[0] for r in text_rows))
            text_top = y0_px + nb1 + min(r[7] for r in text_rows)
            read.top_y = text_top / ch
            style["text_ink_h"] = max(r[6] for r in text_rows) / ch
            style["text_left"] = float((x0_px + min(r[8] for r in text_rows)) / cw)
            style["text_color"] = text_rows[0][9]
            if len(text_rows) >= 2:
                tops = sorted(r[7] for r in text_rows)
                style["pitch"] = float(np.median(np.diff(tops)) / ch)
        if text_rows and nb1 > nb0:
            name_zone = img[nb0:nb1, : int(rw * 0.45), :]
            key = name_zone[::4, ::4].astype(np.int16)
            if self._name_key is not None and key.shape == self._name_key.shape and np.abs(key - self._name_key).mean() < 1.5:
                raw, bbox, info = self._name_cache
            else:
                raw, score, bbox, info = self._read_name(name_zone)
                if not plausible_name(bbox, info, ch):
                    raw, bbox, info = "", None, None
                if raw and score < 0.3:
                    raw = ""
                self._name_key, self._name_cache = key, (raw, bbox, info)
            if bbox is not None:
                read.name_ink = True
                name_top = y0_px + nb0 + bbox[1]
                read.top_y = min(read.top_y, name_top / ch)
                if info and info["cap"]:
                    style["name_cap"] = info["cap"] / ch
                    style["name_color"] = info["color"]
                style["name_left"] = (x0_px + bbox[0]) / cw
                style["name_to_text"] = float((text_top - name_top) / ch)
            canon = self.glossary.canonical_speaker(raw) if raw else None
            if canon:
                read.speaker, read.speaker_known = canon, True
            elif len(raw) >= 2:
                read.speaker = raw
        return read

    @property
    def name_band(self):
        return getattr(self, "_name_band", (0.80, 0.86))

    @name_band.setter
    def name_band(self, value):
        self._name_band = tuple(value)
