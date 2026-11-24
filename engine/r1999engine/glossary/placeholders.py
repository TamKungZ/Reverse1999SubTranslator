import re
from dataclasses import dataclass

PLACEHOLDER = re.compile(r"[\[\(（［【]\s*(\d{1,2})\s*[\]\)）］】]")


@dataclass
class Item:
    idx: int
    orig: str
    kind: str
    shown: str


def restore(translated, items):
    """Puts the shown forms back where the translator kept the [n] placeholders, or None if any was lost."""
    by_idx = {it.idx: it for it in items}
    seen, parts, pos = set(), [], 0
    for m in PLACEHOLDER.finditer(translated):
        it = by_idx.get(int(m.group(1)))
        if it is None:
            continue
        if m.start() > pos:
            parts.append((translated[pos : m.start()], None))
        parts.append((it.shown, it.kind))
        seen.add(it.idx)
        pos = m.end()
    if seen != set(by_idx):
        return None
    if pos < len(translated):
        parts.append((translated[pos:], None))
    return parts


def mark(translated, items):
    """Fallback when placeholders were lost: finds the shown or original forms in the translation and tags them."""
    forms = {}
    for it in items:
        forms[it.shown] = (it.kind, it.shown)
        forms[it.orig] = (it.kind, it.shown)
    keys = sorted((k for k in forms if k), key=len, reverse=True)
    if not keys:
        return [(translated, None)]
    rx = re.compile("|".join(re.escape(k) for k in keys))
    parts, pos = [], 0
    for m in rx.finditer(translated):
        if m.start() > pos:
            parts.append((translated[pos : m.start()], None))
        kind, shown = forms[m.group(0)]
        parts.append((shown, kind))
        pos = m.end()
    if pos < len(translated):
        parts.append((translated[pos:], None))
    return parts
