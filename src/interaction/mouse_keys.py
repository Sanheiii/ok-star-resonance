MOUSE_KEY_MAP = {
    "mouse_left": "left",
    "mouse1": "left",
    "lbutton": "left",
    "mouse_middle": "middle",
    "mouse3": "middle",
    "mbutton": "middle",
    "middle": "middle",
    "mouse_right": "right",
    "mouse2": "right",
    "rbutton": "right",
    "mouse_x1": "x1",
    "mouse4": "x1",
    "x1": "x1",
    "xbutton1": "x1",
    "mouse_x2": "x2",
    "mouse5": "x2",
    "x2": "x2",
    "xbutton2": "x2",
}


def parse_mouse_key(key):
    """Return a mouse button name for explicit keyboard-style mouse keys."""
    if not isinstance(key, str):
        return None
    return MOUSE_KEY_MAP.get(key.lower())
