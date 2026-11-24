import ctypes

from .api import IS_WINDOWS, kernel32, user32

ERROR_ALREADY_EXISTS = 183
MB_OK, MB_ICONINFORMATION, MB_SETFOREGROUND = 0x0, 0x40, 0x10000

_instance_mutex = None


def show_message(text, title):
    """A plain message box, for use before the interface exists."""
    if IS_WINDOWS:
        user32.MessageBoxW(None, text, title, MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND)


def acquire_single_instance(name="Local\\R1999Translator.UI"):
    """True if this is the only running UI; the mutex is held until the process exits."""
    global _instance_mutex
    if not IS_WINDOWS:
        return True
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        return True
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _instance_mutex = handle
    return True


def set_dpi_aware():
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
