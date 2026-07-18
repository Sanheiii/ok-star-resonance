import unittest

from src.tasks.DungeonTasks.Dungeon1234Task import Dungeon1234Task


class Dungeon1234TaskTest(unittest.TestCase):
    def test_wait_for_entity_position_finds_matching_boss(self):
        class Task:
            nearby_entities = {
                1: {'attr_id': 123, 'position': (1, 2, 3)},
                2: {'attr_id': 1985, 'position': (4, 5, 6)},
            }

            def wait_until(self, condition, time_out):
                self.time_out = time_out
                return condition()

        task = Task()

        self.assertEqual(
            Dungeon1234Task._wait_for_entity_position(task, 1985, 15),
            (4, 5, 6),
        )
        self.assertEqual(task.time_out, 15)

    def test_follow_route_uses_all_coordinates_in_order(self):
        class Task:
            def __init__(self):
                self.info = {}
                self.calls = []

            def move_to_positions(self, positions, **kwargs):
                self.calls.append((tuple(positions), kwargs))
                return None

            def log_error(self, _message):
                raise AssertionError('successful movement must not log an error')

        task = Task()
        route = ((1.0, 2.0), (3.0, 4.0))

        self.assertTrue(Dungeon1234Task._follow_route(task, route, '测试路线'))
        self.assertEqual(task.info['State'], '测试路线')
        self.assertEqual(task.calls, [(route, {
            'node_tolerance': 2,
            'max_path_deviation': 8,
            'enable_sprint': True,
        })])


if __name__ == '__main__':
    unittest.main()
