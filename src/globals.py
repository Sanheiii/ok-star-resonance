from PySide6.QtCore import QObject
from threading import RLock

from ok import Logger

logger = Logger.get_logger(__name__)


class Globals(QObject):

    def __init__(self, exit_event):
        super().__init__()
        self._player_state_lock = RLock()
        self.player_position = None
        self.player_facing = None

    def update_player_transform(self, position=None, facing=None):
        """Update the locally controlled player's transform atomically."""
        with self._player_state_lock:
            if position is not None:
                self.player_position = tuple(float(value) for value in position)
            if facing is not None:
                self.player_facing = float(facing) % 360

    def get_player_transform(self):
        with self._player_state_lock:
            return self.player_position, self.player_facing

if __name__ == "__main__":
    glbs = Globals(exit_event=None)
