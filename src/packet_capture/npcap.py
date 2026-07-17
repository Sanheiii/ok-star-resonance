"""Small ctypes wrapper around the Npcap/libpcap API."""

from __future__ import annotations

import ctypes
from ctypes import POINTER, byref, c_char_p, c_int, c_uint, c_ubyte, c_void_p
from dataclasses import dataclass

PCAP_ERRBUF_SIZE = 256


class _PcapIf(ctypes.Structure):
    pass


_PcapIf._fields_ = [
    ("next", POINTER(_PcapIf)),
    ("name", c_char_p),
    ("description", c_char_p),
    ("addresses", c_void_p),
    ("flags", c_uint),
]


class _Timeval(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_long)]


class _PcapHeader(ctypes.Structure):
    _fields_ = [("ts", _Timeval), ("caplen", c_uint), ("length", c_uint)]


class _BpfProgram(ctypes.Structure):
    _fields_ = [("bf_len", c_uint), ("bf_insns", c_void_p)]


@dataclass(frozen=True)
class NpcapDevice:
    name: str
    description: str

    @property
    def display_name(self):
        return self.description or self.name


def _library():
    try:
        lib = ctypes.WinDLL("wpcap.dll")
    except (OSError, AttributeError) as exc:
        raise RuntimeError("未找到 Npcap（wpcap.dll），请先安装 Npcap") from exc
    lib.pcap_findalldevs.argtypes = [POINTER(POINTER(_PcapIf)), c_char_p]
    lib.pcap_findalldevs.restype = c_int
    lib.pcap_freealldevs.argtypes = [POINTER(_PcapIf)]
    lib.pcap_create.argtypes = [c_char_p, c_char_p]
    lib.pcap_create.restype = c_void_p
    lib.pcap_close.argtypes = [c_void_p]
    lib.pcap_geterr.argtypes = [c_void_p]
    lib.pcap_geterr.restype = c_char_p
    return lib


def list_devices():
    lib = _library()
    devices = POINTER(_PcapIf)()
    error = ctypes.create_string_buffer(PCAP_ERRBUF_SIZE)
    if lib.pcap_findalldevs(byref(devices), error) == -1:
        raise RuntimeError(error.value.decode("utf-8", errors="replace"))
    result = []
    try:
        current = devices
        while current:
            item = current.contents
            name = item.name.decode("utf-8", errors="replace")
            description = item.description.decode("utf-8", errors="replace") if item.description else ""
            result.append(NpcapDevice(name, description))
            current = item.next
    finally:
        if devices:
            lib.pcap_freealldevs(devices)
    return result


class NpcapCapture:
    FILTER = b"tcp and not portrange 0-1000"

    def __init__(self, device_name):
        self.lib = _library()
        self.handle = None
        self._callback = None
        self._open(device_name)

    def _error(self):
        value = self.lib.pcap_geterr(self.handle)
        return value.decode("utf-8", errors="replace") if value else "unknown Npcap error"

    def _check(self, name, value):
        if value != 0:
            raise RuntimeError(f"{name} failed: {self._error()}")

    def _open(self, device_name):
        error = ctypes.create_string_buffer(PCAP_ERRBUF_SIZE)
        self.handle = self.lib.pcap_create(device_name.encode("utf-8"), error)
        if not self.handle:
            raise RuntimeError(error.value.decode("utf-8", errors="replace"))
        try:
            for name, value in (("pcap_set_snaplen", 65536), ("pcap_set_promisc", 1),
                                ("pcap_set_timeout", 250), ("pcap_set_buffer_size", 64 * 1024 * 1024)):
                function = getattr(self.lib, name)
                function.argtypes = [c_void_p, c_int]
                self._check(name, function(self.handle, value))
            immediate = getattr(self.lib, "pcap_set_immediate_mode", None)
            if immediate:
                immediate.argtypes = [c_void_p, c_int]
                self._check("pcap_set_immediate_mode", immediate(self.handle, 1))
            self.lib.pcap_activate.argtypes = [c_void_p]
            activated = self.lib.pcap_activate(self.handle)
            if activated < 0:
                raise RuntimeError(f"pcap_activate failed: {self._error()}")
            self._set_filter()
            self.lib.pcap_datalink.argtypes = [c_void_p]
            self.lib.pcap_datalink.restype = c_int
            self.datalink = self.lib.pcap_datalink(self.handle)
            self.lib.pcap_datalink.argtypes = [c_void_p]
            self.lib.pcap_datalink.restype = c_int
            self.datalink = self.lib.pcap_datalink(self.handle)
        except Exception:
            self.close()
            raise

    def _set_filter(self):
        program = _BpfProgram()
        self.lib.pcap_compile.argtypes = [c_void_p, POINTER(_BpfProgram), c_char_p, c_int, c_uint]
        self.lib.pcap_setfilter.argtypes = [c_void_p, POINTER(_BpfProgram)]
        self.lib.pcap_freecode.argtypes = [POINTER(_BpfProgram)]
        self._check("pcap_compile", self.lib.pcap_compile(self.handle, byref(program), self.FILTER, 1, 0))
        try:
            self._check("pcap_setfilter", self.lib.pcap_setfilter(self.handle, byref(program)))
        finally:
            self.lib.pcap_freecode(byref(program))

    def run(self, on_packet):
        callback_type = ctypes.WINFUNCTYPE(None, c_void_p, POINTER(_PcapHeader), POINTER(c_ubyte))

        def receive(_user, header, data):
            on_packet(ctypes.string_at(data, header.contents.caplen))

        self._callback = callback_type(receive)
        self.lib.pcap_loop.argtypes = [c_void_p, c_int, callback_type, c_void_p]
        result = self.lib.pcap_loop(self.handle, -1, self._callback, None)
        if result == -1:
            raise RuntimeError(f"pcap_loop failed: {self._error()}")

    def stop(self):
        if self.handle:
            self.lib.pcap_breakloop.argtypes = [c_void_p]
            self.lib.pcap_breakloop(self.handle)

    def close(self):
        if self.handle:
            self.lib.pcap_close(self.handle)
            self.handle = None
