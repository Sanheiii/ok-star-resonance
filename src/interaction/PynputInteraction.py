from ok.device.interaction_methods.pynput import PynputInteraction as OkPynputInteraction

from src.interaction.mouse_keys import parse_mouse_key
from src.interaction.numpad_keys import parse_numpad_key


class PynputInteraction(OkPynputInteraction):
    """Project pynput backend with keyboard-style mouse button support."""

    def _parse_key(self, key):
        virtual_key = parse_numpad_key(key)
        if virtual_key is not None:
            from pynput import keyboard

            return keyboard.KeyCode.from_vk(virtual_key)
        return super()._parse_key(key)

    def send_key(self, key, down_time=0.01):
        mouse_key = parse_mouse_key(key)
        if mouse_key is not None:
            self.click(0.5, 0.5, down_time=down_time, key=mouse_key)
            return
        super().send_key(key, down_time)

    def send_key_down(self, key):
        mouse_key = parse_mouse_key(key)
        if mouse_key is not None:
            self.mouse_down(0.5, 0.5, key=mouse_key)
            return
        super().send_key_down(key)

    def send_key_up(self, key):
        mouse_key = parse_mouse_key(key)
        if mouse_key is not None:
            self.mouse_up(key=mouse_key)
            return
        super().send_key_up(key)

    @staticmethod
    def get_mouse_button(key):
        from pynput import mouse

        buttons = {
            "left": mouse.Button.left,
            "middle": mouse.Button.middle,
            "right": mouse.Button.right,
            "x1": mouse.Button.x1,
            "x2": mouse.Button.x2,
        }
        try:
            return buttons[key]
        except KeyError as exc:
            raise ValueError(f"Unsupported mouse button: {key}") from exc
