"""Detect the Npcap adapter used by the game window on Windows."""

from __future__ import annotations

import ctypes
import socket
from collections import Counter
from ctypes import wintypes

import psutil


ERROR_BUFFER_OVERFLOW = 111
NO_ERROR = 0


class _SocketAddress(ctypes.Structure):
    _fields_ = [("sockaddr", ctypes.c_void_p), ("length", ctypes.c_int)]


class _AdapterUnicastAddress(ctypes.Structure):
    pass


_AdapterUnicastAddress._fields_ = [
    ("length", wintypes.ULONG),
    ("flags", wintypes.DWORD),
    ("next", ctypes.POINTER(_AdapterUnicastAddress)),
    ("address", _SocketAddress),
]


class _AdapterAddresses(ctypes.Structure):
    pass


_AdapterAddresses._fields_ = [
    ("length", wintypes.ULONG),
    ("if_index", wintypes.DWORD),
    ("next", ctypes.POINTER(_AdapterAddresses)),
    ("adapter_name", ctypes.c_char_p),
    ("first_unicast_address", ctypes.POINTER(_AdapterUnicastAddress)),
]


def _normalize_guid(value):
    value = value.rsplit("\\", 1)[-1].strip().upper()
    if value.startswith("NPF_"):
        value = value[4:]
    return value.strip("{}")


def _sockaddr_ip(address):
    if not address.sockaddr or address.length < 2:
        return None
    family = ctypes.cast(address.sockaddr, ctypes.POINTER(ctypes.c_ushort)).contents.value
    raw = ctypes.string_at(address.sockaddr, address.length)
    if family == socket.AF_INET and len(raw) >= 8:
        return socket.inet_ntop(socket.AF_INET, raw[4:8])
    if family == socket.AF_INET6 and len(raw) >= 24:
        return socket.inet_ntop(socket.AF_INET6, raw[8:24]).split("%", 1)[0]
    return None


def _adapter_ips_by_guid():
    get_adapters_addresses = ctypes.WinDLL("iphlpapi").GetAdaptersAddresses
    get_adapters_addresses.argtypes = [
        wintypes.ULONG,
        wintypes.ULONG,
        ctypes.c_void_p,
        ctypes.POINTER(_AdapterAddresses),
        ctypes.POINTER(wintypes.ULONG),
    ]
    get_adapters_addresses.restype = wintypes.ULONG

    size = wintypes.ULONG(15 * 1024)
    while True:
        buffer = ctypes.create_string_buffer(size.value)
        adapters = ctypes.cast(buffer, ctypes.POINTER(_AdapterAddresses))
        result = get_adapters_addresses(socket.AF_UNSPEC, 0, None, adapters, ctypes.byref(size))
        if result != ERROR_BUFFER_OVERFLOW:
            break
    if result != NO_ERROR:
        raise OSError(result, "GetAdaptersAddresses failed")

    by_guid = {}
    current = adapters
    while current:
        adapter = current.contents
        guid = _normalize_guid(adapter.adapter_name.decode("ascii", errors="replace"))
        addresses = set()
        unicast = adapter.first_unicast_address
        while unicast:
            ip = _sockaddr_ip(unicast.contents.address)
            if ip:
                addresses.add(ip.lower())
            unicast = unicast.contents.next
        by_guid[guid] = addresses
        current = adapter.next
    return by_guid


def _connection_local_ips(pid):
    connections = psutil.Process(pid).net_connections(kind="inet")
    established = Counter()
    other = Counter()
    for connection in connections:
        if not connection.laddr or not connection.raddr:
            continue
        ip = connection.laddr.ip.lower().split("%", 1)[0]
        if ip in {"0.0.0.0", "::", "127.0.0.1", "::1"}:
            continue
        target = established if connection.status == psutil.CONN_ESTABLISHED else other
        target[ip] += 1
    return established + other


def _match_device(devices, local_ips, adapter_ips):
    for ip, _count in local_ips.most_common():
        for device in devices:
            guid = _normalize_guid(device.name)
            if ip in adapter_ips.get(guid, set()):
                return device
    return None


def game_window_pid(hwnd):
    if not hwnd:
        return 0
    process_id = wintypes.DWORD()
    get_window_process_id = ctypes.WinDLL("user32").GetWindowThreadProcessId
    get_window_process_id.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    get_window_process_id.restype = wintypes.DWORD
    get_window_process_id(hwnd, ctypes.byref(process_id))
    return process_id.value


def detect_process_device(pid, devices):
    """Return the Npcap device carrying a process's active remote connections."""
    if not pid:
        return None
    local_ips = _connection_local_ips(pid)
    if not local_ips:
        return None
    return _match_device(devices, local_ips, _adapter_ips_by_guid())
