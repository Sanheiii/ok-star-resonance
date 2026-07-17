import math
import unittest

from src.tasks.DungeonTasks.Dungeon6593Task import Dungeon6593Task


class NearestEntityTest(unittest.TestCase):
    def test_uses_xz_distance_and_excludes_ignored_attr_id(self):
        task = object.__new__(Dungeon6593Task)
        entities = {
            1: {'attr_id': 34016, 'position': (1, 100, 1)},
            2: {'attr_id': 123, 'position': (6, 100, 8)},
            3: {'attr_id': 456, 'position': (3, 999, 4)},
            4: {'attr_id': 789, 'position': None},
        }

        self.assertEqual(
            task._nearest_entity((0, 0, 0), entities),
            ((3, 999, 4), 5),
        )


class ClearMonstersTest(unittest.TestCase):
    def test_moves_to_each_monster_and_waits_until_it_disappears(self):
        class Task:
            def __init__(self):
                self.position = (0, 0)
                self.moves = []
                self.sleeps = []
                self._entities = iter((
                    {1: {'attr_id': 110809}},
                    {},
                    {2: {'attr_id': 110808}},
                    {},
                ))

            @property
            def nearby_entities(self):
                return next(self._entities)

            @property
            def is_dead(self):
                return False

            def move_to_position(self, start, target, target_tolerance):
                self.moves.append((start, target, target_tolerance))
                self.position = target
                return True

            def sleep(self, seconds):
                self.sleeps.append(seconds)

            def handle_death(self):
                raise AssertionError('alive task should not revive')

        task = Task()
        monsters = (
            (110809, (-9, 15.6)),
            (110808, (-9, -15.6)),
        )

        self.assertTrue(Dungeon6593Task._clear_monsters(task, monsters))
        self.assertEqual(task.moves, [
            ((0, 0), (-9, 15.6), 10),
            ((-9, 15.6), (-9, -15.6), 10),
        ])
        self.assertEqual(task.sleeps, [0.2, 0.2])

    def test_stops_when_death_cannot_be_handled(self):
        class DeadTask:
            position = (0, 0)
            nearby_entities = {1: {'attr_id': 110809}}
            is_dead = True

            def move_to_position(self, _start, _target, target_tolerance):
                return target_tolerance == 10

            def handle_death(self):
                return False

            def sleep(self, _seconds):
                raise AssertionError('should stop after failed revive')

        self.assertFalse(Dungeon6593Task._clear_monsters(
            DeadTask(),
            ((110809, (-9, 15.6)),),
        ))


class DummyAvoidanceTest(unittest.TestCase):
    def test_only_selects_dummy_entities_with_the_expected_attr_id(self):
        entities = {
            1: {'entity_type': 11, 'attr_id': 3400013,
                'position': (1, 2, 3)},
            2: {'entity_type': 1, 'attr_id': 3400013,
                'position': (4, 5, 6)},
            3: {'entity_type': 11, 'attr_id': 123,
                'position': (7, 8, 9)},
            4: {'entity_type': 11, 'attr_id': 3400013,
                'position': None},
        }

        self.assertEqual(
            Dungeon6593Task._dummy_positions(entities),
            [(1, 2, 3)],
        )

    def test_only_triggers_when_a_dummy_is_less_than_six_metres_away(self):
        task = object.__new__(Dungeon6593Task)

        self.assertTrue(task._is_near_any_position(
            (10, 0), ((15.99, 0), (30, 0)), 6))
        self.assertFalse(task._is_near_any_position(
            (10, 0), ((16, 0), (30, 0)), 6))

    def test_finds_first_clockwise_point_far_enough_from_every_dummy(self):
        task = object.__new__(Dungeon6593Task)

        result = task._first_clockwise_safe_position(
            (10, 0),
            ((10, 0), (8, 0)),
            minimum_distance=6,
        )

        self.assertIsNotNone(result)
        result_angle = math.degrees(math.atan2(result[1], result[0])) % 360
        self.assertEqual(result_angle, 323)
        self.assertAlmostEqual(math.hypot(*result), 10)
        for dummy in ((10, 0), (8, 0)):
            self.assertGreaterEqual(math.dist(result, dummy), 6)

    def test_returns_none_when_character_is_at_rotation_origin(self):
        task = object.__new__(Dungeon6593Task)

        self.assertIsNone(task._first_clockwise_safe_position(
            (0, 0),
            ((1, 1),),
            minimum_distance=6,
        ))


