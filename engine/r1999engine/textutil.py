import difflib
import re

ABBREV = {"mr", "mrs", "ms", "dr", "st", "prof", "sr", "jr", "vs", "etc"}


def norm(text):
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def similar(a, b):
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def clean_ocr(text):
    text = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("…", "...")
    )
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text


def split_sentences(text):
    tokens = text.split(" ")
    out, cur = [], []
    for i, tok in enumerate(tokens):
        cur.append(tok)
        if not re.search(r"[.!?][\"')\]]*$", tok):
            continue
        base = re.sub(r"[^A-Za-z]", "", tok).lower()
        if tok.endswith(".") and base in ABBREV:
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if nxt and not re.match(r"[\"'(\[]?[A-Z0-9\[]", nxt):
            continue
        out.append(" ".join(cur))
        cur = []
    if cur:
        out.append(" ".join(cur))
    return [s for s in out if s.strip()]


def trim_partial_word(text):
    if re.search(r"[.!?\"')]$", text):
        return text
    trimmed = re.sub(r"\s+\S*$", "", text)
    return trimmed if len(trimmed.split()) >= 2 else ""
