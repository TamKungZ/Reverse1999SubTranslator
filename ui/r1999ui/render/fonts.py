from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FAMILIES = ["Sarabun", "Leelawadee UI", "Yu Gothic UI", "Microsoft YaHei UI", "Malgun Gothic", "Segoe UI"]
THAI_FIRST = ["Kanit"]

thai_default = False
_px_cache = {}


def load_fonts():
    for ttf in sorted(ASSETS.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(ttf))


def set_thai_default(on):
    global thai_default
    thai_default = bool(on)


def make_font(px, weight=QFont.Weight.Normal, italic=False, family=""):
    font = QFont()
    lead = [family] if family else (THAI_FIRST if thai_default else [])
    font.setFamilies(lead + FAMILIES)
    font.setPixelSize(max(6, int(round(px))))
    font.setWeight(weight)
    font.setItalic(italic)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def px_for_height(family, target, sample):
    key = (family, thai_default, sample, round(target, 1))
    if key not in _px_cache:
        px = max(8.0, target)
        for _ in range(3):
            h = QFontMetricsF(make_font(px, family=family)).tightBoundingRect(sample).height()
            if h <= 0:
                break
            px *= target / h
        _px_cache[key] = px
    return _px_cache[key]


def ink_ascent(font, sample):
    return -QFontMetricsF(font).tightBoundingRect(sample).top()
