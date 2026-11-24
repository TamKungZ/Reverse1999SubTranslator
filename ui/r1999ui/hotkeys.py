import ctypes
import sys
import threading
from ctypes import wintypes

IS_WINDOWS = sys.platform == "win32"

VK = {
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27, "ENTER": 0x0D, "ESC": 0x1B,
    "BACKSPACE": 0x08, "TAB": 0x09, "SPACE": 0x20, "INSERT": 0x2D, "DELETE": 0x2E,
    "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
}
for _i in range(1, 13):
    VK["F%d" % _i] = 0x6F + _i
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
    VK[_c] = ord(_c)
MODS = {"CTRL": 0x11, "ALT": 0x12, "SHIFT": 0x10}

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_QUIT = 0x0012
LLKHF_INJECTED = 0x10


def parse_hotkey(text):
    parts = [p.strip().upper() for p in text.split("+") if p.strip()]
    mods = frozenset(MODS[p] for p in parts if p in MODS)
    keys = [p for p in parts if p not in MODS]
    if len(keys) != 1 or keys[0] not in VK:
        raise ValueError("invalid hotkey: %s" % text)
    return mods, VK[keys[0]]


if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    LRESULT = ctypes.c_ssize_t
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.CallNextHookEx.restype = LRESULT
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE


class HotkeyManager:
    def __init__(self, hotkeys, nav_keys, is_active, emit):
        self.bindings = [(*parse_hotkey(combo), action) for action, combo in hotkeys.items()]
        self.nav = {parse_hotkey(combo)[1]: action for action, combo in nav_keys.items()}
        self.is_active = is_active
        self.emit = emit
        self.modal = False
        self._swallowed = set()
        self._thread = None
        self._thread_id = 0
        self._hook = None
        self._proc = None
        self._ready = threading.Event()
        self.error = ""

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
        return frozenset(vk for vk in MODS.values() if user32.GetAsyncKeyState(vk) & 0x8000)

    def _match(self, vk):
        if self.modal and vk in self.nav:
            return "nav:" + self.nav[vk]
        if vk in (0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5):
            return None
        held = self._held_mods()
        for mods, key, action in self.bindings:
            if key == vk and mods == held:
                return action
        return None

    def _callback(self, code, wparam, lparam):
        if code == 0:
            info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = info.vkCode
            if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                if not (info.flags & LLKHF_INJECTED) and self.is_active():
                    action = self._match(vk)
                    if action:
                        self._swallowed.add(vk)
                        self.emit(action)
                        return 1
            elif wparam in (WM_KEYUP, WM_SYSKEYUP):
                if vk in self._swallowed:
                    self._swallowed.discard(vk)
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
