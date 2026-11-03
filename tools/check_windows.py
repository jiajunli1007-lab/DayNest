"""显式运行的 Windows 原生窗口与热键诊断，不操作 Explorer。"""

import ctypes
import json
import sys
from ctypes import wintypes
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from daynest.hotkey import GlobalHotkey
from daynest.window import MainWindow


def main():
    if sys.platform != 'win32':
        raise SystemExit('此诊断仅支持 Windows')
    app = QApplication(['DayNest-native-check', '-platform', 'windows'])
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    window = MainWindow()
    window.show()
    app.processEvents()
    hwnd = int(window.winId())
    visible = bool(user32.IsWindowVisible(hwnd))
    initial_top = bool(user32.GetWindowLongW(hwnd, -20) & 0x8)
    window.on_top.setChecked(True)
    app.processEvents()
    enabled = bool(user32.GetWindowLongW(int(window.winId()), -20) & 0x8)
    window.on_top.setChecked(False)
    app.processEvents()
    disabled = not bool(user32.GetWindowLongW(int(window.winId()), -20) & 0x8)
    hotkey = GlobalHotkey(lambda: None)
    registered = hotkey.register()
    error = hotkey.error
    hotkey.unregister()
    print(json.dumps({'qt_platform': app.platformName(), 'native_visible': visible,
                      'normal_has_topmost': initial_top, 'topmost_flag_set': enabled,
                      'topmost_flag_removed': disabled,
                      'tray_available': QSystemTrayIcon.isSystemTrayAvailable(),
                      'hotkey_registered': registered, 'hotkey_error': error}, ensure_ascii=False, indent=2))
    window.quit_app()
    return 0 if visible and not initial_top and enabled and disabled else 1


if __name__ == '__main__':
    raise SystemExit(main())
