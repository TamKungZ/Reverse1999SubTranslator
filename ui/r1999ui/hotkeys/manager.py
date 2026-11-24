import ctypes
import threading
from ctypes import wintypes

from ..winutil.api import HOOKPROC, IS_WINDOWS, kernel32, user32
from .keys import MODIFIER_KEYS, MODS, parse_hotkey

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_QUIT = 0x0012
LLKHF_INJECTED = 0x10
KEY_DOWN_BIT = 0x8000


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HotkeyManager:
    """Global hotkeys through a low level keyboard hook, active only while `is_active()` is true."""

    def __init__(self, hotkeys, nav_keys, is_active, emit):
        self.bindings = [(*parse_hotkey(combo), action) for action, combo in hotkeys.items()]
        self.nav = {parse_hotkey(combo)[1]: action for action, combo in nav_keys.items()}
        self.is_active = is_active
        self.emit = emit
        self.modal = False
        self.error = ""
        self._swallowed = set()
        self._thread = None
        self._thread_id = 0
        self._hook = None
        self._proc = None
        self._ready = threading.Event()

    def start(self):
        if not IS_WINDOWS:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(3)

    def stop(self):
        if IS_WINDOWS and self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

    def _held_mods(self):
        return frozenset(vk for vk in MODS.values() if user32.GetAsyncKeyState(vk) & KEY_DOWN_BIT)

    def _match(self, vk):
        if self.modal and vk in self.nav:
            return "nav:" + self.nav[vk]
        if vk in MODIFIER_KEYS:
            return None
        held = self._held_mods()
        for mods, key, action in self.bindings:
            if key == vk and mods == held:
                return action
        return None

    def _on_key_down(self, info):
        if info.flags & LLKHF_INJECTED or not self.is_active():
            return False
        action = self._match(info.vkCode)
        if not action:
            return False
        self._swallowed.add(info.vkCode)
        self.emit(action)
        return True

    def _on_key_up(self, info):
        if info.vkCode not in self._swallowed:
            return False
        self._swallowed.discard(info.vkCode)
        return True

    def _callback(self, code, wparam, lparam):
        if code == 0:
            info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                swallow = self._on_key_down(info)
            elif wparam in (WM_KEYUP, WM_SYSKEYUP):
                swallow = self._on_key_up(info)
            else:
                swallow = False
            if swallow:
                return 1
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _run(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        self._proc = HOOKPROC(self._callback)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not self._hook:
            self.error = "SetWindowsHookEx failed (%d)" % ctypes.get_last_error()
            self._ready.set()
            return
        self._ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        user32.UnhookWindowsHookEx(self._hook)
