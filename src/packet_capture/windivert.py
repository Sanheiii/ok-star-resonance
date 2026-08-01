"""WinDivert packet capture backend using pydivert."""

from __future__ import annotations

import importlib


def _load_pydivert():
    try:
        return importlib.import_module("pydivert")
    except ImportError as exc:
        raise RuntimeError("未找到 pydivert，请先安装 WinDivert 抓包依赖") from exc


class WinDivertCapture:
    """Observe TCP packets as raw IPv4 datagrams without intercepting them."""

    FILTER = "ip and tcp and tcp.SrcPort > 1000 and tcp.DstPort > 1000"
    datalink = 12  # DLT_RAW

    def __init__(self):
        pydivert = _load_pydivert()
        self.handle = pydivert.WinDivert(self.FILTER, flags=pydivert.Flag.SNIFF)
        try:
            self.handle.open()
        except Exception:
            self.handle = None
            raise

    def run(self, on_packet):
        while self.handle is not None:
            try:
                packet = self.handle.recv()
            except OSError:
                if self.handle is None:
                    break
                raise
            # pydivert may expose a writable memoryview.  The parser uses IP
            # address slices as TCP stream dictionary keys, so normalize the
            # packet to immutable bytes at the backend boundary.
            on_packet(bytes(packet.raw))

    def stop(self):
        self.close()

    def close(self):
        handle, self.handle = self.handle, None
        if handle is not None:
            handle.close()
