import time
from dataclasses import dataclass

from .api import user32
from .window import client_rect, find_game_window, pid_of_window

SEARCH_INTERVAL = 1.5


@dataclass(frozen=True)
class GameState:
    hwnd: int = 0
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    foreground: bool = False
    running: bool = False


class GameTracker:
    def __init__(self, exe_name):
        self.exe_name = exe_name
        self.state = GameState()
        self._pid = 0
        self._last_search = 0.0
        self.last_seen = time.monotonic()

    def poll(self):
        hwnd = self.state.hwnd
        if hwnd and not user32.IsWindow(hwnd):
            hwnd = 0
        if not hwnd and time.monotonic() - self._last_search > SEARCH_INTERVAL:
            self._last_search = time.monotonic()
            hwnd = find_game_window(self.exe_name) or 0
            self._pid = pid_of_window(hwnd) if hwnd else 0
        if not hwnd:
            self.state = GameState()
            return self.state
        self.last_seen = time.monotonic()
        rect = client_rect(hwnd)
        if not rect or user32.IsIconic(hwnd):
            self.state = GameState(hwnd=hwnd, running=True)
            return self.state
        fg = user32.GetForegroundWindow()
        foreground = bool(fg) and pid_of_window(fg) == self._pid
        self.state = GameState(hwnd, rect[0], rect[1], rect[2], rect[3], foreground, True)
        return self.state
