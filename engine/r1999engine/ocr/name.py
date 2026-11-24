import re
from typing import NamedTuple

import cv2
import numpy as np

from .glyphs import first_glyph_height, hex_color

NAME_MIN_CAP = 0.015  # of client height: a real speaker name has glyphs about 0.028 tall
NAME_SCALES = (2, 3)  # the detector is sensitive to glyph size, some names only read at 3x
NAME_MIN_SCORE = 0.3


class NameRead(NamedTuple):
    text: str
    score: float
    bbox: tuple
    info: dict


NO_NAME = NameRead("", 0.0, None, None)


def plausible_name(bbox, info, ch):
    """Scenery in the name band (bright floor, lamps) can produce an ink box and even a guessed name."""
    if bbox is None or not info:
        return False
    return info["cap"] >= NAME_MIN_CAP * ch


def _canvas(inv, scale):
    big = cv2.resize(inv, (inv.shape[1] * scale, inv.shape[0] * scale), interpolation=cv2.INTER_LANCZOS4)
    pad = 30
    canvas = cv2.copyMakeBorder(big, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)
    return cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)


def _inverted_crop(lum, peak, box):
    y0, y1, x0, x1 = box
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
    return inv, single


def read_name(rows, zone):
    lum = zone.mean(axis=2)
    peak = float(lum.max())
    if peak < 120:
        return NO_NAME
    mask = lum > max(110.0, peak * 0.5)
    if int(mask.sum()) < 25:
        return NO_NAME
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    info = {
        "cap": first_glyph_height(mask[y0 : y1 + 1, x0 : x1 + 1]),
        "color": hex_color(zone[lum > peak * 0.85].mean(axis=0)),
    }
    inv, single = _inverted_crop(lum, peak, (y0, y1, x0, x1))
    found = []
    for scale in NAME_SCALES:
        found = rows.rows(_canvas(inv, scale))
        if found:
            break
    bbox = (int(x0), int(y0), int(x1), int(y1))
    if not found:
        return NameRead("", 0.0, bbox, info)
    text = " ".join(r[0] for r in found).strip()
    score = min(r[1] for r in found)
    if single:
        letters = re.findall(r"[A-Za-z]", text)
        text = letters[0].upper() if letters else ""
    text = re.sub(r"[^A-Za-z0-9 .'\-?!]", "", text).strip()
    return NameRead(text, score, bbox, info)


class NameReader:
    """Reads the speaker name band, skipping the OCR when the band has not changed."""

    def __init__(self, rows):
        self.rows = rows
        self._key = None
        self._last = NO_NAME

    def read(self, zone, client_h):
        key = zone[::4, ::4].astype(np.int16)
        if self._key is not None and key.shape == self._key.shape and np.abs(key - self._key).mean() < 1.5:
            return self._last
        result = read_name(self.rows, zone)
        if not plausible_name(result.bbox, result.info, client_h):
            result = NO_NAME
        elif result.text and result.score < NAME_MIN_SCORE:
            result = result._replace(text="")
        self._key, self._last = key, result
        return result
