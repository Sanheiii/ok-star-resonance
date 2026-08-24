import unittest

from src.tasks.DungeonTasks.DesolateGardenTask import DesolateGardenTask


class TestDesolateGardenTask(unittest.TestCase):

    def test_entities_with_attr_requires_a_position(self):
        entities = {
            1: {'attr_id': 884642, 'position': (1, 2)},
            2: {'attr_id': 884642, 'position': None},
            3: {'attr_id': 884640, 'position': (3, 4)},
        }

        self.assertEqual(
            DesolateGardenTask._entities_with_attr(entities, 884642),
            {1: entities[1]},
        )

    def test_nearest_entity_uses_xz_for_three_dimensional_positions(self):
        entities = {
            10: {'position': (-32.120, 100, 32.790)},
            20: {'position': (-17.980, 100, 46.930)},
        }

        entity_uuid, _ = DesolateGardenTask._nearest_entity_to(
            (-18.0, 0, 45.0),
            entities,
        )

        self.assertEqual(entity_uuid, 20)

    def test_position_beyond_extends_path_five_meters(self):
        position = DesolateGardenTask._position_beyond(
            (0, 0),
            (3, 4),
            5,
        )

        self.assertEqual(position, (6, 8))

    def test_boss_exists_uses_attr_4711(self):
        self.assertTrue(DesolateGardenTask._boss_exists({
            1: {'attr_id': 4711},
        }))
        self.assertFalse(DesolateGardenTask._boss_exists({
            1: {'attr_id': 884642},
        }))

    def test_disabling_boss_auto_battle_does_not_toggle_twice(self):
        class Task:
            _boss_auto_battle_enabled = True

            def __init__(self):
                self.sent_keys = []

            @staticmethod
            def get_custom_key(_action):
                return 'auto'

            def send_key(self, key):
                self.sent_keys.append(key)

        task = Task()
        DesolateGardenTask._set_boss_auto_battle(task, False)
        DesolateGardenTask._set_boss_auto_battle(task, False)

        self.assertEqual(task.sent_keys, ['auto'])

    def test_enabling_boss_auto_battle_sends_key_on_first_call(self):
        class Task:
            def __init__(self):
                self.sent_keys = []

            @staticmethod
            def get_custom_key(_action):
                return 'auto'

            def send_key(self, key):
                self.sent_keys.append(key)

        task = Task()
        DesolateGardenTask._set_boss_auto_battle(task, True)
        DesolateGardenTask._set_boss_auto_battle(task, True)

        self.assertEqual(task.sent_keys, ['auto'])

if __name__ == '__main__':
    unittest.main()
