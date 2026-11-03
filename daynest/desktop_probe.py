"""只读诊断 Explorer 桌面宿主；不会挂接窗口或向 Explorer 发送消息。"""

import ctypes
import json
import sys
from ctypes import wintypes


def inspect_desktop():
    if sys.platform != 'win32':
        raise RuntimeError('此诊断仅支持 Windows')
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    user32.EnumChildWindows.restype = wintypes.BOOL
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.GetShellWindow.restype = wintypes.HWND
    found = {}

    def collect(hwnd, _):
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, name, len(name))
        if name.value in {'Progman', 'WorkerW', 'SHELLDLL_DefView'}:
            found[int(hwnd)] = {'class': name.value, 'hwnd': int(hwnd), 'parent': int(user32.GetParent(hwnd) or 0)}
        return True

    child = callback_type(collect)

    def scan_top(hwnd, unused):
        collect(hwnd, unused)
        user32.EnumChildWindows(hwnd, child, 0)
        return True

    top = callback_type(scan_top)
    if not user32.EnumWindows(top, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return {'shell_hwnd': int(user32.GetShellWindow() or 0), 'windows': list(found.values())}


if __name__ == '__main__':
    print(json.dumps(inspect_desktop(), ensure_ascii=False, indent=2))
