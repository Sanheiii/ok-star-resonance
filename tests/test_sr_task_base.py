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


if __name__ == "__main__":
    unittest.main()
