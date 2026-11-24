MIN_LINE_W = 500


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
