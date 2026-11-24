import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["APPDATA"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).parent.parent / "engine"))

from r1999engine.config import EngineConfig
from r1999engine.glossary import Glossary
from r1999engine.languages import BUILTIN, LANGUAGES, complete, load_languages
import numpy as np
from r1999engine.ocr import DialogRead, line_cuts, plausible_name
from r1999engine.ocr.lines import split_spans
from r1999engine.session import Session
from r1999engine.textutil import split_sentences, trim_partial_word
from r1999engine.translate import FakeEngine, TextTranslator
from r1999engine.common_words import is_common


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


class Echo:
    def translate(self, texts, lang):
        return ["T:" + t for t in texts]


class Drop:
    def translate(self, texts, lang):
        return ["T:" + t.replace("[1]", "").replace("[2]", "") for t in texts]


def make_session(timing="wait"):
    cfg = EngineConfig()
    cfg.update({"timing": timing}, save=False)
    g = Glossary()
    tr = TextTranslator(Echo(), g, persist=False)
    clock = Clock()
    return Session(cfg, g, reader=object(), translator=tr, clock=clock), clock


def settle(s):
    req = s._request
    assert req is not None
    s._request = None
    view = s.build_view(req)
    view["seq"] = req.seq
    s._view = view
    return view


def test_line_cuts_split_close_lines_and_ignore_dots():
    mask = np.zeros((90, 300), bool)
    mask[8:44, 10:290] = True       # long first line
    mask[53:57, 20:24] = True       # an i-dot sitting between the lines
    mask[60:79, 10:80] = True       # short second line
    assert line_cuts(mask) == [(44 + 60) // 2]
    assert line_cuts(mask[:50]) == [] and line_cuts(np.zeros((20, 20), bool)) == []


def test_scenery_in_name_band_is_not_a_name():
    assert plausible_name((57, 0, 608, 47), {"cap": 29, "color": "#a99d84"}, 1080)   # Vertin, with glow wider than the name
    assert not plausible_name((93, 0, 598, 56), {"cap": 6, "color": "#d3d2cc"}, 1080)   # floor reflection read as "SA"
    assert not plausible_name(None, None, 1080)


def test_language_defaults_from_the_nllb_code():
    th, de, ja = complete("th", {"name": "x", "nllb": "tha_Thai"}), complete("de", {"name": "Deutsch", "nllb": "deu_Latn"}), complete("ja", {"name": "x", "nllb": "jpn_Jpan"})
    assert (th["join"], th["native_names"], th["script"]) == (" ", True, "Thai")
    assert (de["join"], de["native_names"], de["model_repo"]) == (" ", False, None)
    assert ja["join"] == ""
    assert complete("xx", {"name": "x", "nllb": "deu_Latn", "join": "", "native_names": True, "model_repo": "me/model"})["model_repo"] == "me/model"
    assert set(LANGUAGES) >= {"th", "id", "vi"}
    assert LANGUAGES["th"]["fonts"][0] == "Kanit" and LANGUAGES["id"]["fonts"] == []
    for bad in ("Kanit", ["ok", ""], [1]):
        try:
            complete("x", {"name": "x", "nllb": "deu_Latn", "fonts": bad})
        except ValueError:
            continue
        raise AssertionError("fonts %r should be rejected" % (bad,))


def test_user_language_file_adds_overrides_and_reports_errors():
    folder = Path(tempfile.mkdtemp())
    user = folder / "languages.json"
    user.write_text(json.dumps({
        "_about": "ignored",
        "de": {"name": "Deutsch", "nllb": "deu_Latn"},
        "th": {"name": "Thai", "nllb": "tha_Thai", "model_repo": "me/thai-model"},
        "bad": {"name": "No code"},
        "also bad!": {"name": "x", "nllb": "deu_Latn"},
        "repo": {"name": "x", "nllb": "deu_Latn", "model_repo": "no-slash"},
    }), encoding="utf-8")
    languages, errors = load_languages([BUILTIN, user, folder / "missing.json"])
    assert set(languages) == {"th", "id", "vi", "de"} and languages["th"]["model_repo"] == "me/thai-model"
    assert len(errors) == 3 and all("languages.json" in e for e in errors)
    user.write_text("[]", encoding="utf-8")
    assert load_languages([user])[1] == ["languages.json: the file must contain a JSON object"]


def test_switching_to_a_language_with_its_own_model():
    import r1999engine.server.host as host_module
    from r1999engine.languages import LANGUAGES as langs

    class Stub:
        def __init__(self, *args):
            self.args = args

    langs["id"]["model_repo"] = "me/indonesian-model"
    original = (host_module.is_ready, host_module.NLLBEngine)
    try:
        host = host_module.Host(config_path=Path(tempfile.mkdtemp()) / "config.json")
        host.session.reader = object()
        host_module.is_ready = lambda directory: "indonesian" not in str(directory)
        host_module.NLLBEngine = Stub
        host._load_model(host.repo())
        assert host.state == "ready" and host.info()["model_repo"] == host.cfg["model_repo"]
        host.update_config({"target_lang": "id"})
        assert host.state == "model_missing" and host.session.translator is None and host.info()["model_repo"] == "me/indonesian-model"
        host_module.is_ready = lambda directory: True
        host._load_model("me/indonesian-model")
        assert host.state == "ready" and host.session.translator.engine.args[0].name.endswith("me__indonesian-model")
        host.update_config({"target_lang": "th"})
        assert host.state == "ready" and host.session.translator.engine is host._engines[host.cfg["model_repo"]]
    finally:
        langs["id"]["model_repo"] = None
        host_module.is_ready, host_module.NLLBEngine = original


class CountingReader:
    def __init__(self):
        self.reads, self.text, self.box = 0, "Hello there friend.", (160, 400, 960, 460)

    def read(self, frame):
        self.reads += 1
        return DialogRead(text=self.text, top_y=0.9, box=self.box if self.text else None, style={})


def test_unchanged_text_is_not_read_again_while_the_background_moves():
    s, clock = make_session("wait")
    reader = s.reader = CountingReader()
    frame = type("F", (), {})()
    base = np.full((540, 1280, 3), 40, np.uint8)
    base[400:460, 160:960] = 200                 # the text
    for step in range(10):
        clock.t += 0.1
        moving = base.copy()
        moving[:300, :, :] = 40 + step * 5       # the background changes every frame, away from the text
        frame.img = moving
        s.process_frame(frame)
    assert reader.reads <= 2                     # the first look and one refresh, not one per frame
    clock.t += 0.1
    changed = base.copy()
    changed[400:460, 160:960] = 40               # the text disappears
    frame.img = changed
    reader.text = ""
    before = reader.reads
    s.process_frame(frame)
    assert reader.reads == before + 1 and s._box is None


def test_text_that_appears_in_a_quiet_scene_is_found():
    s, clock = make_session("wait")
    reader = s.reader = CountingReader()
    reader.text = ""
    frame = type("F", (), {})()
    frame.img = np.full((540, 1280, 3), 40, np.uint8)
    s.process_frame(frame)
    clock.t += 0.3
    frame.img = frame.img.copy()
    frame.img[400:460, 160:960] = 200
    reader.text = "Hello there friend."
    s.process_frame(frame)
    assert reader.reads == 2 and s._box is not None
    s.reset()
    assert s._box is None and s._read_small is None


def test_translation_speed_settings():
    from r1999engine.translate.engines import default_threads
    cfg = EngineConfig(Path(tempfile.mkdtemp()) / "config.json")
    assert cfg["threads"] == 0 and cfg["beam_size"] == 2        # 0 means a number picked from the machine
    cfg.update({"beam_size": 1, "threads": 6}, save=False)
    assert cfg["beam_size"] == 1 and cfg["threads"] == 6
    cfg.update({"beam_size": 99, "threads": -3}, save=False)
    assert cfg["beam_size"] == 5 and cfg["threads"] == 0
    assert 2 <= default_threads() <= 8


def test_a_centered_line_that_starts_left_of_the_usual_area_is_read_whole():
    import cv2
    from r1999engine.ocr import DialogReader, Frame
    w, h = 1920, 1080
    frame = np.full((h, w, 3), (26, 28, 30), np.uint8)
    cv2.putText(frame, "Sounds like your friend just ran into trouble.", (250, 975), cv2.FONT_HERSHEY_DUPLEX, 1.4, (220, 222, 225), 2, cv2.LINE_AA)
    reader = DialogReader(Glossary())
    region = (0.08, 0.78, 0.90, 1.0)
    crop = np.ascontiguousarray(frame[int(region[1] * h):, int(region[0] * w):int(region[2] * w)])
    read = reader.read(Frame(crop, w, h, region))
    assert read.text.startswith("Sounds like") and read.text.endswith("trouble.")
    x0, y0, x1, y1 = read.box
    assert x0 < (0.19 - 0.08) * w and y1 > y0           # the box covers the line, including the part left of the usual area


def test_very_wide_lines_are_read_in_two_pieces_cut_between_words():
    mask = np.zeros((40, 1700), bool)
    for start in range(20, 1650, 60):
        mask[8:30, start:start + 48] = True      # words of 48 pixels with gaps of 12
    mask[:, 860:880] = False                     # a wider gap near the middle
    spans = split_spans(mask)
    assert len(spans) == 2 and spans[0][1] < 860 and spans[1][0] >= 880
    assert split_spans(mask[:, :900]) == [(20, 884 - 8)] or len(split_spans(mask[:, :900])) == 1   # short lines stay whole
    solid = np.zeros((40, 1700), bool)
    solid[8:30, 20:1680] = True
    assert split_spans(solid) == [(20, 1679)]    # no gap to cut at, so it is left whole
    assert split_spans(np.zeros((40, 100), bool)) == []


def test_centered_menu_lines_and_left_aligned_dialog_lines_are_told_apart():
    import cv2
    from r1999engine.ocr import DialogReader, Frame
    from r1999engine.ocr.reader import is_centered
    from r1999engine.session.style import StyleTracker
    w = 1920
    assert is_centered(323, 1596, w) and is_centered(783, 1136, w)           # main menu lines, around the middle of the screen
    assert not is_centered(412, 1500, w) and not is_centered(413, 700, w)    # dialog lines start at the same place
    assert not is_centered(412, 1508, w)                                     # even when such a line happens to be centered
    reader = DialogReader(Glossary())
    region = (0.08, 0.78, 0.90, 1.0)
    for x, text, expected in ((412, "Is the navigation system functioning properly?", "left"), (700, "Plastic wrap can catch the ghost.", "center")):
        frame = np.full((1080, w, 3), (26, 28, 30), np.uint8)
        size = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 1.4, 2)[0][0]
        start = x if expected == "left" else (w - size) // 2
        cv2.putText(frame, text, (start, 975), cv2.FONT_HERSHEY_DUPLEX, 1.4, (220, 222, 225), 2, cv2.LINE_AA)
        crop = np.ascontiguousarray(frame[int(region[1] * 1080):, int(region[0] * w):int(region[2] * w)])
        style = reader.read(Frame(crop, w, 1080, region)).style
        assert style["text_align"] == expected, (expected, style)
        if expected == "center":
            assert abs(style["text_center"] - 0.5) < 0.02
    tracker = StyleTracker()
    for _ in range(5):
        tracker.merge({"text_left": 0.2146})
    tracker.new_text()                                         # a new subtitle is measured on its own, not against the old one
    tracker.merge({"text_left": 0.40})
    assert tracker.values["text_left"] == 0.40


