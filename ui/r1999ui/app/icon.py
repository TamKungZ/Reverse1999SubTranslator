from pathlib import Path

from PySide6.QtGui import QIcon

ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"


def app_icon():
    return QIcon(str(ICON_PATH))
