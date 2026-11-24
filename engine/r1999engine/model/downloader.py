import json
import threading
import urllib.error
import urllib.request

from .. import __version__
from .paths import REQUIRED, is_ready, model_dir

CHUNK = 1 << 20
USER_AGENT = "R1999Translator/%s (+https://github.com/TamKungZ/Reverse1999SubTranslator)" % __version__


def request(url, headers=None):
    """A download request that says who is asking, some model hosts refuse the default Python agent."""
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})


class Downloader:
    def __init__(self):
        self.state = "idle"
        self.done = 0
        self.total = 0
        self.file = ""
        self.error = ""
        self._thread = None
        self._cancel = threading.Event()

    def progress(self):
        return {
            "state": self.state,
            "done": self.done,
            "total": self.total,
            "file": self.file,
            "error": self.error,
        }

    def start(self, repo, on_done=None):
        if self._thread and self._thread.is_alive():
            return
        self._cancel.clear()
        self.state, self.error, self.done, self.total = "downloading", "", 0, 0
        self._thread = threading.Thread(target=self._guarded, args=(repo, on_done), daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def _guarded(self, target, on_done):
        try:
            self._run(target)
            self.state = "done"
            if on_done:
                on_done()
        except Exception as exc:
            self.state = "cancelled" if self._cancel.is_set() else "error"
            self.error = str(exc)

    def _run(self, repo):
        dest = model_dir(repo)
        dest.mkdir(parents=True, exist_ok=True)
        wanted = self._wanted_files(repo)
        self.total = sum(int(s.get("size") or 0) for s in wanted)
        for sib in wanted:
            self._fetch(repo, sib["rfilename"], dest)
        if not is_ready(dest):
            raise RuntimeError("model files are incomplete")

    @staticmethod
    def _wanted_files(repo):
        api = "https://huggingface.co/api/models/%s?blobs=true" % repo
        with urllib.request.urlopen(request(api), timeout=30) as resp:
            info = json.load(resp)
        return [
            s
            for s in info.get("siblings", [])
            if s["rfilename"] in REQUIRED or s["rfilename"].startswith("shared_vocabulary")
        ]

    def _fetch(self, repo, name, dest):
        self.file = name
        part = dest / (name + ".part")
        self._stream("https://huggingface.co/%s/resolve/main/%s" % (repo, name), part)
        part.replace(dest / name)

    def _stream(self, url, part):
        """Downloads a file to `part`, resuming what an earlier try left there."""
        start = part.stat().st_size if part.exists() else 0
        req = request(url, {"Range": "bytes=%d-" % start} if start else None)
        try:
            resp = urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and start:
                return
            raise
        with resp:
            if start and resp.status != 206:
                start = 0
            if not self.total and resp.headers.get("Content-Length"):
                self.total = start + int(resp.headers["Content-Length"])
            mode = "ab" if start else "wb"
            self.done += start
            with open(part, mode) as fh:
                while True:
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    if self._cancel.is_set():
                        raise RuntimeError("cancelled")
                    fh.write(chunk)
                    self.done += len(chunk)
