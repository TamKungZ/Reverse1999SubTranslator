import difflib
import re
from pathlib import Path

from ..storage import read_json
from .placeholders import Item, mark, restore
from .spans import Span, unknown_name_spans

DATA = Path(__file__).resolve().parent.parent / "data"


class Glossary:
    restore = staticmethod(restore)
    mark = staticmethod(mark)

    def __init__(self, user_path=None):
        self.names = {}
        self.terms = {}
        self.resolver = None
        self._load(DATA / "glossary.json")
        if user_path:
            self._load(Path(user_path))
        self._compile()

    def _load(self, path):
        raw = read_json(path, {})
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
        found += unknown_name_spans(text, found)
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
