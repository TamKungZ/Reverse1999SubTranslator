import os
import sys
import tempfile
from pathlib import Path

os.environ["APPDATA"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).parent.parent / "engine"))

from r1999engine.config import EngineConfig
from r1999engine.glossary import Glossary
import numpy as np
from r1999engine.ocr import DialogRead, line_cuts, plausible_name
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
