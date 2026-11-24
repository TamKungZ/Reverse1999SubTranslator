import threading

from .. import PROTOCOL_VERSION, __version__
from ..config import EngineConfig
from ..glossary import Glossary
from ..languages import LANGUAGES
from ..model import Downloader, is_ready, model_dir
from ..session import Session
from ..storage import data_dir
from ..translate import FakeEngine, NLLBEngine, TextTranslator
from .frames import decode_frame


class Host:
    """Owns the engine state: config, glossary, OCR and translation session, and the model download."""

    def __init__(self, fake=False, config_path=None, glossary_path=None):
        self.cfg = EngineConfig(config_path)
        self.glossary = Glossary(glossary_path or data_dir() / "glossary.json")
        self.session = Session(self.cfg, self.glossary)
        self.fake = fake
        self.downloader = Downloader()
        self.state = "starting"
        self.error = ""

    def start(self):
        self.session.start()
        threading.Thread(target=self._boot, daemon=True).start()

    def _fail(self, exc):
        self.state, self.error = "error", str(exc)

    def _boot(self):
        try:
            from ..ocr import DialogReader

            self.session.reader = DialogReader(self.glossary)
            if self.fake:
                self._attach(FakeEngine())
            elif is_ready(model_dir(self.cfg["model_repo"])):
                self._load_model()
            else:
                self.state = "model_missing"
        except Exception as exc:
            self._fail(exc)

    def _load_model(self):
        self.state = "loading"
        try:
            engine = NLLBEngine(model_dir(self.cfg["model_repo"]), self.cfg["threads"], self.cfg["device"])
            self._attach(engine)
        except Exception as exc:
            self._fail(exc)

    def _attach(self, engine):
        self.session.translator = TextTranslator(engine, self.glossary, persist=not self.fake)
        self.state = "ready"

    def download_model(self):
        self.state = "downloading"
        self.downloader.start(
            self.cfg["model_repo"], on_done=lambda: threading.Thread(target=self._load_model, daemon=True).start()
        )

    def update_config(self, values):
        changed = self.cfg.update(values)
        if {"target_lang", "mode", "word_level", "name_style"} & set(changed):
            self.session.reset()
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
            "config": self.cfg.snapshot(),
        }

    def frame(self, body, headers):
        return self.session.process_frame(decode_frame(body, headers))

    def close(self):
        self.session.stop()
        if self.session.translator:
            self.session.translator.flush()
