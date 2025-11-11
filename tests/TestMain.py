import unittest
import re

from src.config import config
from ok.test.TaskTestCase import TaskTestCase

# 导入需要测试的任务类
from src.tasks.FishingTask import FishingTask


class TestGeneratedTasks(TaskTestCase):

    task_class = FishingTask
    config = config

    def test_ocr(self):
        self.set_image('tests/images/test.png')
        res = self.task.ocr()
        pass



if __name__ == '__main__':
    unittest.main()