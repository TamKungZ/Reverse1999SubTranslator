import subprocess
import threading
import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QMessageBox, QSystemTrayIcon

from .. import render, winutil
from ..capture import ScreenGrabber
from ..client import EngineClient
from ..hotkeys import HotkeyManager
from ..i18n import Locale
from ..menu import MenuModel
from ..overlay import OverlayWindow
from .download import run_download_dialog
from .frames import FrameLoop
from .icon import app_icon
from .launcher import launch_engine
from .notify import beep, cue
from .screenshot import take
from .tray import Tray

BOOT_ATTEMPTS = 240
BOOT_POLL = 0.5
GAME_POLL_MS = 200
AUTO_EXIT_AFTER = 10
ENGINE_CHOICES = {"target_lang", "translator"}


class Bridge(QObject):
    view = Signal(object)
    action = Signal(str)
    toast = Signal(str)
    ready = Signal(object)
    notice = Signal(str, bool)


class Controller:
    def __init__(self, app, ui):
        self.app, self.ui = app, ui
        self.loc = Locale(ui["locale"])
        self.client = EngineClient(ui["engine_port"])
        self.engine_proc = None
        self.engine_cfg = {}
        self.languages = {}
        self.scripts = {}
        self.language_fonts = {}
        self.region = (0.08, 0.78, 0.90, 1.0)
        self.is_ready = False
        self.frame_loop = None
        self.previous = None
        self.notice = None
        self.grabber = None
        self.watching = False
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
        self.bridge.notice.connect(self.notify)
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
            self.notify(self.loc.t("toast.hotkey_error", error=self.hotkeys.error), warning=True)
        if self.ui["startup_notice"]:
            self.show_startup_notice()

    def show_startup_notice(self):
        keys = self.ui["hotkeys"]
        text = self.loc.t("startup.text", menu=keys["menu"], screenshot=keys["screenshot"])
        box = QMessageBox(QMessageBox.Icon.Information, self.loc.t("app.title"), text)
        box.setWindowIcon(app_icon())
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        never = QCheckBox(self.loc.t("startup.never"))
        box.setCheckBox(never)
        box.finished.connect(lambda _: self.set_ui("startup_notice", False) if never.isChecked() else None)
        self.notice = box
        box.show()

    def notify(self, text, warning=False):
        """A message in the corner of the screen, with a sound unless the sounds are off."""
        if self.tray:
            icon = QSystemTrayIcon.MessageIcon.Warning if warning else QSystemTrayIcon.MessageIcon.Information
            self.tray.icon.showMessage(self.loc.t("app.title"), text, icon, 5000)
        if self.ui["sounds"]:
            beep(warning)

    def boot(self):
        try:
            self.client.info()
        except OSError:
            self.engine_proc = launch_engine(self.ui["engine_port"])
        self.bridge.ready.emit(self.wait_for_engine())

    def wait_for_engine(self):
        info = None
        for _ in range(BOOT_ATTEMPTS):
            if self._stop.is_set():
                return None
            try:
                info = self.client.info()
                if info["state"] not in ("starting", "loading"):
                    break
            except OSError:
                pass
            time.sleep(BOOT_POLL)
        return info

    def on_ready(self, info):
        if not info:
            self.overlay.toast(self.loc.t("toast.engine_failed"), 5000)
            self.notify(self.loc.t("toast.engine_failed"), warning=True)
            return
        if not self.engine_cfg:
            self.engine_cfg.update(info["config"])
        self.scripts = info.get("scripts", {})
        self.language_fonts = info.get("fonts", {})
        self.languages = info["languages"]
        self.region = tuple(self.engine_cfg["region"])
        self.apply_font_default()
        if info["state"] == "model_missing":
            self.ask_model()
        elif info["state"] == "error":
            self.overlay.toast(self.loc.t("toast.engine_error", error=info["error"][:80]), 6000)
            self.notify(self.loc.t("toast.engine_error", error=info["error"][:200]), warning=True)
        else:
            self.mark_ready()
        if self.engine_cfg.get("translator") != info.get("translator", self.engine_cfg.get("translator")):
            text = self.loc.t("toast.translator_unavailable", lang=self.languages.get(self.engine_cfg["target_lang"], ""))
            self.overlay.toast(text, 5000)
            self.notify(text, warning=True)

    def ask_model(self):
        beep()
        if run_download_dialog(self.client, self.loc):
            self.mark_ready()
        elif not self.is_ready:
            self.quit()
        elif self.previous and self.previous[1] != self.engine_cfg.get(self.previous[0]):
            self.set_engine(*self.previous)

    def mark_ready(self):
        self.is_ready = True
        self.overlay.toast(self.loc.t("toast.ready", key=self.ui["hotkeys"]["menu"]), 3000)
        self.notify(self.loc.t("notify.ready", key=self.ui["hotkeys"]["menu"]))
        self.watch_background()
        if self.frame_loop is None:
            self.frame_loop = FrameLoop(self.ui, self.client, self.tracker, self.region, self._stop, self.bridge.view.emit)
            threading.Thread(target=self.frame_loop.run, daemon=True).start()

    def watch_background(self):
        """Says when the other translator has been downloaded and loaded, which goes on after the program is usable."""
        if not self.watching:
            self.watching = True
            threading.Thread(target=self._watch_background, daemon=True).start()

    def _watch_background(self):
        announced = False
        while not self._stop.wait(2.0):
            try:
                background = self.client.info()["background"]
            except (OSError, KeyError):
                continue
            name = self.loc.t("opt.translator." + background["translator"]) if background["translator"] else ""
            if background["state"] == "downloading" and not announced:
                announced = True
                self.bridge.notice.emit(self.loc.t("notify.background_start", name=name, mb=max(1, background["total"] >> 20)), False)
            elif background["state"] in ("error", "cancelled"):
                self.bridge.notice.emit(self.loc.t("notify.background_failed", name=name), True)
                break
            elif background["loaded"]:
                if announced:
                    self.bridge.notice.emit(self.loc.t("notify.background_done", name=name), False)
                break
        self.watching = False

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
            self.play_cue("on" if self.ui["enabled"] else "off")
            self.overlay.toast(self.loc.t("toast.translation", state=self.loc.t("val.on" if self.ui["enabled"] else "val.off")))
        elif action == "mode":
            new = "word" if self.engine_cfg.get("mode") == "sentence" else "sentence"
            self.set_engine("mode", new)
            self.play_cue("switch")
            self.overlay.toast(self.loc.t("toast.mode", mode=self.loc.t("opt.mode." + new)))
        elif action == "menu":
            self.toggle_menu()
        elif action == "screenshot":
            self.screenshot()
        elif action.startswith("nav:") and self.menu:
            key = action[4:]
            if key == "back":
                self.toggle_menu()
            else:
                self.menu.handle(key)
                self.overlay.set_menu(self.menu.rows())

    def play_cue(self, name):
        if self.ui["sounds"]:
            cue(name)

    def screenshot(self):
        state = self.tracker.state if self.tracker else None
        if state is None or state.w <= 0:
            return
        self.grabber = self.grabber or ScreenGrabber()
        path = take(self.grabber, state, self.overlay.state)
        if path:
            self.overlay.toast(self.loc.t("toast.screenshot"), 2500)
            self.notify(self.loc.t("notify.screenshot", path=path))
        else:
            self.notify(self.loc.t("notify.screenshot_failed"), warning=True)

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
        lang = self.engine_cfg.get("target_lang", "th")
        fonts = render.families_for(lang, self.scripts.get(lang))
        return MenuModel(self.ui, self.engine_cfg, self.loc, self.languages, fonts, self.on_change, self.on_menu_action)

    def on_change(self, src, key, value):
        if src == "ui":
            self.set_ui(key, value)
            if key == "enabled":
                self.play_cue("on" if value else "off")
            if key == "locale":
                self.loc.set(value)
                self.tray.refresh()
        else:
            if key in ENGINE_CHOICES:
                self.previous = (key, self.engine_cfg.get(key))
                self.notify(self.loc.t("notify.loading"))
            self.set_engine(key, value)
        if key in ("locale", "target_lang"):
            self.apply_font_default()
            if self.menu:
                index = self.menu.index
                self.menu = self.new_menu()
                self.menu.index = index

    def apply_font_default(self):
        codes = dict.fromkeys([self.engine_cfg.get("target_lang"), self.loc.code])
        render.set_languages([(c, self.scripts[c], self.language_fonts.get(c, [])) for c in codes if c in self.scripts])
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
            return
        if ENGINE_CHOICES & set(values):
            self.bridge.ready.emit(self.wait_for_engine())

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
