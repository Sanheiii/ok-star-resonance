from collections import defaultdict, deque
import time


class MidiKeyState:
    """Track note instances separately from the physical keys they currently own."""

    def __init__(self, key_down, key_up, sleep, clock=time.monotonic, min_hold=0.04):
        self.key_down = key_down
        self.key_up = key_up
        self.sleep = sleep
        self.pending = defaultdict(deque)
        self.owners = {}
        self.clock = clock
        self.min_hold = min_hold
        self.started = {}

    def _release(self, key):
        remaining = self.min_hold - (self.clock() - self.started[key])
        if remaining > 0:
            self.sleep(remaining)
        self.key_up(key)
        del self.owners[key]
        del self.started[key]

    def note_on(self, channel, pitch, key):
        token = object()
        self.pending[channel, pitch].append(token)
        if key is None:
            return
        if key in self.owners:
            self._release(key)
            # Give the game a visible release before retriggering the same key.
            self.sleep(0.033)
        # Register before sending, so cleanup also covers a partially failed send.
        self.owners[key] = token
        self.started[key] = self.clock()
        self.key_down(key)
        self.started[key] = self.clock()

    def note_off(self, channel, pitch):
        identity = channel, pitch
        queue = self.pending.get(identity)
        if not queue:
            return
        token = queue.popleft()
        if not queue:
            del self.pending[identity]
        for key, owner in list(self.owners.items()):
            if owner is token:
                self._release(key)
                break

    def release_all(self):
        # Keep pending note instances: their later note_off must not stop new notes.
        error = None
        for key in list(self.owners):
            try:
                self.key_up(key)
            except Exception as exc:
                if error is None:
                    error = exc
            else:
                del self.owners[key]
                self.started.pop(key, None)
        if error is not None:
            raise error
