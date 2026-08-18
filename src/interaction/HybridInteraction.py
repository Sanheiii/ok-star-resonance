import win32api
import win32con

from ok import PostMessageInteraction
from src.interaction.mouse_keys import parse_mouse_key


class HybridInteraction(PostMessageInteraction):
    """PostMessage input with real-cursor positioning for mouse actions."""

    _MODIFIER_KEYS = {
        win32con.VK_LSHIFT: (win32con.VK_LSHIFT, 0x2A, False),
        win32con.VK_RSHIFT: (win32con.VK_RSHIFT, 0x36, False),
        win32con.VK_LCONTROL: (win32con.VK_CONTROL, 0x1D, False),
        win32con.VK_RCONTROL: (win32con.VK_CONTROL, 0x1D, True),
        win32con.VK_LMENU: (win32con.VK_MENU, 0x38, False),
        win32con.VK_RMENU: (win32con.VK_MENU, 0x38, True),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mouse_controller = None

    @property
    def mouse_controller(self):
        if self._mouse_controller is None:
            from pynput import mouse

            self._mouse_controller = mouse.Controller()
        return self._mouse_controller

    def send_key_down(self, key, activate=True):
        mouse_key = parse_mouse_key(key)
        if mouse_key is not None:
            self.mouse_down(*self._screen_center(), key=mouse_key)
            return
        if activate:
            self.try_activate()
        virtual_key, lparam = self._keyboard_message(key, is_up=False)
        self.post(win32con.WM_KEYDOWN, virtual_key, lparam)

    def send_key_up(self, key):
        mouse_key = parse_mouse_key(key)
        if mouse_key is not None:
            self.mouse_up(key=mouse_key)
            return
        virtual_key, lparam = self._keyboard_message(key, is_up=True)
        self.post(win32con.WM_KEYUP, virtual_key, lparam)

    def send_key(self, key, down_time=0.02):
        mouse_key = parse_mouse_key(key)
        if mouse_key is not None:
            self.click(*self._screen_center(), down_time=down_time, key=mouse_key)
            return
        super().send_key(key, down_time)

    def _keyboard_message(self, key, is_up):
        virtual_key = self.get_key_by_str(key)
        message_key, scan_code, extended = self._MODIFIER_KEYS.get(
            virtual_key,
            (virtual_key, win32api.MapVirtualKey(virtual_key, 0), False),
        )
        lparam = (scan_code << 16) | 1
        if extended:
            lparam |= 1 << 24
        if is_up:
            lparam |= (1 << 30) | (1 << 31)
        return message_key, lparam

    def _screen_center(self):
        return self.capture.width // 2, self.capture.height // 2

    def _move_with_pynput(self, x, y):
        if x >= 0 and y >= 0:
            self.mouse_controller.position = self.capture.get_abs_cords(x, y)

    def click(
        self,
        x=-1,
        y=-1,
        move_back=False,
        name=None,
        down_time=0.01,
        move=True,
        key="left",
    ):
        self._move_with_pynput(x, y)
        return super().click(
            x,
            y,
            move_back=move_back,
            name=name,
            down_time=down_time,
            move=move,
            key=key,
        )

    def mouse_down(self, x=-1, y=-1, name=None, key="left"):
        self._move_with_pynput(x, y)
        return super().mouse_down(x, y, name=name, key=key)
