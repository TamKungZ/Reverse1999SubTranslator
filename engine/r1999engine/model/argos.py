import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

from ..storage import data_dir
from .downloader import Downloader, request

INDEX_URL = "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
SOURCE = "en"
KEPT = ("sentencepiece.model",)


def argos_dir(code):
    return data_dir() / "argos" / ("%s_%s" % (SOURCE, code))


def is_argos_ready(directory):
    root = Path(directory)
    return (
        (root / "model" / "model.bin").is_file()
        and (root / "sentencepiece.model").is_file()
        and any((root / "model").glob("*vocabulary*"))
    )


def _version(text):
    return tuple(int(part) if part.isdigit() else 0 for part in str(text).split("."))


def pick_pack(index, code):
    """The newest English to `code` package in the Argos index, or None."""
    packs = [p for p in index if p.get("from_code") == SOURCE and p.get("to_code") == code]
    return max(packs, key=lambda p: _version(p.get("package_version", "0")), default=None)


def extract_pack(archive, destination):
    """Unpacks the model files of an .argosmodel archive. Anything that would land outside `destination` is refused."""
    destination = Path(destination)
    work = destination.with_name(destination.name + ".tmp")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    with zipfile.ZipFile(archive) as pack:
        for member in pack.infolist():
            _, _, relative = member.filename.partition("/")
            if member.is_dir() or not (relative in KEPT or relative.startswith("model/")):
                continue
            target = (work / relative).resolve()
            if not target.is_relative_to(work.resolve()):
                raise RuntimeError("the model package contains an unsafe path: %s" % member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with pack.open(member) as source, open(target, "wb") as sink:
                shutil.copyfileobj(source, sink)
    shutil.rmtree(destination, ignore_errors=True)
    work.rename(destination)


class ArgosDownloader(Downloader):
    """Downloads the Argos model from English to one language. `repo` is the language code, for example "th"."""

    def _run(self, code):
        self.file = "index"
        with urllib.request.urlopen(request(INDEX_URL), timeout=30) as resp:
            pack = pick_pack(json.load(resp), code)
        url = next((link for link in (pack or {}).get("links", []) if link.startswith("https://")), None)
        if not url:
            raise RuntimeError("Argos has no model from English to %s" % code)
        self.file = url.rsplit("/", 1)[-1]
        archive = argos_dir(code).with_name("%s_%s.argosmodel.part" % (SOURCE, code))
        archive.parent.mkdir(parents=True, exist_ok=True)
        self._stream(url, archive)
        extract_pack(archive, argos_dir(code))
        archive.unlink()
        if not is_argos_ready(argos_dir(code)):
            raise RuntimeError("model files are incomplete")
