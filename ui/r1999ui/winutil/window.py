import ctypes
import os
from ctypes import wintypes

from .api import ENUMPROC, kernel32, user32

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011
HWND_TOPMOST = -1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

MIN_GAME_WIDTH, MIN_GAME_HEIGHT = 400, 300


def exe_name_of_pid(pid):
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(handle)


def pid_of_window(hwnd):
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def client_rect(hwnd):
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    origin = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        return None
    return origin.x, origin.y, rect.right - rect.left, rect.bottom - rect.top


def find_game_window(exe_name):
    wanted = exe_name.lower()
    found = []

    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            rect = client_rect(hwnd)
            if rect and rect[2] >= MIN_GAME_WIDTH and rect[3] >= MIN_GAME_HEIGHT:
                if exe_name_of_pid(pid_of_window(hwnd)) == wanted:
                    found.append((rect[2] * rect[3], hwnd))
        return True

    user32.EnumWindows(ENUMPROC(visit), 0)
    return max(found)[1] if found else None


def prepare_overlay_window(hwnd):
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)
    user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
    keep_topmost(hwnd)


def keep_topmost(hwnd):
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
