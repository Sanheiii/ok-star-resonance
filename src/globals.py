from PySide6.QtCore import QObject
from ok import og
from src.packet_capture.state import PacketCaptureData


class Globals(QObject):

    def __init__(self, exit_event):
        super().__init__()
        og.packet_capture_data = PacketCaptureData()
        og.packet_capture_tool = None

    @staticmethod
    def on_show_main_window(main_window):
        from src.environment.card import PythonEnvironmentCard

        main_window.python_environment_card = PythonEnvironmentCard(main_window.start_tab)
        main_window.start_tab.add_widget(main_window.python_environment_card)

if __name__ == "__main__":
    glbs = Globals(exit_event=None)
