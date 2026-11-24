from PySide6.QtGui import QFontDatabase

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


def fonts_for_language(lang, script):
    """Installed font families that can show the target language, for the font choice in the menu."""
    system = BY_LANGUAGE.get(lang) or BY_SCRIPT.get(script, SYSTEMS.Any)
    return sorted({f for f in QFontDatabase.families(system) if not f.startswith("@")}, key=str.lower)
