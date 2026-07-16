import unittest
from unittest.mock import patch

from src.packet_capture.parser import ActorState
from src.tasks import SRTaskBase as sr_task_base_module
from src.tasks.SRTaskBase import SRTaskBase


class _WaitTask:
    def __init__(self, states):
        self._states = iter(states)
        self._in_combat = None
        self.capture_checks = 0

    @property
    def in_combat(self):
        self._in_combat = next(self._states)
        return self._in_combat

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


class CapturedStatePropertyTest(unittest.TestCase):
    def test_exposes_combat_and_actor_states(self):
        class CaptureData:
            @staticmethod
            def get_combat_state():
                return 1

            @staticmethod
            def get_actor_state():
                return ActorState.DEAD

        task = object.__new__(SRTaskBase)
        with patch.object(
                sr_task_base_module.og,
                "packet_capture_data",
                CaptureData(),
                create=True):
            self.assertEqual(task.in_combat, 1)
            self.assertEqual(task.actor_state, ActorState.DEAD)
            self.assertTrue(task.is_dead)


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


class _LookAtTask:
    _xz = staticmethod(SRTaskBase._xz)
    _angle_delta = staticmethod(SRTaskBase._angle_delta)

    def __init__(self, camera_direction=0, position=(0, 0), detected=True):
        self.camera_direction = camera_direction
        self.position = position
        self._camera_direction_detected = detected
        self.rotations = []
        self.capture_checks = 0
        self.frame_count = 0

    def _require_packet_capture(self):
        self.capture_checks += 1

    def next_frame(self):
        self.frame_count += 1

    def detect_camera_direction(self):
        return self.camera_direction

    def rotate_camera(self, degrees):
        self.rotations.append(degrees)


class LookAtTest(unittest.TestCase):
    def test_looks_at_absolute_angle_using_shortest_turn(self):
        task = _LookAtTask(camera_direction=350)

        result = SRTaskBase.look_at(task, 10)

        self.assertTrue(result)
        self.assertEqual(task.rotations, [20])
        self.assertEqual(task.capture_checks, 0)

    def test_looks_at_world_position(self):
        task = _LookAtTask(camera_direction=0, position=(10, 5, 20))

        result = SRTaskBase.look_at(task, (20, 99, 20))

        self.assertTrue(result)
        self.assertEqual(task.rotations, [90])
        self.assertEqual(task.capture_checks, 1)

    def test_does_not_rotate_when_direction_detection_fails(self):
        task = _LookAtTask(camera_direction=123, detected=False)

        result = SRTaskBase.look_at(task, 90)

        self.assertFalse(result)
        self.assertEqual(task.rotations, [])

    def test_same_position_needs_no_camera_detection(self):
        task = _LookAtTask(position=(10, 20))

        result = SRTaskBase.look_at(task, (10, 20))

        self.assertTrue(result)
        self.assertEqual(task.frame_count, 0)
        self.assertEqual(task.rotations, [])


if __name__ == "__main__":
    unittest.main()
