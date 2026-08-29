import win32con


def parse_numpad_key(key):
    """Return the Windows virtual-key code for ``num0`` through ``num9``."""
    if not isinstance(key, str):
        return None
    normalized = key.lower()
    if normalized.startswith("num"):
        digit = normalized[3:]
        if len(digit) == 1 and digit in "0123456789":
            return win32con.VK_NUMPAD0 + int(digit)
    return None