def test_split():
    assert split_sentences("No, no. Don't go. Oh, come on! That was the best part!") == [
        "No, no.", "Don't go.", "Oh, come on!", "That was the best part!"]
    assert split_sentences("Mr. Smith left. He ran.") == ["Mr. Smith left.", "He ran."]
    assert trim_partial_word("Sounds like your fri") == "Sounds like your"
    assert trim_partial_word("Sounds.") == "Sounds."


def test_protect_restore():
    g = Glossary()
    text = "Sounds like your friend just got into some troubles, Regulus."
    prot, items = g.protect(text, "th")
    assert prot.endswith("troubles, [1].") and items[0].shown == "เรกูลัส"
    parts = g.restore("เพื่อนของคุณมีปัญหา [1]", items)
    assert parts == [("เพื่อนของคุณมีปัญหา ", None), ("เรกูลัส", "name")]
    assert g.restore("เพื่อนของคุณมีปัญหา", items) is None
    assert g.restore("เพื่อนของคุณ ［1］", items)[-1] == ("เรกูลัส", "name")
    marked = g.mark("ปัญหา Regulus ครับ", items)
    assert ("เรกูลัส", "name") in marked


def test_fallback_when_placeholder_lost():
    g = Glossary()
    tr = TextTranslator(Drop(), g, persist=False)
    segs = tr.sentence("Sounds like trouble, Regulus.", "th")
    assert "".join(t for t, _ in segs).startswith("T:")


