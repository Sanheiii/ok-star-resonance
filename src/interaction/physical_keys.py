import ctypes
from ctypes import wintypes

# Band note and paging keys mapped to their US keyboard positions (set 1 scan codes).
# The game binds the band keys by physical position and labels each key for the active layout,
# so typing the character instead presses a different key on non-US layouts
# (e.g. "[" lands on the US "]" position on a Japanese layout, "z" on the US "y" position on German).
US_SCAN_CODES = {
    '1': 0x02, '2': 0x03, '3': 0x04, '4': 0x05, '5': 0x06,
    '6': 0x07, '7': 0x08, '8': 0x09, '9': 0x0A, '0': 0x0B,
    'q': 0x10, 'w': 0x11, 'e': 0x12, 'r': 0x13, 't': 0x14, 'y': 0x15, 'u': 0x16,
    'i': 0x17, 'o': 0x18, 'p': 0x19, '[': 0x1A, ']': 0x1B,
    'a': 0x1E, 's': 0x1F, 'd': 0x20, 'f': 0x21, 'g': 0x22, 'h': 0x23, 'j': 0x24,
    'z': 0x2C, 'x': 0x2D, 'c': 0x2E, 'v': 0x2F, 'b': 0x30, 'n': 0x31, 'm': 0x32,
    ',': 0x33, '.': 0x34,
}

_MAPVK_VSC_TO_VK_EX = 3

_user32 = ctypes.WinDLL('user32', use_last_error=True)
_user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.GetKeyboardLayout.argtypes = (wintypes.DWORD,)
_user32.GetKeyboardLayout.restype = wintypes.HKL
_user32.MapVirtualKeyExW.argtypes = (wintypes.UINT, wintypes.UINT, wintypes.HKL)
_user32.MapVirtualKeyExW.restype = wintypes.UINT
_user32.GetForegroundWindow.argtypes = ()
_user32.GetForegroundWindow.restype = wintypes.HWND


def us_scan_code(key):
    try:
        return US_SCAN_CODES[str(key).lower()]
    except KeyError:
        raise ValueError(f"Not a band key: {key!r}") from None


def virtual_key_for_scan(scan_code, hwnd):
    """Virtual key that the keyboard layout of ``hwnd`` assigns to ``scan_code``."""
    thread_id = _user32.GetWindowThreadProcessId(hwnd, None)
    layout = _user32.GetKeyboardLayout(thread_id)
    virtual_key = _user32.MapVirtualKeyExW(scan_code, _MAPVK_VSC_TO_VK_EX, layout)
    if not virtual_key:
        raise ValueError(f"Scan code 0x{scan_code:02X} has no key in keyboard layout {layout}")
    return virtual_key


def foreground_window():
    return _user32.GetForegroundWindow()
