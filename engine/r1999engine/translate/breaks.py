def add_breaks(segments, lang):
    if lang != "th":
        return segments
    try:
        from pythainlp.tokenize import word_tokenize
    except ImportError:
        return segments
    out = []
    for i, (text, kind) in enumerate(segments):
        if kind is None and text.strip():
            text = "​".join(word_tokenize(text, engine="newmm", keep_whitespace=True))
        out.append(("​" + text if i else text, kind))
    return out
