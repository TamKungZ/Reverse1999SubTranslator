import numpy as np

MIN_LINE_W = 500
MAX_PIECE_W = 1100   # the recognizer gets unreliable on lines much wider than this
MIN_PIECE_W = 400
MIN_GAP = 6


def split_spans(line_mask):
    """Column spans of a line to read one by one: the line itself, or two halves cut at a gap between words."""
    ink = line_mask.any(axis=0)
    cols = np.where(ink)[0]
    if not len(cols):
        return []
    first, last = int(cols.min()), int(cols.max())
    if last - first + 1 <= MAX_PIECE_W:
        return [(first, last)]
    centre, best, start = (first + last) / 2, None, None
    for c in range(first + MIN_PIECE_W, last - MIN_PIECE_W + 1):
        if not ink[c]:
            start = c if start is None else start
        elif start is not None:
            if c - start >= MIN_GAP and (best is None or abs((start + c) / 2 - centre) < abs((best[0] + best[1]) / 2 - centre)):
                best = (start, c)
            start = None
    if best is None:
        return [(first, last)]
    return [(first, best[0] - 1), (best[1], last)]


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
