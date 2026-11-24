import re

from ..common_words import is_common


def clean_meaning(text):
    text = text.strip().strip("\"'()[]").rstrip(".。!,")
    return text[:40]


def build_chips(text, glossary, lang, level, meanings, limit=80):
    """Splits text into word chips, each with its translated meaning. `meanings` maps a word list to {word: meaning}."""
    spans = glossary.spans(text)
    entries, pending = [], []
    for m in re.finditer(r"\S+", text):
        span = next((s for s in spans if s.start <= m.start() < s.end), None)
        if span:
            if m.start() == span.start:
                entries.append(
                    {"w": text[span.start : span.end], "m": glossary.display(span.canon, span.kind, lang), "k": span.kind}
                )
            continue
        token = m.group(0)
        core = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9'’-]+$", "", token)
        if not re.search(r"[A-Za-z]", core):
            continue
        base = re.sub(r"['’]s$", "", core).lower().strip("'-")
        entry = {"w": token, "m": "", "k": "word"}
        if not (is_common(base, level) or (level != "off" and len(base) < 3)):
            pending.append((entry, base))
        entries.append(entry)
    found = meanings(list(dict.fromkeys(b for _, b in pending))) if pending else {}
    for entry, base in pending:
        entry["m"] = found.get(base, base)
    return entries[:limit]
