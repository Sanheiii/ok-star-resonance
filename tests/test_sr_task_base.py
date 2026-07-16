import unittest

from src.tasks.SRTaskBase import SRTaskBase


class _WaitTask:
    def __init__(self, states):
        self._states = iter(states)
        self._combat_state = None
        self.capture_checks = 0

    @property
    def combat_state(self):
        self._combat_state = next(self._states)
        return self._combat_state

    def _require_packet_capture(self):
        self.capture_checks += 1

    def wait_until(self, condition, time_out=0):
        self.time_out = time_out
        for _ in range(10):
            if condition():
                return True
        return None


class WaitOutOfCombatTest(unittest.TestCase):
    def test_waits_through_unknown_and_combat_until_zero(self):
        task = _WaitTask([None, 1, 0])

        result = SRTaskBase.wait_out_of_combat(task, time_out=12)

        self.assertTrue(result)
        self.assertEqual(task.time_out, 12)
        self.assertEqual(task.capture_checks, 4)

    def test_returns_false_when_zero_is_not_seen(self):
        task = _WaitTask([1] * 10)

        self.assertFalse(SRTaskBase.wait_out_of_combat(task, time_out=1))


class _PathTask:
    def __init__(self, results):
        self.position = (0, 0)
        self.results = iter(results)
        self.calls = []

    def _begin_movement_session(self):
        pass

    def _end_movement_session(self):
        pass

    def _release_move_keys(self):
        pass

    def sleep(self, _seconds):
        pass

    def move_to_position(self, start, target, **_kwargs):
        self.calls.append((start, target))
        return next(self.results)


class MovementReturnValueTest(unittest.TestCase):
    def test_path_returns_current_and_later_nodes_after_death(self):
        task = _PathTask([True, False])
        nodes = [(1, 1), (2, 2), (3, 3)]

        remaining = SRTaskBase.move_to_positions(task, nodes)

        self.assertEqual(remaining, [(2, 2), (3, 3)])

    def test_completed_path_returns_none(self):
        task = _PathTask([True, True])

        self.assertIsNone(SRTaskBase.move_to_positions(task, [(1, 1), (2, 2)]))

    def test_direct_move_releases_keys_before_returning_on_death(self):
        class DirectTask:
            _xz = staticmethod(SRTaskBase._xz)
            position = (0, 0)
            is_dead = True
            camera_direction = 0
            release_count = 0

            def _release_move_keys(self):
                self.release_count += 1

            def _require_packet_capture(self):
                pass

            def next_frame(self):
                pass

            def detect_camera_direction(self):
                pass

        task = DirectTask()

        result = SRTaskBase._move_direct(task, (0, 0), tolerance=1)

        self.assertFalse(result)
        self.assertEqual(task.release_count, 2)


if __name__ == "__main__":
    unittest.main()
