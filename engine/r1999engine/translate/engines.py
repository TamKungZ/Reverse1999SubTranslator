import os
from pathlib import Path

from ..languages import LANGUAGES

MAX_AUTO_THREADS = 8


def default_threads():
    return max(2, min(MAX_AUTO_THREADS, (os.cpu_count() or 4) * 2 // 3))


class NLLBEngine:
    tag = "nllb"

    def __init__(self, model_dir, threads=0, device="cpu", beam_size=2):
        self.beam_size = beam_size
        import ctranslate2
        import sentencepiece

        self.sp = sentencepiece.SentencePieceProcessor()
        self.sp.Load(str(Path(model_dir) / "sentencepiece.bpe.model"))
        self.translator = ctranslate2.Translator(
            str(model_dir), device=device, inter_threads=1, intra_threads=threads or default_threads(), compute_type="auto"
        )

    def translate(self, texts, lang):
        target = LANGUAGES[lang]["nllb"]
        batch = [["eng_Latn"] + self.sp.encode(t, out_type=str) + ["</s>"] for t in texts]
        results = self.translator.translate_batch(
            batch,
            target_prefix=[[target]] * len(batch),
            beam_size=self.beam_size,
            max_decoding_length=200,
            repetition_penalty=1.1,
            max_batch_size=16,
        )
        out = []
        for res in results:
            pieces = res.hypotheses[0]
            if pieces and pieces[0] == target:
                pieces = pieces[1:]
            out.append(self.sp.decode(pieces).strip())
        return out


class ArgosEngine:
    tag = "argos"

    """Argos Translate models (OPUS-MT, one per language pair) run with CTranslate2 and SentencePiece, without the Argos library."""

    def __init__(self, directory, threads=0, beam_size=2):
        import ctranslate2
        import sentencepiece

        root = Path(directory)
        self.beam_size = beam_size
        self.sp = sentencepiece.SentencePieceProcessor()
        self.sp.Load(str(root / "sentencepiece.model"))
        self.translator = ctranslate2.Translator(
            str(root / "model"), device="cpu", inter_threads=1, intra_threads=threads or default_threads(), compute_type="auto"
        )

    def translate(self, texts, lang):
        batch = [self.sp.encode(t, out_type=str) for t in texts]
        results = self.translator.translate_batch(batch, beam_size=self.beam_size, max_decoding_length=200, max_batch_size=16)
        return [clean_pieces(self.sp.decode(r.hypotheses[0])) for r in results]


def clean_pieces(text):
    """The Argos models leave SentencePiece's word marker in some of their output."""
    return " ".join(text.replace("▁", " ").split())


class FakeEngine:
    def translate(self, texts, lang):
        return ["(%s) %s" % (lang, t) for t in texts]
