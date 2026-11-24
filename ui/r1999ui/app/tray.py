from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

ACTIONS = (("tray.toggle", "toggle"), ("tray.mode", "mode"), ("tray.settings", "menu"))
ICON_BACKGROUND = QColor(222, 196, 136)
ICON_LETTER = QColor(44, 33, 18)
ALIGN_CENTER = 0x84


def make_icon():
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(ICON_BACKGROUND)
    p.setPen(QColor(0, 0, 0, 0))
    p.drawRoundedRect(4, 4, 56, 56, 16, 16)
    p.setPen(ICON_LETTER)
    font = p.font()
    font.setBold(True)
    font.setPixelSize(36)
    p.setFont(font)
    p.drawText(pix.rect(), ALIGN_CENTER, "T")
    p.end()
    return QIcon(pix)


class Tray:
    def __init__(self, app, loc, emit, quit_):
        self.loc = loc
        self.icon = QSystemTrayIcon(make_icon(), app)
        self.menu = QMenu()
        self._actions = []
        for key, action in ACTIONS:
            self._add(key, lambda _=False, a=action: emit(a))
        self.menu.addSeparator()
        self._add("tray.quit", quit_)
        self.icon.setContextMenu(self.menu)
        self.icon.setToolTip(loc.t("app.title"))
        self.icon.show()

    def _add(self, key, handler):
        act = QAction(self.loc.t(key), self.menu)
        act.triggered.connect(handler)
        self.menu.addAction(act)
        self._actions.append((act, key))

    def refresh(self):
        for act, key in self._actions:
            act.setText(self.loc.t(key))
