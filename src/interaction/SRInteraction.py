import threading
import time

import win32con

from ok import PostMessageInteraction


class SRInteraction(PostMessageInteraction):
    """Background-capable interaction for Star Resonance.

    Keyboard, text, wheel, and button events are delivered by ok-script's
    PostMessage backend. The real cursor is moved with pynput before mouse
    button messages are posted because the game uses the cursor position when
    handling a click.
    """

    _CURSOR_SETTLE_TIME = 0.035

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._input_lock = threading.RLock()
        self._mouse_controller = None

    @property
    def mouse_controller(self):
        if self._mouse_controller is None:
            from pynput import mouse

            self._mouse_controller = mouse.Controller()
        return self._mouse_controller

    def move(self, x, y, down_btn=0):
        """Move the system cursor while keeping PostMessage's target updated."""
        with self._input_lock:
            long_position = self.update_mouse_pos(x, y, True)
            if x >= 0 and y >= 0:
                self.mouse_controller.position = self.capture.get_abs_cords(x, y)
            return long_position

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
        with self._input_lock:
            original_position = None
            if move and move_back:
                original_position = self.mouse_controller.position

            if move:
                long_position = self.move(x, y)
                if x >= 0 and y >= 0:
                    time.sleep(self._CURSOR_SETTLE_TIME)
            else:
                long_position = self.update_mouse_pos(x, y, True)

            button_down, button_flag, button_up = self._button_messages(key)
            try:
                self.post(button_down, button_flag, long_position)
                time.sleep(down_time)
                self.post(button_up, 0, long_position)
            finally:
                if original_position is not None:
                    time.sleep(self._CURSOR_SETTLE_TIME)
                    self.mouse_controller.position = original_position

    @staticmethod
    def _button_messages(key):
        if key == "left":
            return win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, win32con.WM_LBUTTONUP
        if key == "middle":
            return win32con.WM_MBUTTONDOWN, win32con.MK_MBUTTON, win32con.WM_MBUTTONUP
        return win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, win32con.WM_RBUTTONUP

