import subprocess
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

from .. import render, winutil
from ..client import EngineClient
from ..hotkeys import HotkeyManager
from ..i18n import Locale
from ..menu import MenuModel
from ..overlay import OverlayWindow
from .download import run_download_dialog
from .fonts import fonts_for_language
from .frames import FrameLoop
from .launcher import launch_engine
from .tray import Tray

BOOT_ATTEMPTS = 240
BOOT_POLL = 0.5
GAME_POLL_MS = 200
AUTO_EXIT_AFTER = 10


class Bridge(QObject):
    view = Signal(object)
    action = Signal(str)
    toast = Signal(str)
    ready = Signal(object)


class Controller:
    def __init__(self, app, ui):
        self.app, self.ui = app, ui
        self.loc = Locale(ui["locale"])
        self.client = EngineClient(ui["engine_port"])
        self.engine_proc = None
        self.engine_cfg = {}
        self.languages = {}
        self.region = (0.19, 0.78, 0.90, 1.0)
        self.is_ready = False
        self.menu = None
        self.tray = None
        self._stop = threading.Event()
        self.bridge = Bridge()
        self.overlay = OverlayWindow(ui)
        self.tracker = winutil.GameTracker(ui["game_exe"]) if winutil.IS_WINDOWS else None
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
        self.timer.setInterval(GAME_POLL_MS)
        self.timer.timeout.connect(self.poll_game)

    def start(self):
        self.tray = Tray(self.app, self.loc, self.bridge.action.emit, self.quit)
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
        for _ in range(BOOT_ATTEMPTS):
            if self._stop.is_set():
                return
            try:
                info = self.client.info()
                if info["state"] not in ("starting", "loading"):
                    break
            except OSError:
                pass
            time.sleep(BOOT_POLL)
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
            if run_download_dialog(self.client, self.loc):
                self.mark_ready()
            else:
                self.quit()
        elif info["state"] == "error":
            self.overlay.toast(self.loc.t("toast.engine_error", error=info["error"][:80]), 6000)
        else:
            self.mark_ready()

    def mark_ready(self):
        self.is_ready = True
        self.overlay.toast(self.loc.t("toast.ready", key=self.ui["hotkeys"]["menu"]), 3000)
        loop = FrameLoop(self.ui, self.client, self.tracker, self.region, self._stop, self.bridge.view.emit)
        threading.Thread(target=loop.run, daemon=True).start()

    def poll_game(self):
        if not self.tracker:
            return
        state = self.tracker.poll()
        self.overlay.set_game(state)
        if self.ui["auto_exit"] and not state.running and time.monotonic() - self.tracker.last_seen > AUTO_EXIT_AFTER:
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
        fonts = fonts_for_language(self.engine_cfg.get("target_lang", "th"))
        return MenuModel(self.ui, self.engine_cfg, self.loc, self.languages, fonts, self.on_change, self.on_menu_action)

    def on_change(self, src, key, value):
        if src == "ui":
            self.set_ui(key, value)
            if key == "locale":
                self.loc.set(value)
                self.tray.refresh()
        else:
            self.set_engine(key, value)
        if key in ("locale", "target_lang"):
            self.apply_font_default()
            if self.menu:
                index = self.menu.index
                self.menu = self.new_menu()
                self.menu.index = index

    def apply_font_default(self):
        render.set_thai_default("th" in (self.loc.code, self.engine_cfg.get("target_lang", "th")))
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
