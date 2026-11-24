from pathlib import Path

from ..storage import data_dir

REQUIRED = ("config.json", "model.bin", "sentencepiece.bpe.model")
VOCABULARY = ("shared_vocabulary.json", "shared_vocabulary.txt")


def model_dir(repo):
    return data_dir() / "models" / repo.replace("/", "__")


def is_ready(directory):
    directory = Path(directory)
    if not all((directory / name).is_file() for name in REQUIRED):
        return False
    return any((directory / n).is_file() for n in VOCABULARY)
