import threading

from .. import PROTOCOL_VERSION, __version__
from ..config import EngineConfig
from ..glossary import Glossary
from ..languages import ERRORS, LANGUAGES, model_repo
from ..model import ArgosDownloader, Downloader, argos_dir, is_argos_ready, is_ready, model_dir
from ..session import Session
from ..storage import data_dir
from ..translate import ArgosEngine, FakeEngine, NLLBEngine, TextTranslator
from .frames import decode_frame

RESET_KEYS = {"target_lang", "translator", "mode", "word_level", "name_style"}
ENGINE_KEYS = {"target_lang", "translator"}
MEDIA_PACK = "Install the Media Feature Pack from Microsoft (Windows N editions) and restart. OpenCV could not be loaded: %s"


def explain(exc):
    """OpenCV needs Windows Media Foundation, which is missing on Windows N editions, and it fails with a cryptic message."""
    text = str(exc)
    if isinstance(exc, ImportError) and (getattr(exc, "name", None) == "cv2" or "cv2" in text):
        return MEDIA_PACK % text
    return text


class Host:
    """Owns the engine state: config, glossary, OCR and translation session, and the model downloads."""

    def __init__(self, fake=False, config_path=None, glossary_path=None):
        self.cfg = EngineConfig(config_path)
        self.glossary = Glossary(glossary_path or data_dir() / "glossary.json")
        self.session = Session(self.cfg, self.glossary)
        self.fake = fake
        self.downloaders = {"nllb": Downloader(), "argos": ArgosDownloader()}
        self._downloading = "nllb"
        self.state = "starting"
        self.error = ""
        self._engines = {}

    @property
    def downloader(self):
        return self.downloaders[self._downloading]

    def need(self):
        """What the target language is translated with: ("argos", language code) or ("nllb", model repo).

        The Argos translator only exists for languages that have an Argos model, the others keep using NLLB."""
        lang = self.cfg["target_lang"]
        argos = LANGUAGES[lang]["argos"]
        if self.cfg["translator"] == "argos" and argos:
            return ("argos", argos)
        return ("nllb", model_repo(lang, self.cfg["model_repo"]))

    def repo(self):
        kind, key = self.need()
        return key if kind == "nllb" else "argos:en-%s" % key

    def start(self):
        self.session.start()
        threading.Thread(target=self._boot, daemon=True).start()

    def _fail(self, exc):
        self.state, self.error = "error", explain(exc)

    def _boot(self):
        try:
            from ..ocr import DialogReader

            self.session.reader = DialogReader(self.glossary)
            self._select_engine()
        except Exception as exc:
            self._fail(exc)

    @staticmethod
    def _on_disk(need):
        kind, key = need
        return is_ready(model_dir(key)) if kind == "nllb" else is_argos_ready(argos_dir(key))

    def _build(self, need):
        kind, key = need
        if kind == "nllb":
            return NLLBEngine(model_dir(key), self.cfg["threads"], self.cfg["device"], self.cfg["beam_size"])
        return ArgosEngine(argos_dir(key), self.cfg["threads"], self.cfg["beam_size"])

    def _select_engine(self):
        """Uses the engine of the target language: attach it, load it from disk, or report the model as missing."""
        if self.fake:
            if self.session.translator is None:
                self._attach(FakeEngine())
            return
        need = self.need()
        if need in self._engines:
            self._attach(self._engines[need])
            return
        self._detach()
        if self._on_disk(need):
            self.state = "loading"
            threading.Thread(target=self._load_model, args=(need,), daemon=True).start()
        else:
            self.state = "model_missing"

    def _load_model(self, need):
        self.state = "loading"
        try:
            self._engines[need] = self._build(need)
        except Exception as exc:
            self._fail(exc)
            return
        self._select_engine()

    def _detach(self):
        old, self.session.translator = self.session.translator, None
        if old:
            old.flush()

    def _attach(self, engine):
        old = self.session.translator
        if old:
            old.flush()
        self.session.translator = TextTranslator(engine, self.glossary, persist=not self.fake)
        self.state, self.error = "ready", ""

    def download_model(self):
        need = self.need()
        self._downloading = need[0]
        self.state = "downloading"
        self.downloader.start(
            need[1], on_done=lambda: threading.Thread(target=self._load_model, args=(need,), daemon=True).start()
        )

    def update_config(self, values):
        changed = self.cfg.update(values)
        if RESET_KEYS & set(changed):
            self.session.reset()
        if ENGINE_KEYS & set(changed) and self.session.reader is not None:
            self._select_engine()
        return changed

    def info(self):
        if self.state == "downloading" and self.downloader.state in ("error", "cancelled"):
            self.state, self.error = "model_missing", self.downloader.error
        return {
            "protocol": PROTOCOL_VERSION,
            "version": __version__,
            "state": self.state,
            "error": self.error,
            "download": self.downloader.progress(),
            "languages": {k: v["name"] for k, v in LANGUAGES.items()},
            "scripts": {k: v["script"] for k, v in LANGUAGES.items()},
            "fonts": {k: v["fonts"] for k, v in LANGUAGES.items()},
            "language_errors": ERRORS,
            "translator": self.need()[0],
            "model_repo": self.repo(),
            "config": self.cfg.snapshot(),
        }

    def frame(self, body, headers):
        return self.session.process_frame(decode_frame(body, headers))

    def close(self):
        self.session.stop()
        if self.session.translator:
            self.session.translator.flush()
