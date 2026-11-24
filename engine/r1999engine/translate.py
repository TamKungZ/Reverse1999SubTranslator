import json
import re
import threading
from pathlib import Path

from .common_words import is_common
from .config import LANGUAGES, data_dir
from .textutil import split_sentences

_THAI = re.compile(r"[฀-๿]")
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")


class NLLBEngine:
    def __init__(self, model_dir, threads=4, device="cpu"):
        import ctranslate2
        import sentencepiece

        self.sp = sentencepiece.SentencePieceProcessor()
        self.sp.Load(str(Path(model_dir) / "sentencepiece.bpe.model"))
        self.translator = ctranslate2.Translator(
            str(model_dir), device=device, inter_threads=1, intra_threads=threads, compute_type="auto"
        )

    def translate(self, texts, lang):
        target = LANGUAGES[lang]["nllb"]
        batch = [["eng_Latn"] + self.sp.encode(t, out_type=str) + ["</s>"] for t in texts]
        results = self.translator.translate_batch(
            batch,
            target_prefix=[[target]] * len(batch),
            beam_size=3,
            max_decoding_length=200,
            repetition_penalty=1.1,
            max_batch_size=16,
        )
        out = []
        for res in results:
            pieces = res.hypotheses[0]
            if pieces and pieces[0] == target:
                pieces = pieces[1:]
            out.append(self.sp.decode(pieces).strip())
        return out


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
            text = "\u200b".join(word_tokenize(text, engine="newmm", keep_whitespace=True))
        out.append(("\u200b" + text if i else text, kind))
    return out


class FakeEngine:
    def translate(self, texts, lang):
        return ["(%s) %s" % (lang, t) for t in texts]


class _Cache:
    def __init__(self, filename):
        self.path = data_dir() / filename
        self.data = {}
        self.dirty = 0
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value):
        self.data[key] = value
        self.dirty += 1
        if self.dirty >= 15:
            self.flush()

    def flush(self):
        if not self.dirty:
            return
        try:
            self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            self.dirty = 0
        except OSError:
            pass


def _clean_meaning(text):
    text = text.strip().strip("\"'()[]").rstrip(".。!,")
    return text[:40]


class TextTranslator:
    def __init__(self, engine, glossary, persist=True):
        self.engine = engine
        self.glossary = glossary
        self.glossary.resolver = self.transliterate
        self.lock = threading.Lock()
        self.words_cache = _Cache("word_cache.json") if persist else _Cache("_unused.json")
        self.names_cache = _Cache("name_cache.json") if persist else _Cache("_unused2.json")
        self.sentence_cache = {}
        if not persist:
            self.words_cache.flush = self.names_cache.flush = lambda: None

    def flush(self):
        self.words_cache.flush()
        self.names_cache.flush()

    def transliterate(self, name, lang):
        if not LANGUAGES[lang]["native_names"]:
            return name
        key = "%s|%s" % (lang, name)
        cached = self.names_cache.get(key)
        if cached is not None:
            return cached
        result = name
        try:
            with self.lock:
                out = self.engine.translate([name], lang)[0].strip().rstrip(".。")
            ok = bool(_THAI.search(out)) if lang == "th" else not re.fullmatch(r"[\x00-\x7f]*", out)
            if ok and len(out) <= len(name) * 2 + 6 and not re.search(r"\d", out):
                result = out
        except Exception:
            pass
        self.names_cache.put(key, result)
        return result

    def speaker_display(self, canon, lang, style):
        if style == "original" or not LANGUAGES[lang]["native_names"]:
            return canon
        shown = self.glossary.display(canon, "name", lang)
        if style == "both" and shown != canon:
            return "%s · %s" % (shown, canon)
        return shown

    def sentence(self, text, lang):
        key = (lang, text)
        if key in self.sentence_cache:
            return self.sentence_cache[key]
        join = LANGUAGES[lang]["join"]
        protected, items = self.glossary.protect(text, lang)
        with self.lock:
            outs = self.engine.translate(split_sentences(protected) or [protected], lang)
        joined = join.join(outs)
        if not items:
            segments = [(joined, None)]
        else:
            segments = self.glossary.restore(joined, items)
            if segments is None:
                with self.lock:
                    outs = self.engine.translate(split_sentences(text) or [text], lang)
                segments = self.glossary.mark(join.join(outs), items)
        if len(self.sentence_cache) > 200:
            self.sentence_cache.clear()
        self.sentence_cache[key] = segments
        return segments

    def meanings(self, words, lang):
        missing = [w for w in words if self.words_cache.get("%s|%s" % (lang, w)) is None]
        if missing:
            with self.lock:
                outs = self.engine.translate(missing, lang)
            for w, out in zip(missing, outs):
                self.words_cache.put("%s|%s" % (lang, w), _clean_meaning(out))
        return {w: self.words_cache.get("%s|%s" % (lang, w)) or w for w in words}

    def chips(self, text, lang, level, limit=80):
        spans = self.glossary.spans(text)
        entries, pending = [], []
        for m in re.finditer(r"\S+", text):
            span = next((s for s in spans if s.start <= m.start() < s.end), None)
            if span:
                if m.start() == span.start:
                    entries.append(
                        {"w": text[span.start : span.end], "m": self.glossary.display(span.canon, span.kind, lang), "k": span.kind}
                    )
                continue
            token = m.group(0)
            core = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9'\u2019-]+$", "", token)
            if not re.search(r"[A-Za-z]", core):
                continue
            base = re.sub(r"['\u2019]s$", "", core).lower().strip("'-")
            entry = {"w": token, "m": "", "k": "word"}
            if not (is_common(base, level) or (level != "off" and len(base) < 3)):
                pending.append((entry, base))
            entries.append(entry)
        found = self.meanings(list(dict.fromkeys(b for _, b in pending)), lang) if pending else {}
        for entry, base in pending:
            entry["m"] = found.get(base, base)
        return entries[:limit]
