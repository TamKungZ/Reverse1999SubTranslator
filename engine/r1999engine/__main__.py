import argparse
import json
import sys

DEFAULT_PORT = 47631


def selftest(image_path, fake):
    import cv2

    from .config import EngineConfig
    from .glossary import Glossary
    from .model import is_ready, model_dir
    from .ocr import DialogReader, Frame
    from .translate import FakeEngine, NLLBEngine, TextTranslator

    cfg = EngineConfig()
    glossary = Glossary()
    reader = DialogReader(glossary)
    if fake:
        engine = FakeEngine()
    else:
        path = model_dir(cfg["model_repo"])
        if not is_ready(path):
            sys.exit("model not downloaded: %s" % path)
        engine = NLLBEngine(path, cfg["threads"], cfg["device"])
    translator = TextTranslator(engine, glossary, persist=False)
    img = cv2.imread(image_path)
    h, w = img.shape[:2]
    x0, y0, x1, y1 = cfg["region"]
    crop = img[int(y0 * h) : int(y1 * h), int(x0 * w) : int(x1 * w)]
    reader.name_band = cfg["name_band"]
    read = reader.read(Frame(crop, w, h, tuple(cfg["region"])))
    out = {"text": read.text, "speaker": read.speaker, "top_y": round(read.top_y, 3)}
    if read.text:
        lang = cfg["target_lang"]
        out["sentence"] = "".join(t for t, _ in translator.sentence(read.text, lang))
        out["words"] = translator.chips(read.text, lang, cfg["word_level"])
    print(json.dumps(out, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(prog="r1999-engine")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--test-image")
    args = parser.parse_args()
    if args.test_image:
        selftest(args.test_image, args.fake)
        return
    from .server import Host, serve

    serve(Host(fake=args.fake), args.port)


if __name__ == "__main__":
    main()
