import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import render, winutil
from .client import EngineClient
from .i18n import Locale
from .settings import UiSettings


def launch_engine(port):
    flags = 0x08000000 if winutil.IS_WINDOWS else 0
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).parent / "engine" / "r1999-engine.exe"
        cmd, cwd, env = [str(exe), "--port", str(port)], None, None
    else:
        root = Path(__file__).resolve().parents[2] / "engine"
        cmd = [sys.executable, "-m", "r1999engine", "--port", str(port)]
        cwd, env = str(root), dict(os.environ, PYTHONPATH=str(root))
    if os.environ.get("R1999_FAKE"):
        cmd.append("--fake")
    return subprocess.Popen(cmd, cwd=cwd, env=env, creationflags=flags)


class Controller:
    def __init__(self, app, ui):
        from PySide6.QtCore import QObject, QTimer, Signal

        class Bridge(QObject):
            view = Signal(object)
            action = Signal(str)
            toast = Signal(str)
            ready = Signal(object)

        from .hotkeys import HotkeyManager
        from .menu import MenuModel
        from .overlay import OverlayWindow

        self.app, self.ui = app, ui
        self.loc = Locale(ui["locale"])
        self.client = EngineClient(ui["engine_port"])
        self.engine_proc = None
        self.engine_cfg = {}
        self.languages = {}
        self.region = (0.19, 0.78, 0.90, 1.0)
        self.is_ready = False
        self._stop = threading.Event()
        self.bridge = Bridge()
        self.overlay = OverlayWindow(ui)
        self.tracker = winutil.GameTracker(ui["game_exe"]) if winutil.IS_WINDOWS else None
        self.menu = None
        self.MenuModel = MenuModel
        self.hotkeys = HotkeyManager(
            ui["hotkeys"], ui["menu_keys"],
            lambda: bool(self.tracker and self.tracker.state.foreground),
            self.bridge.action.emit,
        )
        self.overlay.state.t = self.loc.t
        self.apply_font_default()
        self.bridge.view.connect(self.overlay.set_view)
        self.bridge.action.connect(self.on_action)
        self.bridge.toast.connect(self.overlay.toast)
        self.bridge.ready.connect(self.on_ready)
        self.timer = QTimer()
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.poll_game)

    def start(self):
        self.make_tray()
        threading.Thread(target=self.boot, daemon=True).start()
        self.timer.start()
        self.hotkeys.start()
        if self.hotkeys.error:
            self.overlay.toast(self.loc.t("toast.hotkey_error", error=self.hotkeys.error), 4000)

    def boot(self):
        try:
            self.client.info()
        except OSError:
            self.engine_proc = launch_engine(self.ui["engine_port"])
        info = None
        for _ in range(240):
            if self._stop.is_set():
                return
            try:
                info = self.client.info()
                if info["state"] not in ("starting", "loading"):
                    break
            except OSError:
                pass
            time.sleep(0.5)
        self.bridge.ready.emit(info)

    def on_ready(self, info):
        if not info:
            self.overlay.toast(self.loc.t("toast.engine_failed"), 5000)
            return
        self.engine_cfg = info["config"]
        self.languages = info["languages"]
        self.region = tuple(self.engine_cfg["region"])
        self.apply_font_default()
        if info["state"] == "model_missing":
            self.ask_download()
        elif info["state"] == "error":
            self.overlay.toast(self.loc.t("toast.engine_error", error=info["error"][:80]), 6000)
        else:
            self.mark_ready()

    def mark_ready(self):
        self.is_ready = True
        self.overlay.toast(self.loc.t("toast.ready", key=self.ui["hotkeys"]["menu"]), 3000)
        threading.Thread(target=self.frame_loop, daemon=True).start()

    def ask_download(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

        dialog = QDialog()
        dialog.setWindowTitle(self.loc.t("app.title"))
        dialog.setMinimumWidth(460)
        label = QLabel(self.loc.t("setup.text"))
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.hide()
        start = QPushButton(self.loc.t("setup.download"))
        quit_ = QPushButton(self.loc.t("setup.quit"))
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(start)
        row.addWidget(quit_)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label)
        layout.addWidget(bar)
        layout.addLayout(row)
        poll = QTimer(dialog)

        def tick():
            try:
                info = self.client.info()
            except OSError:
                return
            dl = info["download"]
            if info["state"] == "ready":
                poll.stop()
                dialog.accept()
            elif info["state"] == "downloading":
                total = max(1, dl["total"])
                bar.setValue(int(dl["done"] * 100 / total))
                label.setText(self.loc.t("setup.downloading", file=dl["file"], done=dl["done"] >> 20, total=total >> 20))
            elif info["state"] == "loading":
                label.setText(self.loc.t("setup.loading"))
            elif info["state"] in ("model_missing", "error") and dl["state"] in ("error", "cancelled"):
                label.setText(self.loc.t("setup.failed", error=dl["error"] or info["error"]))
                start.setEnabled(True)
                start.setText(self.loc.t("setup.retry"))
                poll.stop()

        def begin():
            start.setEnabled(False)
            bar.show()
            self.client.download_model()
            poll.start(500)

        start.clicked.connect(begin)
        quit_.clicked.connect(dialog.reject)
        poll.timeout.connect(tick)
        if dialog.exec():
            self.mark_ready()
        else:
            self.quit()

    def frame_loop(self):
        from .capture import ScreenGrabber

        grabber = ScreenGrabber()
        last = (-1, "none")
        idle = True
        while not self._stop.is_set():
            state = self.tracker.state if self.tracker else None
            if not (self.ui["enabled"] and state and state.foreground and state.w > 0):
                if not idle:
                    idle = True
                    last = (-1, "none")
                    try:
                        self.client.reset()
                    except OSError:
                        pass
                    self.bridge.view.emit(None)
                time.sleep(0.2)
                continue
            idle = False
            try:
                img = grabber.grab(state, self.region)
                if img is None:
                    time.sleep(0.2)
                    continue
                view = self.client.frame(img, state.w, state.h, self.region)
            except OSError:
                time.sleep(1.0)
                continue
            key = (view["seq"], view["kind"])
            if key != last:
                last = key
                self.bridge.view.emit(view)
            time.sleep(self.ui["poll_ms"] / 1000.0)

    def poll_game(self):
        if not self.tracker:
            return
        state = self.tracker.poll()
        self.overlay.set_game(state)
        if self.ui["auto_exit"] and not state.running and time.monotonic() - self.tracker.last_seen > 10:
            self.quit()

    def on_action(self, action):
        if action == "toggle":
            self.set_ui("enabled", not self.ui["enabled"])
            self.overlay.toast(self.loc.t("toast.translation", state=self.loc.t("val.on" if self.ui["enabled"] else "val.off")))
        elif action == "mode":
            new = "word" if self.engine_cfg.get("mode") == "sentence" else "sentence"
            self.set_engine("mode", new)
            self.overlay.toast(self.loc.t("toast.mode", mode=self.loc.t("opt.mode." + new)))
        elif action == "menu":
            self.toggle_menu()
        elif action.startswith("nav:") and self.menu:
            key = action[4:]
            if key == "back":
                self.toggle_menu()
            else:
                self.menu.handle(key)
                self.overlay.set_menu(self.menu.rows())

    def toggle_menu(self):
        if self.menu:
            self.menu = None
            self.hotkeys.modal = False
            self.overlay.set_menu(None)
            return
        self.menu = self.new_menu()
        self.hotkeys.modal = True
        self.overlay.set_menu(self.menu.rows())

    def new_menu(self):
        return self.MenuModel(self.ui, self.engine_cfg, self.loc, self.languages, self.fonts_for_language(),
                              self.on_change, self.on_menu_action)

    def fonts_for_language(self):
        from PySide6.QtGui import QFontDatabase

        systems = QFontDatabase.WritingSystem
        wanted = {"th": systems.Thai, "ja": systems.Japanese, "zh": systems.SimplifiedChinese,
                  "ko": systems.Korean, "vi": systems.Vietnamese, "id": systems.Latin}
        system = wanted.get(self.engine_cfg.get("target_lang", "th"), systems.Any)
        return sorted({f for f in QFontDatabase.families(system) if not f.startswith("@")}, key=str.lower)

    def on_change(self, src, key, value):
        if src == "ui":
            self.set_ui(key, value)
            if key == "locale":
                self.loc.set(value)
                self.refresh_tray()
        else:
            self.set_engine(key, value)
        if key in ("locale", "target_lang"):
            self.apply_font_default()
        if key in ("locale", "target_lang") and self.menu:
            index = self.menu.index
            self.menu = self.new_menu()
            self.menu.index = index

    def apply_font_default(self):
        thai = "th" in (self.loc.code, self.engine_cfg.get("target_lang", "th"))
        render.set_thai_default(thai)
        self.overlay.update()

    def on_menu_action(self, name):
        if name == "quit":
            self.quit()

    def set_ui(self, key, value):
        self.ui.set(key, value)
        self.overlay.update()

    def set_engine(self, key, value):
        self.engine_cfg[key] = value
        threading.Thread(target=self._push, args=({key: value},), daemon=True).start()

    def _push(self, values):
        try:
            self.client.set_config(values)
        except OSError:
            pass

    def make_tray(self):
        from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
        from PySide6.QtWidgets import QMenu, QSystemTrayIcon

        pix = QPixmap(64, 64)
        pix.fill(QColor(0, 0, 0, 0))
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(222, 196, 136))
        p.setPen(QColor(0, 0, 0, 0))
        p.drawRoundedRect(4, 4, 56, 56, 16, 16)
        p.setPen(QColor(44, 33, 18))
        font = p.font()
        font.setBold(True)
        font.setPixelSize(36)
        p.setFont(font)
        p.drawText(pix.rect(), 0x84, "T")
        p.end()
        self.tray = QSystemTrayIcon(QIcon(pix), self.app)
        menu = QMenu()
        self._tray_actions = []
        for key, action in (("tray.toggle", "toggle"), ("tray.mode", "mode"), ("tray.settings", "menu")):
            act = QAction(self.loc.t(key), menu)
            act.triggered.connect(lambda _=False, a=action: self.bridge.action.emit(a))
            menu.addAction(act)
            self._tray_actions.append((act, key))
        menu.addSeparator()
        quit_act = QAction(self.loc.t("tray.quit"), menu)
        quit_act.triggered.connect(self.quit)
        menu.addAction(quit_act)
        self._tray_actions.append((quit_act, "tray.quit"))
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(self.loc.t("app.title"))
        self.tray.show()
        self._tray_menu = menu

    def refresh_tray(self):
        for act, key in self._tray_actions:
            act.setText(self.loc.t(key))

    def quit(self):
        self._stop.set()
        self.hotkeys.stop()
        if self.engine_proc:
            self.client.shutdown()
            try:
                self.engine_proc.wait(3)
            except subprocess.TimeoutExpired:
                self.engine_proc.kill()
        self.app.quit()


def main():
    if not winutil.acquire_single_instance():
        return
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
    winutil.set_dpi_aware()
    from PySide6.QtWidgets import QApplication

    from . import render

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    render.load_fonts()
    controller = Controller(app, UiSettings())
    controller.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