def test_unknown_names_and_terms():
    g = Glossary()
    spans = g.spans("I met Bronwen near the APPLe and an Arcanist, Perhaps.")
    kinds = {(s.canon, s.kind) for s in spans}
    assert ("Bronwen", "name") in kinds and ("APPLe", "term") in kinds and ("Arcanist", "term") in kinds
    assert ("Perhaps", "name") not in kinds
    assert g.canonical_speaker("Tertin") == "Vertin"
    assert g.canonical_speaker("Z") == "Z"
    assert g.canonical_speaker("Xq") is None


def test_chips_levels():
    g = Glossary()
    tr = TextTranslator(FakeEngine(), g, persist=False)
    chips = tr.chips("The navigation system works, Regulus said.", "th", "basic")
    assert [c["w"] for c in chips][:2] == ["The", "navigation"] and chips[0]["m"] == "" and chips[1]["m"]
    assert any(c["w"] == "Regulus" and c["k"] == "name" and c["m"] == "เรกูลัส" for c in chips)
    every = tr.chips("Far as I can tell,", "th", "off")
    assert [c["w"] for c in every] == ["Far", "as", "I", "can", "tell,"] and all(c["m"] for c in every)
    assert not is_common("horizon", "medium") and is_common("troubles", "medium")
    assert [c["m"] for c in tr.chips("the and", "th", "basic")] == ["", ""]
    assert any(c["w"] == "APPLe" and c["k"] == "term" for c in tr.chips("The APPLe sails on.", "th", "basic"))


