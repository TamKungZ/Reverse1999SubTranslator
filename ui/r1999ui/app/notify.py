from pathlib import Path

from ..winutil import IS_WINDOWS

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def beep(warning=False):
    if not IS_WINDOWS:
        return
    import winsound

    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION if warning else winsound.MB_ICONASTERISK)


def cue(name):
    """The short sound of a hotkey: `on` and `off` for switching the translation, `switch` for changing the mode."""
    if not IS_WINDOWS:
        return
    import winsound

    winsound.PlaySound(str(ASSETS / (name + ".wav")), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
