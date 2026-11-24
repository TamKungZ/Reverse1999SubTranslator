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
MODIFIER_KEYS = (0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5)


def parse_hotkey(text):
    parts = [p.strip().upper() for p in text.split("+") if p.strip()]
    mods = frozenset(MODS[p] for p in parts if p in MODS)
    keys = [p for p in parts if p not in MODS]
    if len(keys) != 1 or keys[0] not in VK:
        raise ValueError("invalid hotkey: %s" % text)
    return mods, VK[keys[0]]
