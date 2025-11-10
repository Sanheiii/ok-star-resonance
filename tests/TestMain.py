import unittest
import re

from src.config import config
from ok.test.TaskTestCase import TaskTestCase

# 导入需要测试的任务类
from src.tasks.PickPassTask import PickPassTask
from src.tasks.FishingTask import FishingTask


class TestGeneratedTasks(TaskTestCase):
    """
    为 PickPassTask 和 FishingTask 中的计算机视觉功能编写的单元测试。
    注意: 您必须提供 'tests/images/' 文件夹下的截图才能使这些测试通过。
    """

    task_class = FishingTask
    config = config

    # --- PickPassTask Tests ---

    # def test_pick_pass_close_button_ocr(self):
    #     """
    #     测试 PickPassTask: 识别月卡界面的'点击空白处关闭'。
    #     """
    #     self.set_task(PickPassTask)
    #     # 需要一张显示了月卡弹出窗口的截图
    #     self.set_image('tests/images/pass_prompt.png')
    #     # 任务中的调用: self.ocr(0.44, 0.94, 0.56, 1, match='点击空白处关闭')
    #     texts = self.task.ocr(0.44, 0.94, 0.56, 1, match='点击空白处关闭')
    #     self.assertGreater(len(texts), 0, "未能识别到'点击空白处关闭'")
    #     self.assertEqual(texts[0].name, '点击空白处关闭')

    # # --- FishingTask Tests ---

    # def test_fishing_level_ocr(self):
    #     """
    #     测试 FishingTask: 在开始钓鱼界面识别'等级'。
    #     """
    #     self.set_task(FishingTask)
    #     # 需要一张显示了初始钓鱼界面的截图
    #     self.set_image('tests/images/fishing_start.png')
    #     # 任务中的调用: self.ocr(0.56, 0.91, 0.60, 0.96, match='等级')
    #     texts = self.task.ocr(0.56, 0.91, 0.60, 0.96, match='等级')
    #     self.assertGreater(len(texts), 0, "未能识别到'等级'")
    #     self.assertEqual(texts[0].name, '等级')

    # def test_fishing_add_rod_ocr(self):
    #     """
    #     测试 FishingTask: 在鱼竿损坏时识别'添加鱼竿'。
    #     """
    #     self.set_task(FishingTask)
    #     # 需要一张显示了鱼竿损坏后界面的截图
    #     self.set_image('tests/images/fishing_add_rod.png')
    #     # 任务中的调用: self.ocr(0.90, 0.92, 0.96, 0.96, match='添加鱼竿')
    #     texts = self.task.ocr(0.90, 0.92, 0.96, 0.96, match='添加鱼竿')
    #     self.assertGreater(len(texts), 0, "未能识别到'添加鱼竿'")
    #     self.assertEqual(texts[0].name, '添加鱼竿')

    # def test_fishing_use_rod_ocr(self):
    #     """
    #     测试 FishingTask: 在更换鱼竿菜单识别'使用'。
    #     """
    #     self.set_task(FishingTask)
    #     # 需要一张显示了更换鱼竿选择界面的截图
    #     self.set_image('tests/images/fishing_rod_selection.png')
    #     # 任务中的调用: self.ocr(box=None, match="使用", log=False, threshold=0.8)
    #     texts = self.task.ocr(box=None, match="使用", threshold=0.8)
    #     self.assertGreater(len(texts), 0, "未能识别到'使用'")
    #     self.assertEqual(texts[0].name, '使用')

    # def test_fishing_hook_feature(self):
    #     """
    #     测试 FishingTask: 识别鱼上钩的提示图标。
    #     """
    #     self.set_task(FishingTask)
    #     # 需要一张显示了鱼上钩瞬间的截图
    #     self.set_image('tests/images/fishing_hook_prompt.png')
    #     # 任务中的调用: self.find_one("hint_fishing_click", threshold=0.5)
    #     feature = self.task.find_one("hint_fishing_click", threshold=0.5)
    #     self.assertIsNotNone(feature, "未能识别到鱼上钩的提示图标 'hint_fishing_click'")

    # def test_fishing_continue_ocr(self):
    #     """
    #     测试 FishingTask: 成功钓到鱼后识别'继续钓鱼'。
    #     """
    #     self.set_task(FishingTask)
    #     # 需要一张显示了成功钓到鱼后界面的截图
    #     self.set_image('tests/images/fishing_success.png')
    #     # 任务中的调用: self.ocr(0.79, 0.88, 0.87, 0.93, match='继续钓鱼')
    #     texts = self.task.ocr(0.79, 0.88, 0.87, 0.93, match='继续钓鱼')
    #     self.assertGreater(len(texts), 0, "未能识别到'继续钓鱼'")
    #     self.assertEqual(texts[0].name, '继续钓鱼')

    # def test_fishing_tension_bar_ocr(self):
    #     """
    #     测试 FishingTask: 在收线小游戏中识别'鱼线张力'。
    #     """
    #     self.set_task(FishingTask)
    #     # 需要一张显示了收线小游戏界面的截图
    #     self.set_image('tests/images/fishing_minigame.png')
    #     # 任务中的调用: self.ocr(0.54, 0.77, 0.62, 0.81, match='鱼线张力')
    #     texts = self.task.ocr(0.54, 0.77, 0.62, 0.81, match='鱼线张力')
    #     self.assertGreater(len(texts), 0, "未能识别到'鱼线张力'")
    #     self.assertEqual(texts[0].name, '鱼线张力')

    def test_ocr(self):
        self.set_image('tests/images/test.png')
        res = self.task.ocr()
        pass



if __name__ == '__main__':
    unittest.main()