import re
from typing import NamedTuple

import numpy as np

from .glyphs import hex_color


class TextRow(NamedTuple):
    text: str
    score: float
    x0: int
    y0: int
    x1: int
    y1: int
    ink_h: int
    top: int
    left: int
    color: str


MIN_SCORE = 0.5


def read_text(rows, zone, min_score=MIN_SCORE):
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
    out = []
    for t, s, a, b, c, d in rows.rows_by_line(zone[y0:y1, x0:x1], mask[y0:y1, x0:x1]):
        if s < min_score or not re.search(r"[A-Za-z]", t):
            continue
        ax, ay, bx, by = x0 + a, y0 + b, x0 + c, y0 + d
        sub = zone[ay:by, ax:bx]
        sub_lum = sub.mean(axis=2)
        pk = float(sub_lum.max())
        ink = sub_lum > max(90.0, pk * 0.6)
        ink_rows = np.where(ink.sum(axis=1) >= 2)[0]
        ink_cols = np.where(ink.any(axis=0))[0]
        if not len(ink_rows) or not len(ink_cols):
            continue
        color = sub[sub_lum > pk * 0.85].mean(axis=0)
        out.append(
            TextRow(t, s, ax, ay, bx, by, int(ink_rows.max() - ink_rows.min() + 1), ay + int(ink_rows.min()),
                    ax + int(ink_cols.min()), hex_color(color))
        )
    return out
