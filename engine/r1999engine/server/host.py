import threading

from .. import PROTOCOL_VERSION, __version__
from ..config import EngineConfig
from ..glossary import Glossary
from ..languages import ERRORS, LANGUAGES, model_repo
from ..model import Downloader, is_ready, model_dir
from ..session import Session
from ..storage import data_dir
from ..translate import FakeEngine, NLLBEngine, TextTranslator
from .frames import decode_frame

RESET_KEYS = {"target_lang", "mode", "word_level", "name_style"}
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
        self.downloader = Downloader()
        self.state = "starting"
        self.error = ""
        self._engines = {}

    def repo(self):
        """The model the current target language translates with."""
        return model_repo(self.cfg["target_lang"], self.cfg["model_repo"])

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

    def _select_engine(self):
        """Uses the engine of the target language: attach it, load it from disk, or report the model as missing."""
        if self.fake:
            if self.session.translator is None:
                self._attach(FakeEngine())
            return
        repo = self.repo()
        if repo in self._engines:
            self._attach(self._engines[repo])
            return
        self._detach()
        if is_ready(model_dir(repo)):
            self.state = "loading"
            threading.Thread(target=self._load_model, args=(repo,), daemon=True).start()
        else:
            self.state = "model_missing"

    def _load_model(self, repo):
        self.state = "loading"
        try:
            self._engines[repo] = NLLBEngine(model_dir(repo), self.cfg["threads"], self.cfg["device"], self.cfg["beam_size"])
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
        repo = self.repo()
        self.state = "downloading"
        self.downloader.start(
            repo, on_done=lambda: threading.Thread(target=self._load_model, args=(repo,), daemon=True).start()
        )

    def update_config(self, values):
        changed = self.cfg.update(values)
        if RESET_KEYS & set(changed):
            self.session.reset()
        if "target_lang" in changed and self.session.reader is not None:
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
            "model_repo": self.repo(),
            "config": self.cfg.snapshot(),
        }

    def frame(self, body, headers):
        return self.session.process_frame(decode_frame(body, headers))

    def close(self):
        self.session.stop()
        if self.session.translator:
            self.session.translator.flush()
