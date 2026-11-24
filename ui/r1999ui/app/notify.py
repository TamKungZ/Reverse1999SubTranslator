from ..winutil import IS_WINDOWS


def beep(warning=False):
    if not IS_WINDOWS:
        return
    import winsound

    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION if warning else winsound.MB_ICONASTERISK)
