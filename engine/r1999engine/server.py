import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

from . import PROTOCOL_VERSION, __version__
from .config import LANGUAGES, EngineConfig, data_dir
from .glossary import Glossary
from .model import Downloader, is_ready, model_dir
from .ocr import Frame
from .session import Session
from .translate import FakeEngine, NLLBEngine, TextTranslator


class Host:
    def __init__(self, fake=False, config_path=None, glossary_path=None):
        self.cfg = EngineConfig(config_path)
        self.glossary = Glossary(glossary_path or data_dir() / "glossary.json")
        self.session = Session(self.cfg, self.glossary)
        self.fake = fake
        self.downloader = Downloader()
        self.state = "starting"
        self.error = ""
        self._lock = threading.Lock()

    def start(self):
        self.session.start()
        threading.Thread(target=self._boot, daemon=True).start()

    def _boot(self):
        try:
            from .ocr import DialogReader

            self.session.reader = DialogReader(self.glossary)
            if self.fake:
                self._attach(FakeEngine())
            elif is_ready(model_dir(self.cfg["model_repo"])):
                self._load_model()
            else:
                self.state = "model_missing"
        except Exception as exc:
            self.state, self.error = "error", str(exc)

    def _load_model(self):
        self.state = "loading"
        try:
            engine = NLLBEngine(
                model_dir(self.cfg["model_repo"]), self.cfg["threads"], self.cfg["device"]
            )
            self._attach(engine)
        except Exception as exc:
            self.state, self.error = "error", str(exc)

    def _attach(self, engine):
        self.session.translator = TextTranslator(engine, self.glossary, persist=not self.fake)
        self.state = "ready"

    def download_model(self):
        self.state = "downloading"
        self.downloader.start(
            self.cfg["model_repo"], on_done=lambda: threading.Thread(target=self._load_model, daemon=True).start()
        )

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
        w, h = int(headers["X-Width"]), int(headers["X-Height"])
        if headers.get("X-Format", "bgr") == "png":
            img = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_COLOR)
        else:
            img = np.frombuffer(body, np.uint8).reshape(h, w, 3)
        region = tuple(float(v) for v in headers.get("X-Region", "0.19,0.78,0.90,1.0").split(","))
        frame = Frame(img, int(headers["X-Client-W"]), int(headers["X-Client-H"]), region)
        return self.session.process_frame(frame)


def make_handler(host):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _send(self, payload, status=200):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            return self.rfile.read(int(self.headers.get("Content-Length") or 0))

        def do_GET(self):
            if self.path == "/info":
                self._send(host.info())
            elif self.path == "/view":
                self._send(host.session.view())
            elif self.path == "/config":
                self._send(host.cfg.snapshot())
            else:
                self._send({"error": "not found"}, 404)

        def do_POST(self):
            body = self._body()
            try:
                if self.path == "/frame":
                    self._send(host.frame(body, self.headers))
                elif self.path == "/config":
                    changed = host.cfg.update(json.loads(body or b"{}"))
                    if {"target_lang", "mode", "word_level", "name_style"} & set(changed):
                        host.session.reset()
                    self._send({"changed": changed})
                elif self.path == "/reset":
                    host.session.reset()
                    self._send({"ok": True})
                elif self.path == "/model/download":
                    host.download_model()
                    self._send({"ok": True})
                elif self.path == "/model/cancel":
                    host.downloader.cancel()
                    self._send({"ok": True})
                elif self.path == "/shutdown":
                    self._send({"ok": True})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                else:
                    self._send({"error": "not found"}, 404)
            except Exception as exc:
                self._send({"error": str(exc)}, 400)

    return Handler


def serve(host, port):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(host))
    server.daemon_threads = True
    host.start()
    try:
        server.serve_forever()
    finally:
        host.session.stop()
        if host.session.translator:
            host.session.translator.flush()