def test_wait_mode():
    s, clock = make_session("wait")
    for step, text in enumerate(["Sounds", "Sounds like", "Sounds like your friend"]):
        clock.t += 0.1
        s.observe(DialogRead(text=text, speaker="Regulus", speaker_known=True, top_y=0.81), clock.t)
        s.evaluate(clock.t)
        assert s._request is None
    clock.t += 0.5
    s.evaluate(clock.t)
    view = settle(s)
    assert view["kind"] == "sentence" and view["speaker"]["display"] == "เรกูลัส"
    assert "".join(x["t"] for x in view["segments"]).replace("\u200b", "") == "T:Sounds like your friend"
    clock.t += 1
    s.observe(DialogRead(text="Sounds like your friend", speaker="Regulus", speaker_known=True), clock.t)
    s.evaluate(clock.t)
    assert s._request is None and s.view()["kind"] == "sentence"


def test_new_sentence_hides_then_translates():
    s, clock = make_session("wait")
    s.observe(DialogRead(text="First line here."), clock.t)
    clock.t += 0.6
    s.evaluate(clock.t)
    settle(s)
    clock.t += 0.1
    s.observe(DialogRead(text="Second"), clock.t)
    s.evaluate(clock.t)
    assert s.view()["kind"] == "sentence"
    clock.t += 0.1
    s.observe(DialogRead(text="Second"), clock.t)
    s.evaluate(clock.t)
    assert s.view()["kind"] == "none"
    clock.t += 0.6
    s.observe(DialogRead(text="Second line now."), clock.t)
    clock.t += 0.6
    s.evaluate(clock.t)
    assert s._request.text == "Second line now."


def test_ocr_jitter_does_not_retranslate():
    s, clock = make_session("wait")
    s.observe(DialogRead(text="Far as I can tell, there's nothing."), clock.t)
    clock.t += 0.6
    s.evaluate(clock.t)
    settle(s)
    clock.t += 0.2
    s.observe(DialogRead(text="Far as I can tell, theres nothing."), clock.t)
    clock.t += 0.6
    s.evaluate(clock.t)
    assert s._request is None and s.view()["kind"] == "sentence"


def shown(s, clock, text="Far as I can tell, there's nothing but sea."):
    s.observe(DialogRead(text=text, top_y=0.81), clock.t)
    clock.t += 0.6
    s.evaluate(clock.t)
    settle(s)


