from pathlib import Path

from ..languages import LANGUAGES


class NLLBEngine:
    def __init__(self, model_dir, threads=4, device="cpu"):
        import ctranslate2
        import sentencepiece

        self.sp = sentencepiece.SentencePieceProcessor()
        self.sp.Load(str(Path(model_dir) / "sentencepiece.bpe.model"))
        self.translator = ctranslate2.Translator(
            str(model_dir), device=device, inter_threads=1, intra_threads=threads, compute_type="auto"
        )

    def translate(self, texts, lang):
        target = LANGUAGES[lang]["nllb"]
        batch = [["eng_Latn"] + self.sp.encode(t, out_type=str) + ["</s>"] for t in texts]
        results = self.translator.translate_batch(
            batch,
            target_prefix=[[target]] * len(batch),
            beam_size=3,
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


class FakeEngine:
    def translate(self, texts, lang):
        return ["(%s) %s" % (lang, t) for t in texts]
