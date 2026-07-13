from ok import BaseTask
from src.tasks.SRTaskBase import SRTaskBase


class SRTask(SRTaskBase, BaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
