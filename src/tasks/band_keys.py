class BandKeyMixin:
    """Send band keys by physical position; see ``src.interaction.physical_keys``."""

    def send_band_key_down(self, key):
        self._send_band_key(key, 'send_physical_key_down', self.send_key_down)

    def send_band_key_up(self, key):
        self._send_band_key(
            key, 'send_physical_key_up', self.send_key_up, check_enabled=False,
        )

    def _send_band_key(self, key, method_name, fallback, check_enabled=True):
        send = getattr(self.executor.interaction, method_name, None)
        if send is None:
            fallback(key)
            return
        # ok-script 3 keeps cancelled jobs active while their cleanup runs.
        self.executor.reset_scene(check_enabled=check_enabled)
        send(key)
