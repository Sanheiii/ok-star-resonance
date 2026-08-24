import ctypes
import threading
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable


WH_KEYBOARD_LL = 13
WM_QUIT = 0x0012
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
LLKHF_INJECTED = 0x10
LLKHF_UP = 0x80
INPUT_MARKER = 0x5352524F


@dataclass(frozen=True)
class KeyboardEvent:
    vk_code: int
    scan_code: int
    flags: int
    time: int
    extra_info: int

    @property
    def injected(self):
        return bool(self.flags & LLKHF_INJECTED)

    @property
    def project_injected(self):
        return self.injected and self.extra_info == INPUT_MARKER

    @property
    def action(self):
        return "up" if self.flags & LLKHF_UP else "down"


def is_physical_keyboard_event(flags):
    """Return whether low-level hook flags describe non-injected input."""
    return not bool(flags & LLKHF_INJECTED)


class _KeyboardHookData(ctypes.Structure):
    _fields_ = (
        ("vk_code", wintypes.DWORD),
        ("scan_code", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("extra_info", ctypes.c_size_t),
    )


_HOOK_CALLBACK = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)


class PhysicalKeyboardMonitor:
    """Observe physical keyboard events with a Windows low-level hook."""

    START_TIMEOUT = 2.0
    STOP_TIMEOUT = 2.0

    def __init__(self, callback: Callable[[KeyboardEvent], None]):
        self._event_callback = callback
        self._lock = threading.RLock()
        self._ready = threading.Event()
        self._thread = None
        self._thread_id = None
        self._hook_callback = None
        self._running = False
        self.error = None

        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._declare_win32_types()

    @property
    def running(self):
        with self._lock:
            return self._running

    def start(self):
        with self._lock:
            if self._running:
                return True
            if self._thread is not None and self._thread.is_alive():
                thread = self._thread
            else:
                self.error = None
                self._ready.clear()
                thread = threading.Thread(
                    target=self._hook_loop,
                    name="PhysicalKeyboardMonitor",
                    daemon=True,
                )
                self._thread = thread
                thread.start()

        if not self._ready.wait(self.START_TIMEOUT):
            self.error = RuntimeError("keyboard hook startup timed out")
            return False
        return self.running

    def stop(self):
        with self._lock:
            thread = self._thread
            thread_id = self._thread_id
        if thread is None:
            return
        if thread.is_alive() and thread_id is not None:
            self._user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
            if thread is not threading.current_thread():
                thread.join(self.STOP_TIMEOUT)
        with self._lock:
            if not thread.is_alive():
                self._thread = None
                self._thread_id = None
                self._hook_callback = None
                self._running = False

    def _declare_win32_types(self):
        self._user32.SetWindowsHookExW.argtypes = (
            ctypes.c_int,
            _HOOK_CALLBACK,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        self._user32.SetWindowsHookExW.restype = ctypes.c_void_p
        self._user32.CallNextHookEx.argtypes = (
            ctypes.c_void_p,
            ctypes.c_int,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )
        self._user32.CallNextHookEx.restype = ctypes.c_ssize_t
        self._user32.UnhookWindowsHookEx.argtypes = (ctypes.c_void_p,)
        self._user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        self._user32.PostThreadMessageW.argtypes = (
            wintypes.DWORD,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )
        self._user32.PostThreadMessageW.restype = wintypes.BOOL
        self._user32.GetMessageW.argtypes = (
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        )
        self._user32.GetMessageW.restype = wintypes.BOOL
        self._user32.TranslateMessage.argtypes = (ctypes.POINTER(wintypes.MSG),)
        self._user32.TranslateMessage.restype = wintypes.BOOL
        self._user32.DispatchMessageW.argtypes = (ctypes.POINTER(wintypes.MSG),)
        self._user32.DispatchMessageW.restype = ctypes.c_ssize_t
        self._kernel32.GetCurrentThreadId.argtypes = ()
        self._kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        self._kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
        self._kernel32.GetModuleHandleW.restype = ctypes.c_void_p

    def _hook_loop(self):
        thread_id = self._kernel32.GetCurrentThreadId()
        with self._lock:
            self._thread_id = thread_id

        @_HOOK_CALLBACK
        def hook_callback(code, message, data_address):
            try:
                if code >= 0 and message in (
                    WM_KEYDOWN,
                    WM_KEYUP,
                    WM_SYSKEYDOWN,
                    WM_SYSKEYUP,
                ):
                    data = ctypes.cast(
                        data_address, ctypes.POINTER(_KeyboardHookData)
                    ).contents
                    if is_physical_keyboard_event(data.flags):
                        self._event_callback(
                            KeyboardEvent(
                                vk_code=int(data.vk_code),
                                scan_code=int(data.scan_code),
                                flags=int(data.flags),
                                time=int(data.time),
                                extra_info=int(data.extra_info),
                            )
                        )
            except Exception:
                # Exceptions must never escape a ctypes callback. The hook is
                # observational, so always forward the event.
                pass
            return self._user32.CallNextHookEx(
                None, code, message, data_address
            )

        self._hook_callback = hook_callback
        ctypes.set_last_error(0)
        hook = self._user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            hook_callback,
            self._kernel32.GetModuleHandleW(None),
            0,
        )
        if not hook:
            self.error = ctypes.WinError(ctypes.get_last_error())
            self._ready.set()
            return

        with self._lock:
            self._running = True
        self._ready.set()
        message = wintypes.MSG()
        try:
            while self._user32.GetMessageW(
                ctypes.byref(message), None, 0, 0
            ) > 0:
                self._user32.TranslateMessage(ctypes.byref(message))
                self._user32.DispatchMessageW(ctypes.byref(message))
        finally:
            self._user32.UnhookWindowsHookEx(hook)
            with self._lock:
                self._running = False

