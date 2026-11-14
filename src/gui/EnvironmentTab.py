from ok import og
from ok.ui.qt.widget.CustomTab import CustomTab

from src.environment.card import PythonEnvironmentCard


class EnvironmentTab(CustomTab):
    icon = "pulse"

    def __init__(self):
        super().__init__()
        self.python_environment_card = PythonEnvironmentCard(self.view)
        self.add_widget(self.python_environment_card)

    @property
    def name(self):
        return og.app.tr("Environment Check")
