from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .icon import app_icon

ACTIONS = (("tray.toggle", "toggle"), ("tray.mode", "mode"), ("tray.settings", "menu"))


class Tray:
    def __init__(self, app, loc, emit, quit_):
        self.loc = loc
        self.icon = QSystemTrayIcon(app_icon(), app)
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
