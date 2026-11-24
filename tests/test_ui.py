import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["APPDATA"] = tempfile.mkdtemp()
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "ui"))
sys.path.insert(0, str(ROOT / "engine"))

import cv2
import numpy as np
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from r1999ui import render, winutil
from r1999ui.client import EngineClient
from r1999ui.hotkeys import HotkeyManager, parse_hotkey
from r1999ui.menu import MenuModel
from r1999ui.overlay import OverlayWindow
from r1999ui.settings import UiSettings

app = QApplication.instance() or QApplication([])
render.load_fonts()

def synthetic_frame(w=1920, h=1080):
    frame = np.full((h, w, 3), (26, 28, 30), np.uint8)
    light = (220, 222, 225)
    cv2.putText(frame, "Regulus", (425, 905), cv2.FONT_HERSHEY_DUPLEX, 1.5, light, 2, cv2.LINE_AA)
    cv2.putText(frame, "Sounds like your friend just ran into trouble.", (412, 975), cv2.FONT_HERSHEY_DUPLEX, 1.4, light, 2, cv2.LINE_AA)
    return frame


def pump(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)


def test_hotkey_parse():
    assert parse_hotkey("F9") == (frozenset(), 0x78)
    assert parse_hotkey("Ctrl+Shift+T") == (frozenset({0x11, 0x10}), ord("T"))
    for bad in ("", "Ctrl", "A+B", "F13"):
        try:
            parse_hotkey(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    mgr = HotkeyManager({"toggle": "F7"}, {"up": "UP"}, lambda: True, lambda a: None)
    mgr.modal = True
    mgr._held_mods = lambda: frozenset()
    assert mgr._match(0x26) == "nav:up" and mgr._match(0x76) == "toggle" and mgr._match(0x41) is None
    mgr.modal = False
    assert mgr._match(0x26) is None


def test_menu():
    from r1999ui.i18n import Locale
    ui = UiSettings()
    cfg = {"mode": "sentence", "timing": "wait", "target_lang": "th", "name_style": "native", "word_level": "basic", "stable_ms": 450}
    changes = []

    def on_change(src, key, value):
        changes.append((src, key, value))
        (ui.data if src == "ui" else cfg)[key] = value

    loc = Locale("en")
    menu = MenuModel(ui, cfg, loc, {"th": "ไทย", "ja": "日本語"}, ["Alpha", "Beta", "Gamma"], on_change, lambda n: changes.append(n))
    keys = [i["key"] for i in menu.items]
    menu.index = keys.index("mode")
    menu.handle("right")
    assert changes[-1] == ("eng", "mode", "word")
    menu.index = keys.index("target_lang")
    menu.handle("right")
    assert changes[-1] == ("eng", "target_lang", "ja")
    menu.index = keys.index("font_family")
    menu.handle("right")
    assert changes[-1] == ("ui", "font_family", "Alpha")
    menu.handle("pagedown")
    assert changes[-1] == ("ui", "font_family", "Gamma")
    menu.index = keys.index("size_adjust")
    for _ in range(40):
        menu.handle("right")
    assert ui["size_adjust"] == 1.8
    menu.index = keys.index("locale")
    menu.handle("right")
    assert changes[-1][:2] == ("ui", "locale") and changes[-1][2] in loc.available()
    menu.index = 0
    menu.handle("enter")
    assert changes[-1] == ("ui", "enabled", False)
    menu.index = len(menu.items) - 1
    menu.handle("enter")
    assert changes[-1] == "quit"
    rows = menu.rows()
    assert len(rows) == len(menu.items) and sum(r["selected"] for r in rows) == 1
    assert rows[0]["label"] == "Translation" and rows[0]["value"] == "Off"


def test_locales_complete():
    import json
    from r1999ui.i18n import BUILTIN, Locale
    en = json.loads((BUILTIN / "en.json").read_text(encoding="utf-8"))
    th = json.loads((BUILTIN / "th.json").read_text(encoding="utf-8"))
    assert set(en) == set(th)
    loc = Locale("th")
    assert loc.t("val.on") == "เปิด" and loc.t("toast.mode", mode="x") == "โหมด: x"
    assert Locale("zz").code == "en" and Locale("en").t("no.such.key") == "no.such.key"
    assert set(Locale("en").available()) >= {"en", "th"}
    assert Locale("en").t("toast.ready", key="F9") == "Ready. Press F9 for settings"


def test_language_fonts_and_fallback():
    fonts = render.fonts
    original = fonts.families_for
    fonts.families_for = lambda lang, script: {"th": ["Tahoma", "Zed"], "ar": ["Arabic Sans"]}.get(lang, [])
    try:
        fonts.set_languages([("th", "Thai", ["Kanit", "Tahoma"]), ("ar", "Arab", ["Missing"])])
        assert fonts.preferred == ["Kanit", "Tahoma", "Missing"]
        assert fonts.fallback() == ["Arabic Sans"]
        families = fonts.make_font(20).families()
        assert families[:3] == ["Kanit", "Tahoma", "Missing"] and families[-1] == "Arabic Sans"
        assert fonts.make_font(20, family="Arial").families()[:2] == ["Arial", "Kanit"]
    finally:
        fonts.families_for = original
        fonts.set_languages([])
    assert fonts.preferred == [] and fonts.fallback() == []


def test_centered_subtitles_are_drawn_around_their_center():
    ui = UiSettings().data
    view = {"kind": "sentence", "style": {"text_ink_h": 33 / 1080, "name_cap": 31 / 1080, "text_left": 504 / 1920, "name_left": 426 / 1920,
            "name_to_text": 76 / 1080, "pitch": None, "text_color": "#e1dedc", "name_color": "#b4aba4", "text_align": "center", "text_center": 0.5}}
    style = render.resolve_style(view, ui, 1920, 1080, 1.0)
    assert style["align"] == "center" and abs(style["center"] - 960) < 1e-6
    view["style"]["text_align"] = "left"
    assert render.resolve_style(view, ui, 1920, 1080, 1.0)["align"] == "left"
    from r1999ui.render.text import layout
    font = render.make_font(40)
    centered, lines, _ = layout("short line", [], font, 1000.0, 0.0, "center")   # the layouts must stay alive while their lines are used
    left, plain, _ = layout("short line", [], font, 1000.0, 0.0)
    assert plain[0].position().x() == 0 and abs(lines[0].position().x() - (1000.0 - lines[0].naturalTextWidth()) / 2) < 1e-6


def test_style_matching_sizes():
    ui = UiSettings()
    view = {"kind": "sentence", "style": {"text_ink_h": 33 / 1080, "name_cap": 31 / 1080, "text_left": 412 / 1920,
            "name_left": 426 / 1920, "name_to_text": 76 / 1080, "pitch": None, "text_color": "#e1dedc", "name_color": "#b4aba4"}}
    st = render.resolve_style(view, ui.data, 1920, 1080, 1.0)
    from PySide6.QtGui import QFontMetricsF
    h = QFontMetricsF(render.make_font(st["text_px"])).tightBoundingRect("Hgdp").height()
    c = QFontMetricsF(render.make_font(st["name_px"])).tightBoundingRect("H").height()
    assert abs(h - 33) <= 1.5 and abs(c - 31) <= 1.5
    assert st["text_color"].name() == "#e1dedc" and round(st["text_left"]) == 412
    st2 = render.resolve_style(view, ui.data, 3840, 2160, 2.0)
    assert st2["text_px"] > st["text_px"] * 1.9


def test_overlay_paint_and_visibility():
    ui = UiSettings()
    ui.data["animations"] = False
    ov = OverlayWindow(ui)
    ov.set_game(winutil.GameState(1, 0, 0, 1920, 1080, True, True))
    view = {"seq": 1, "kind": "sentence", "pending": False, "speaker": {"display": "เรกูลัส"},
            "segments": [{"t": "ไม่ ไม่นะ อย่าไปสิ", "k": None}], "chips": [], "anchor_top": 0.81}
    view["style"] = None
    ov.set_view(view)
    assert ov.isVisible() and ov.state.reveal == 1.0
    image = ov.grab().toImage()
    assert image.width() == 1920 and any(image.pixelColor(x, y).alpha() > 0 for x in range(420, 900, 6) for y in range(700, 860, 4))
    ov.set_game(winutil.GameState(1, 0, 0, 1920, 1080, False, True))
    assert not ov.isVisible()
    ov.set_game(winutil.GameState(1, 0, 0, 1920, 1080, True, True))
    assert ov.isVisible()
    ov.set_view({"kind": "none"})
    assert ov.state.view is None and not ov.isVisible()
    ov.set_menu([{"label": "x", "selected": True, "kind": "toggle", "ratio": None, "value": "", "on": True}])
    assert ov.isVisible()
    ov.set_menu(None)
    assert ov.state.menu_rows is None and not ov.isVisible()


def test_overlay_animation_runs():
    ui = UiSettings()
    ov = OverlayWindow(ui)
    ov.set_game(winutil.GameState(1, 0, 0, 1280, 720, True, True))
    ov.set_view({"seq": 1, "kind": "sentence", "pending": False, "speaker": None, "segments": [{"t": "ทดสอบ", "k": None}], "chips": [], "anchor_top": 0.8})
    assert ov.state.reveal < 1.0
    pump(500)
    assert ov.state.reveal == 1.0
    ov.set_view({"kind": "none"})
    pump(400)
    assert ov.state.view is None and not ov.isVisible()


def test_end_to_end_with_engine():
    port = 47811
    env = dict(os.environ, PYTHONPATH=str(ROOT / "engine"))
    proc = subprocess.Popen([sys.executable, "-m", "r1999engine", "--fake", "--port", str(port)], cwd=ROOT / "engine", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = EngineClient(port)
    try:
        for _ in range(60):
            try:
                if client.info()["state"] == "ready":
                    break
            except OSError:
                pass
            time.sleep(0.5)
        else:
            raise AssertionError("engine not ready")
        img = synthetic_frame()
        h, w = img.shape[:2]
        region = (0.08, 0.78, 0.90, 1.0)
        crop = img[int(region[1] * h):, int(region[0] * w):int(region[2] * w)].copy()
        view = None
        for _ in range(12):
            view = client.frame(crop, w, h, region)
            if view["kind"] != "none":
                break
            time.sleep(0.15)
        assert view["kind"] == "sentence" and view["speaker"]["display"] == "เรกูลัส"
        client.set_config({"mode": "word"})
        for _ in range(12):
            view = client.frame(crop, w, h, region)
            if view["kind"] == "words":
                break
            time.sleep(0.2)
        assert view["kind"] == "words" and view["chips"]
        ui = UiSettings()
        ui.data["animations"] = False
        ov = OverlayWindow(ui)
        ov.set_game(winutil.GameState(1, 0, 0, w, h, True, True))
        ov.set_view(view)
        assert ov.isVisible()
    finally:
        client.shutdown()
        proc.wait(5)


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("ok  ", name)
            except Exception:
                import traceback
                traceback.print_exc()
                failed += 1
                print("FAIL", name)
    sys.exit(1 if failed else 0)
