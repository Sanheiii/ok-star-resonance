import unittest

from src.tasks.DungeonTasks.Dungeon1722Task import Dungeon1722Task


class Dungeon1722TaskTest(unittest.TestCase):
    def test_wait_for_entity_position_filters_type_and_uses_ten_seconds(self):
        class Task:
            ENTITY_WAIT_TIMEOUT = 10
            nearby_entities = {
                1: {'attr_id': 5023, 'entity_type': 1, 'position': (1, 2, 3)},
                2: {'attr_id': 5023, 'entity_type': 3, 'position': (4, 5, 6)},
            }

            def wait_until(self, condition, time_out):
                self.time_out = time_out
                return condition()

        task = Task()

        self.assertEqual(
            Dungeon1722Task._wait_for_entity_position(task, 5023, 3),
            (4, 5, 6),
        )
        self.assertEqual(task.time_out, 10)

    def test_wait_for_entity_position_returns_none_after_timeout(self):
        class Task:
            ENTITY_WAIT_TIMEOUT = 10
            nearby_entities = {}

            @staticmethod
            def wait_until(_condition, time_out):
                assert time_out == 10
                return False

        self.assertIsNone(
            Dungeon1722Task._wait_for_entity_position(Task(), 1955, 1)
        )


if __name__ == '__main__':
    unittest.main()
