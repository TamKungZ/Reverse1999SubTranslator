import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication, QImage, QPainter

from . import render
from .i18n import Locale
from .menu import MenuModel
from .settings import DEFAULTS

STYLE = {"text_ink_h": 33 / 1080, "name_cap": 31 / 1080, "text_left": 412 / 1920, "name_left": 426 / 1920,
         "name_to_text": 76 / 1080, "pitch": None, "text_color": "#e1dedc", "name_color": "#b4aba4"}


def _breaks(segments):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
    from r1999engine.translate import add_breaks

    return [{"t": t, "k": k} for t, k in add_breaks([(s["t"], s["k"]) for s in segments], "th")]


def sample_views():
    seg = lambda *parts: _breaks([{"t": t, "k": k} for t, k in parts])
    return {
        "f214f9ec": {"kind": "sentence", "anchor_top": 0.812, "pending": False, "style": STYLE,
                     "speaker": {"display": "Z"},
                     "segments": seg(("ฟังดูเหมือนเพื่อนของเธอเพิ่งเจอปัญหาเข้าแล้วนะ ", None), ("เรกูลัส", "name"), ("", None))},
        "b7fa3e03": {"kind": "sentence", "anchor_top": 0.873, "pending": False, "style": STYLE, "speaker": None,
                     "segments": seg(("", None), ("APPLe", "term"), (" แล่นต่อไปโดยมีเพียงท้องฟ้าสีฟ้าสดใสเป็นเพื่อน", None))},
        "3d6b09cb": {"kind": "sentence", "anchor_top": 0.811, "pending": False, "style": STYLE,
                     "speaker": {"display": "เรกูลัส"},
                     "segments": seg(("ไม่ ไม่นะ อย่าไปสิ โธ่ ไม่เอาน่า! ตรงนั้นแหละคือช่วงที่ดีที่สุดเลย! "
                                      "ฉันตั้งใจเล่าให้จบอยู่แล้วเชียว แต่เธอก็ลุกหนีไปก่อนทุกที "
                                      "คราวหน้าอย่างน้อยก็ฟังให้จบก่อนได้ไหม แล้วค่อยตัดสินว่ามันน่าเบื่อหรือเปล่า", None))},
        "f113b198": {"kind": "sentence", "anchor_top": 0.811, "pending": True, "style": STYLE,
                     "speaker": {"display": "เวอร์ติน"},
                     "segments": seg(("ระบบนำทางทำงานได้ตามปกติหรือเปล่า", None))},
        "98351c93": {"kind": "words", "anchor_top": 0.811, "pending": False, "style": STYLE,
                     "speaker": {"display": "เรกูลัส"}, "segments": [],
                     "chips": [{"w": "Far", "m": "ไกล", "k": "word"}, {"w": "as", "m": "เท่าที่", "k": "word"}, {"w": "I", "m": "ฉัน", "k": "word"}, {"w": "can", "m": "สามารถ", "k": "word"}, {"w": "tell,", "m": "บอก", "k": "word"}, {"w": "there's", "m": "มี", "k": "word"}, {"w": "nothing", "m": "ไม่มีอะไร", "k": "word"}, {"w": "but", "m": "นอกจาก", "k": "word"}, {"w": "sea", "m": "ทะเล", "k": "word"}, {"w": "from", "m": "จาก", "k": "word"}, {"w": "here", "m": "ที่นี่", "k": "word"}, {"w": "to", "m": "ไปยัง", "k": "word"}, {"w": "the", "m": "ที่", "k": "word"}, {"w": "horizon.", "m": "เส้นขอบฟ้า", "k": "word"}]},
    }


def render_image(src, view, out, menu=False, toast="", ui_over=None, locale="en"):
    img = QImage(str(src)).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    ui = {k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in DEFAULTS.items()}
    ui.update(ui_over or {})
    loc = Locale(locale)
    st = render.RenderState(view=view, reveal=1.0, ui=ui, pulse=0.4, hotkeys=ui["hotkeys"], t=loc.t)
    if menu:
        engine_cfg = {"mode": "sentence", "timing": "wait", "target_lang": "th", "name_style": "native",
                      "word_level": "basic", "stable_ms": 450}
        model = MenuModel(ui, engine_cfg, loc, {"th": "ไทย", "ja": "日本語", "zh": "中文"}, ["Leelawadee UI", "Sarabun", "Tahoma"], lambda *a: None, lambda *a: None)
        model.index = 1
        st.menu_rows, st.menu_reveal = model.rows(), 1.0
        st.view = None
    if toast:
        st.toast, st.toast_alpha = toast, 1.0
    p = QPainter(img)
    render.paint(p, img.width(), img.height(), st)
    p.end()
    img.save(str(out))


def main():
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "preview")
    out_dir.mkdir(parents=True, exist_ok=True)
    app = QGuiApplication([])
    render.load_fonts()
    uploads = Path("/mnt/user-data/uploads")
    for key, view in sample_views().items():
        render_image(uploads / ("%s-image.jpg" % key), view, out_dir / ("%s.png" % key))
    render_image(uploads / "3d6b09cb-image.jpg", None, out_dir / "menu.png", menu=True, toast="Mode: Word by word")
    render_image(uploads / "3d6b09cb-image.jpg", None, out_dir / "menu_th.png", menu=True, locale="th", ui_over={"locale": "th"})
    del app


if __name__ == "__main__":
    main()
