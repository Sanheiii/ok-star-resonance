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


class JumpRouteTest(unittest.TestCase):
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
