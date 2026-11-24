from PySide6.QtGui import QFontDatabase

SYSTEMS = QFontDatabase.WritingSystem
WRITING_SYSTEM = {"th": SYSTEMS.Thai, "vi": SYSTEMS.Vietnamese, "id": SYSTEMS.Latin}


def fonts_for_language(lang):
    """Installed font families that can show the target language, for the font choice in the menu."""
    system = WRITING_SYSTEM.get(lang, SYSTEMS.Any)
    return sorted({f for f in QFontDatabase.families(system) if not f.startswith("@")}, key=str.lower)
