import re
import sys
from pathlib import Path

from .storage import data_dir, read_json

BUILTIN = Path(__file__).resolve().parent / "data" / "languages.json"
USER_FILE = "languages.json"

CODE = re.compile(r"[A-Za-z0-9_-]{1,16}")
NLLB_CODE = re.compile(r"[a-z]{3}_[A-Z][a-z]{3}")
MODEL_REPO = re.compile(r"[\w.-]+/[\w.-]+")
NO_SPACE_SCRIPTS = frozenset({"Jpan", "Hans", "Hant"})


def complete(code, entry):
    """Validates one language entry and fills in what can be derived from its NLLB code."""
    if not CODE.fullmatch(code):
        raise ValueError("the code must be 1 to 16 letters, digits, - or _")
    if not isinstance(entry, dict):
        raise ValueError("the entry must be an object")
    name, nllb, repo = entry.get("name"), entry.get("nllb"), entry.get("model_repo")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name is missing")
    if not isinstance(nllb, str) or not NLLB_CODE.fullmatch(nllb):
        raise ValueError("nllb must look like tha_Thai")
    if repo is not None and not (isinstance(repo, str) and MODEL_REPO.fullmatch(repo)):
        raise ValueError("model_repo must look like owner/name")
    fonts = entry.get("fonts", [])
    if not (isinstance(fonts, list) and all(isinstance(f, str) and f.strip() for f in fonts)):
        raise ValueError("fonts must be a list of font names")
    script = nllb.split("_")[1]
    return {
        "name": name,
        "nllb": nllb,
        "script": script,
        "join": entry.get("join", "" if script in NO_SPACE_SCRIPTS else " "),
        "native_names": bool(entry.get("native_names", script != "Latn")),
        "model_repo": repo,
        "fonts": fonts,
    }


def load_languages(paths):
    """Merges the language files in order, later files overriding earlier ones. Returns (languages, errors)."""
    languages, errors = {}, []
    for path in paths:
        raw = read_json(path, {})
        if not isinstance(raw, dict):
            errors.append("%s: the file must contain a JSON object" % Path(path).name)
            continue
        for code, entry in raw.items():
            if code.startswith("_"):
                continue
            try:
                languages[code] = complete(code, entry)
            except ValueError as exc:
                errors.append("%s: %s: %s" % (Path(path).name, code, exc))
    return languages, errors


LANGUAGES, ERRORS = load_languages([BUILTIN, data_dir() / USER_FILE])
for _line in ERRORS:
    print("language entry skipped, " + _line, file=sys.stderr)


def model_repo(lang, default):
    return LANGUAGES[lang]["model_repo"] or default
