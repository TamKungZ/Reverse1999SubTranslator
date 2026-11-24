from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF

FONTS = Path(__file__).resolve().parent.parent / "fonts"
FAMILIES = ["Leelawadee UI", "Yu Gothic UI", "Microsoft YaHei UI", "Malgun Gothic", "Segoe UI"]

SYSTEMS = QFontDatabase.WritingSystem
BY_LANGUAGE = {"vi": SYSTEMS.Vietnamese}
BY_SCRIPT = {
    "Thai": SYSTEMS.Thai,
    "Latn": SYSTEMS.Latin,
    "Jpan": SYSTEMS.Japanese,
    "Hans": SYSTEMS.SimplifiedChinese,
    "Hant": SYSTEMS.TraditionalChinese,
    "Hang": SYSTEMS.Korean,
    "Arab": SYSTEMS.Arabic,
    "Cyrl": SYSTEMS.Cyrillic,
    "Grek": SYSTEMS.Greek,
    "Hebr": SYSTEMS.Hebrew,
    "Deva": SYSTEMS.Devanagari,
    "Beng": SYSTEMS.Bengali,
    "Khmr": SYSTEMS.Khmer,
    "Laoo": SYSTEMS.Lao,
    "Mymr": SYSTEMS.Myanmar,
    "Taml": SYSTEMS.Tamil,
}

preferred = []
_languages = []
_fallback = None
_px_cache = {}


def families_for(lang, script):
    """Installed font families that can show the language."""
    system = BY_LANGUAGE.get(lang) or BY_SCRIPT.get(script, SYSTEMS.Any)
    return sorted({f for f in QFontDatabase.families(system) if not f.startswith("@")}, key=str.lower)


def load_fonts():
    global _fallback
    for ttf in sorted(FONTS.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(ttf))
    _fallback = None


def set_languages(entries):
    """Sets the languages being shown, as (code, script, preferred fonts). The first font of the first language is the default."""
    global preferred, _languages, _fallback
    preferred = list(dict.fromkeys(font for _, _, fonts in entries for font in fonts))
    _languages = [(lang, script) for lang, script, _ in entries]
    _fallback = None


def fallback():
    """For a language none of whose preferred fonts is installed, any installed font that can show it."""
    global _fallback
    if _fallback is None:
        _fallback = []
        for lang, script in _languages:
            found = families_for(lang, script)
            if found and not any(font in found for font in preferred):
                _fallback.append(found[0])
    return _fallback


def make_font(px, weight=QFont.Weight.Normal, italic=False, family=""):
    font = QFont()
    lead = ([family] if family else []) + preferred
    font.setFamilies(list(dict.fromkeys(lead + FAMILIES + fallback())))
    font.setPixelSize(max(6, int(round(px))))
    font.setWeight(weight)
    font.setItalic(italic)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def px_for_height(family, target, sample):
    key = (family, tuple(preferred), sample, round(target, 1))
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
