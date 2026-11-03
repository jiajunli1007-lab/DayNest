"""Windows 全局快捷键；无法注册时不会影响应用的普通窗口。"""

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter


class GlobalHotkey(QAbstractNativeEventFilter):
    """把 Ctrl+Alt+N 注册到 Qt 事件循环所在的 Windows 线程。"""

    # 普通应用的标识符必须位于 0x0000–0xBFFF。
    HOTKEY_ID = 0x0DAC
    WM_HOTKEY = 0x0312

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.registered = False
        self.error = ""
        self.user32 = None
        if sys.platform == "win32":
            self.user32 = ctypes.WinDLL("user32", use_last_error=True)
            self.user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            self.user32.RegisterHotKey.restype = wintypes.BOOL
            self.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            self.user32.UnregisterHotKey.restype = wintypes.BOOL

    def register(self):
        if self.user32 is None:
            self.error = "全局快捷键仅支持 Windows。"
            return False
        if self.registered:
            return True
        # MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_N
        self.registered = bool(self.user32.RegisterHotKey(None, self.HOTKEY_ID, 0x4003, 0x4E))
        if not self.registered:
            code = ctypes.get_last_error()
            reason = "快捷键已被占用" if code == 1409 else ctypes.FormatError(code).strip()
            self.error = f"Ctrl+Alt+N 注册失败（Windows 错误 {code}：{reason}）。"
        return self.registered

    def unregister(self):
        if self.registered and self.user32 is not None:
            self.user32.UnregisterHotKey(None, self.HOTKEY_ID)
            self.registered = False

    def nativeEventFilter(self, event_type, message):
        if self.registered and bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == self.WM_HOTKEY and msg.wParam == self.HOTKEY_ID:
                self.callback()
                return True, 0
        return False, 0
