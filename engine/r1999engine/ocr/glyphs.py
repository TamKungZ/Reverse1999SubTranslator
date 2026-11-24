import numpy as np


def hex_color(bgr):
    b, g, r = (int(round(float(v))) for v in bgr)
    return "#%02x%02x%02x" % (r, g, b)


def first_glyph_height(mask):
    cols = mask.any(axis=0)
    if not cols.any():
        return 0
    start = int(np.argmax(cols))
    rest = ~cols[start:]
    end = start + (int(np.argmax(rest)) if rest.any() else len(rest))
    rows = np.where(mask[:, start:end].any(axis=1))[0]
    return int(rows.max() - rows.min() + 1) if len(rows) else 0
