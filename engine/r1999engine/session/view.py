from dataclasses import dataclass

from ..translate import add_breaks


@dataclass
class Request:
    seq: int
    text: str
    speaker: str
    speaker_known: bool
    top: float
    final: bool
    style: dict


def none_view(seq):
    return {
        "seq": seq,
        "kind": "none",
        "pending": False,
        "speaker": None,
        "segments": [],
        "chips": [],
        "anchor_top": 0.0,
        "source": "",
    }


def build_view(req, cfg, translator):
    lang = cfg["target_lang"]
    speaker = None
    if req.speaker:
        shown = translator.speaker_display(req.speaker, lang, cfg["name_style"]) if req.speaker_known else req.speaker
        speaker = {"raw": req.speaker, "display": shown, "known": req.speaker_known}
    view = {
        "seq": req.seq,
        "kind": "sentence" if cfg["mode"] == "sentence" else "words",
        "pending": not req.final,
        "speaker": speaker,
        "segments": [],
        "chips": [],
        "anchor_top": req.top,
        "source": req.text,
        "style": req.style,
    }
    if view["kind"] == "sentence":
        view["segments"] = [{"t": t, "k": k} for t, k in add_breaks(translator.sentence(req.text, lang), lang)]
    else:
        view["chips"] = translator.chips(req.text, lang, cfg["word_level"])
    return view