class JumpRouteTest(unittest.TestCase):
    def test_presses_q_before_releasing_forward_on_last_segment(self):
        class Task:
            actor_state = None

            def __init__(self):
                self.position = (0, 0, 0)
                self.keys = []

            def move_to_position(self, _start, target, target_tolerance):
                self.position = (target[0], 0, target[1])
                return target_tolerance == 0.5

            def look_at(self, _target):
                return True

            def send_key_down(self, key):
                self.keys.append(('down', key))

            def send_key(self, key):
                self.keys.append(('press', key))

            def send_key_up(self, key):
                self.keys.append(('up', key))

            def sleep(self, _seconds):
                pass

            def log_error(self, _message):
                pass

        task = Task()

        self.assertTrue(Dungeon6593Task._jump_route(
            task,
            ((1, 1), (2, 2), (3, 3)),
        ))
        self.assertEqual(task.keys.count(('press', 'q')), 1)
        q_index = task.keys.index(('press', 'q'))
        self.assertEqual(task.keys[q_index + 1], ('up', 'w'))

    def test_jumps_toward_each_next_position_and_calibrates_landings(self):
        class Task:
            def __init__(self):
                self.position = (0, 0)
                self.moves = []
                self.looks = []
                self.keys = []
                self.sleeps = []

            def move_to_position(self, start, target, target_tolerance):
                self.moves.append((start, target, target_tolerance))
                self.position = target
                return True

            def look_at(self, target):
                self.looks.append(target)
                return True

            def send_key_down(self, key):
                self.keys.append(('down', key))

            def send_key(self, key):
                self.keys.append(('press', key))

            def send_key_up(self, key):
                self.keys.append(('up', key))

            def sleep(self, seconds):
                self.sleeps.append(seconds)

            def log_error(self, _message):
                pass

        task = Task()
        positions = ((1, 1), (2, 2), (3, 3))

        self.assertTrue(Dungeon6593Task._jump_route(task, positions))
        self.assertEqual(task.looks, [(2, 2), (3, 3)])
        self.assertEqual(task.moves, [
            ((0, 0), (1, 1), 1),
            ((1, 1), (2, 2), 1),
            ((2, 2), (3, 3), 1),
        ])
        self.assertEqual(task.keys, [
            ('down', 'w'), ('press', 'space'), ('press', 'space'), ('up', 'w'),
            ('down', 'w'), ('press', 'space'), ('press', 'space'), ('up', 'w'),
        ])
        self.assertEqual(task.sleeps, [0.5, 0.5, 2, 0.5, 0.5, 2])

    def test_releases_forward_key_when_jump_is_interrupted(self):
        class InterruptedTask:
            position = (0, 0)

            def __init__(self):
                self.released = []

            def move_to_position(self, _start, _target, target_tolerance):
                return target_tolerance == 1

            def look_at(self, _target):
                return True

            def send_key_down(self, _key):
                pass

            def send_key(self, _key):
                pass

            def send_key_up(self, key):
                self.released.append(key)

            def sleep(self, _seconds):
                raise RuntimeError('task interrupted')

            def log_error(self, _message):
                pass

        task = InterruptedTask()

        with self.assertRaisesRegex(RuntimeError, 'task interrupted'):
            Dungeon6593Task._jump_route(task, ((1, 1), (2, 2)))
        self.assertEqual(task.released, ['w'])


if __name__ == '__main__':
    unittest.main()
