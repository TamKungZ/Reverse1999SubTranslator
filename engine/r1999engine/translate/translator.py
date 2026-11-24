import re
import threading

from ..languages import LANGUAGES
from ..storage import data_dir
from ..textutil import split_sentences
from .cache import Cache
from .chips import build_chips, clean_meaning

THAI = re.compile(r"[฀-๿]")
SENTENCE_CACHE_SIZE = 200


class TextTranslator:
    def __init__(self, engine, glossary, persist=True):
        self.engine = engine
        self.glossary = glossary
        self.glossary.resolver = self.transliterate
        self.lock = threading.Lock()
        self.words_cache = Cache(data_dir() / "word_cache.json" if persist else None)
        self.names_cache = Cache(data_dir() / "name_cache.json" if persist else None)
        self.sentence_cache = {}

    def flush(self):
        self.words_cache.flush()
        self.names_cache.flush()

    def _translate(self, texts, lang):
        with self.lock:
            return self.engine.translate(texts, lang)

    def transliterate(self, name, lang):
        if not LANGUAGES[lang]["native_names"]:
            return name
        key = "%s|%s" % (lang, name)
        cached = self.names_cache.get(key)
        if cached is not None:
            return cached
        result = name
        try:
            out = self._translate([name], lang)[0].strip().rstrip(".。")
            ok = bool(THAI.search(out)) if lang == "th" else not re.fullmatch(r"[\x00-\x7f]*", out)
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
        joined = join.join(self._translate(split_sentences(protected) or [protected], lang))
        if not items:
            segments = [(joined, None)]
        else:
            segments = self.glossary.restore(joined, items)
            if segments is None:
                outs = self._translate(split_sentences(text) or [text], lang)
                segments = self.glossary.mark(join.join(outs), items)
        if len(self.sentence_cache) > SENTENCE_CACHE_SIZE:
            self.sentence_cache.clear()
        self.sentence_cache[key] = segments
        return segments

    def meanings(self, words, lang):
        keys = {w: "%s|%s" % (lang, w) for w in words}
        missing = [w for w in words if self.words_cache.get(keys[w]) is None]
        if missing:
            for w, out in zip(missing, self._translate(missing, lang)):
                self.words_cache.put(keys[w], clean_meaning(out))
        return {w: self.words_cache.get(keys[w]) or w for w in words}

    def chips(self, text, lang, level, limit=80):
        return build_chips(text, self.glossary, lang, level, lambda words: self.meanings(words, lang), limit)