def test_garbled_frame_does_not_hide():
    s, clock = make_session("wait")
    shown(s, clock)
    clock.t += 0.1
    s.observe(DialogRead(text="Fer zs I cqn tell, thare nothinq bvt sea."), clock.t)
    s.evaluate(clock.t)
    assert s.wants_read() and s.view()["kind"] == "sentence"
    clock.t += 0.1
    s.observe(DialogRead(text="Far as I can tell, there's nothing but sea."), clock.t)
    clock.t += 0.6
    s.evaluate(clock.t)
    assert not s.wants_read() and s._request is None and s.view()["kind"] == "sentence"


def test_dropped_frames_keep_settle_timer():
    s, clock = make_session("wait")
    s.observe(DialogRead(text="Hello there friend."), clock.t)
    clock.t += 0.3
    s.observe(DialogRead(text=""), clock.t)
    clock.t += 0.05
    s.observe(DialogRead(text="Hello there friend."), clock.t)
    clock.t += 0.15
    s.evaluate(clock.t)
    assert s._request is not None and s._request.final


def test_typing_waits_until_text_stops_growing():
    s, clock = make_session("wait")
    text = "Far as I can tell, there's nothing but sea from here to the horizon."
    for i in range(20, len(text) + 1):
        clock.t += 0.1
        s.observe(DialogRead(text=text[:i]), clock.t)
        s.evaluate(clock.t)
        assert s._request is None
    clock.t += 0.5
    s.evaluate(clock.t)
    assert s._request.text == text


def test_late_growth_retranslates_without_hiding():
    s, clock = make_session("wait")
    text = "Far as I can tell, there's nothing but sea from here to the horizon."
    shown(s, clock, text[:-6])
    s.observe(DialogRead(text=text), clock.t)
    clock.t += 0.6
    s.evaluate(clock.t)
    assert s._request.text == text and s.view()["kind"] == "sentence"


def test_moving_text_uses_median_anchor():
    s, clock = make_session("wait")
    for top in (0.81, 0.93, 0.81, 0.70, 0.81):
        clock.t += 0.05
        s.observe(DialogRead(text="Hello there friend.", top_y=top), clock.t)
    assert abs(s.cur_top - 0.81) < 1e-9


def test_hide_after_text_disappears():
    s, clock = make_session("wait")
    s.observe(DialogRead(text="Hello there friend."), clock.t)
    clock.t += 0.6
    s.evaluate(clock.t)
    settle(s)
    clock.t += 0.1
    s.observe(DialogRead(text=""), clock.t)
    s.evaluate(clock.t)
    assert s.view()["kind"] == "sentence"
    clock.t += 0.6
    s.evaluate(clock.t)
    assert s.view()["kind"] == "none"


def test_live_mode_translates_partials():
    s, clock = make_session("live")
    s.observe(DialogRead(text="Sounds like your fri"), clock.t)
    s.evaluate(clock.t + 0.0)
    clock.t += 0.35
    s.observe(DialogRead(text="Sounds like your friend ju"), clock.t)
    s.evaluate(clock.t)
    assert s._request is not None and s._request.text == "Sounds like your friend" and not s._request.final
    view = settle(s)
    assert view["pending"] is True
    clock.t += 0.6
    s.evaluate(clock.t)
    assert s._request.final


def test_stale_translation_dropped():
    s, clock = make_session("wait")
    s.observe(DialogRead(text="Hello there friend."), clock.t)
    clock.t += 0.6
    s.evaluate(clock.t)
    req = s._request
    s._hide()
    assert req.seq != s._seq


def test_word_mode_view():
    s, clock = make_session("wait")
    s.cfg.update({"mode": "word"}, save=False)
    s.observe(DialogRead(text="The navigation system, Regulus."), clock.t)
    clock.t += 0.6
    s.evaluate(clock.t)
    view = settle(s)
    assert view["kind"] == "words" and {c["k"] for c in view["chips"]} == {"word", "name"}


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("ok  ", name)
            except Exception as exc:
                failed += 1
                import traceback
                traceback.print_exc()
                print("FAIL", name, exc)
    sys.exit(1 if failed else 0)
