import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .common_words import BASIC, MEDIUM

DATA = Path(__file__).parent / "data"

NOT_NAMES = frozenset(
    "monday tuesday wednesday thursday friday saturday sunday january february march april may june july august "
    "september october november december i god".split()
)
_COMMON = frozenset(BASIC) | frozenset(MEDIUM)

_PLACEHOLDER = re.compile(r"[\[\(（［【]\s*(\d{1,2})\s*[\]\)）］】]")
_UNKNOWN_NAME = re.compile(r"(?<=[a-z,;:] )([A-Z][a-z]{2,}(?: [A-Z][a-z]{2,})*)")


@dataclass
class Span:
    start: int
    end: int
    canon: str
    kind: str


@dataclass
class Item:
    idx: int
    orig: str
    kind: str
    shown: str


class Glossary:
    def __init__(self, user_path=None):
        self.names = {}
        self.terms = {}
        self.resolver = None
        self._load(DATA / "glossary.json")
        if user_path:
            self._load(Path(user_path))
        self._compile()

    def _load(self, path):
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for key, target in (("names", self.names), ("terms", self.terms)):
            for canon, forms in raw.get(key, {}).items():
                if isinstance(forms, str):
                    forms = {"th": forms}
                target[canon] = dict(forms)

    def _compile(self):
        keys = [(k, "name") for k in self.names if len(k) > 1] + [(k, "term") for k in self.terms]
        keys.sort(key=lambda kv: -len(kv[0]))
        self._kind_of = {k: kind for k, kind in keys}
        if keys:
            alt = "|".join(re.escape(k) for k, _ in keys)
            self._rx = re.compile(r"(?<![A-Za-z0-9])(" + alt + r")(?![A-Za-z0-9])")
        else:
            self._rx = None

    def canonical_speaker(self, raw):
        raw = raw.strip()
        if not raw:
            return None
        lowered = {n.lower(): n for n in self.names}
        if raw.lower() in lowered:
            return lowered[raw.lower()]
        if len(raw) <= 2:
            return None
        hit = difflib.get_close_matches(raw.lower(), list(lowered), n=1, cutoff=0.7)
        return lowered[hit[0]] if hit else None

    def display(self, canon, kind, lang):
        table = self.names if kind == "name" else self.terms
        entry = table.get(canon)
        if entry and lang in entry:
            return entry[lang]
        if kind == "name" and self.resolver:
            return self.resolver(canon, lang)
        return canon

    def spans(self, text):
        found = []
        if self._rx:
            for m in self._rx.finditer(text):
                found.append(Span(m.start(1), m.end(1), m.group(1), self._kind_of[m.group(1)]))
        for m in _UNKNOWN_NAME.finditer(text):
            words = m.group(1).split(" ")
            if words[0].lower() in _COMMON or words[0].lower() in NOT_NAMES:
                continue
            if any(m.start(1) < s.end and m.end(1) > s.start for s in found):
                continue
            found.append(Span(m.start(1), m.end(1), m.group(1), "name"))
        found.sort(key=lambda s: s.start)
        return found

    def protect(self, text, lang):
        out, items, pos = [], [], 0
        for i, span in enumerate(self.spans(text), start=1):
            out.append(text[pos : span.start])
            out.append("[%d]" % i)
            items.append(
                Item(i, text[span.start : span.end], span.kind, self.display(span.canon, span.kind, lang))
            )
            pos = span.end
        out.append(text[pos:])
        return "".join(out), items

    @staticmethod
    def restore(translated, items):
        by_idx = {it.idx: it for it in items}
        seen, parts, pos = set(), [], 0
        for m in _PLACEHOLDER.finditer(translated):
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

    @staticmethod
    def mark(translated, items):
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
