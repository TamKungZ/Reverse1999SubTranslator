import json
import threading
import urllib.request
from pathlib import Path

from .config import data_dir

REQUIRED = ("config.json", "model.bin", "sentencepiece.bpe.model")


def model_dir(repo):
    return data_dir() / "models" / repo.replace("/", "__")


def is_ready(directory):
    directory = Path(directory)
    if not all((directory / name).is_file() for name in REQUIRED):
        return False
    return any((directory / n).is_file() for n in ("shared_vocabulary.json", "shared_vocabulary.txt"))


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
        self._thread = threading.Thread(target=self._run, args=(repo, on_done), daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def _run(self, repo, on_done):
        try:
            dest = model_dir(repo)
            dest.mkdir(parents=True, exist_ok=True)
            api = "https://huggingface.co/api/models/%s?blobs=true" % repo
            with urllib.request.urlopen(api, timeout=30) as resp:
                info = json.load(resp)
            wanted = [
                s
                for s in info.get("siblings", [])
                if s["rfilename"] in REQUIRED or s["rfilename"].startswith("shared_vocabulary")
            ]
            self.total = sum(int(s.get("size") or 0) for s in wanted)
            for sib in wanted:
                self._fetch(repo, sib["rfilename"], dest)
            if not is_ready(dest):
                raise RuntimeError("model files are incomplete")
            self.state = "done"
            if on_done:
                on_done()
        except Exception as exc:
            self.state = "cancelled" if self._cancel.is_set() else "error"
            self.error = str(exc)

    def _fetch(self, repo, name, dest):
        target = dest / name
        part = dest / (name + ".part")
        self.file = name
        url = "https://huggingface.co/%s/resolve/main/%s" % (repo, name)
        start = part.stat().st_size if part.exists() else 0
        req = urllib.request.Request(url)
        if start:
            req.add_header("Range", "bytes=%d-" % start)
        with urllib.request.urlopen(req, timeout=60) as resp:
            if start and resp.status != 206:
                start = 0
            mode = "ab" if start else "wb"
            self.done += start
            with open(part, mode) as fh:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    if self._cancel.is_set():
                        raise RuntimeError("cancelled")
                    fh.write(chunk)
                    self.done += len(chunk)
        part.replace(target)
