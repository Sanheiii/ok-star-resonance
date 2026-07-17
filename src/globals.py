from PySide6.QtCore import QObject
from ok import og
from src.packet_capture.state import PacketCaptureData


class Globals(QObject):

    def __init__(self, exit_event):
        super().__init__()
        og.packet_capture_data = PacketCaptureData()
        og.packet_capture_tool = None

if __name__ == "__main__":
    glbs = Globals(exit_event=None)
