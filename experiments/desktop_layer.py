"""独立桌面层实验；默认只读，只有显式 --attach 才修改测试窗口的父关系。

只选择当前 Progman 下、与图标视图同级的唯一 WorkerW；不发送未文档化
消息，不修改 Explorer 的窗口样式。不支持的布局直接退出。
"""

import argparse
import ctypes
import json
import sys
from ctypes import wintypes

from daynest.desktop_probe import inspect_desktop


def select_host(snapshot):
    shell = snapshot['shell_hwnd']
    windows = snapshot['windows']
    has_icons = any(w['class'] == 'SHELLDLL_DefView' and w['parent'] == shell for w in windows)
    candidates = [w['hwnd'] for w in windows if w['class'] == 'WorkerW' and w['parent'] == shell]
    return candidates[0] if shell and has_icons and len(candidates) == 1 else None


def attach_experiment(host, duration_ms=15000):
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication, QLabel

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    user32.SetParent.restype = wintypes.HWND
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    app = QApplication.instance() or QApplication(['DayNest-wallpaper-experiment'])
    app.setQuitOnLastWindowClosed(False)
    window = QLabel('DayNest 桌面层实验\n15 秒后自动退出')
    window.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
    window.setStyleSheet('background: #19404a; color: white; padding: 18px; font-size: 18px;')
    window.resize(300, 120)
    window.show()
    app.processEvents()
    hwnd = int(window.winId())
    old_parent = int(user32.GetParent(hwnd) or 0)
    old_style = user32.GetWindowLongPtrW(hwnd, -16)
    attached = False
    style_changed = False
    restoration_ok = True

    def restore_and_close():
        nonlocal attached, style_changed, restoration_ok
        verify_parent = attached
        # 先恢复原生窗口，再结束 Qt 事件循环；否则 Qt 可能先销毁句柄。
        if (attached or style_changed) and not user32.IsWindow(hwnd):
            print('警告：测试窗口句柄已销毁，无法检查恢复状态。', file=sys.stderr)
            restoration_ok = False
            attached = style_changed = False
        if attached:
            ctypes.set_last_error(0)
            previous_parent = user32.SetParent(hwnd, old_parent or None)
            if not previous_parent and ctypes.get_last_error():
                print('警告：未能恢复原父窗口关系。', file=sys.stderr)
                restoration_ok = False
            attached = False
        if style_changed:
            ctypes.set_last_error(0)
            restored = user32.SetWindowLongPtrW(hwnd, -16, old_style)
            if not restored and ctypes.get_last_error():
                print('警告：未能恢复测试窗口样式。', file=sys.stderr)
                restoration_ok = False
            if not user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0027):
                print('警告：未能刷新测试窗口样式。', file=sys.stderr)
                restoration_ok = False
            style_changed = False
        # WS_CHILD 恢复前，桌面窗口可暂时显示为父窗口；恢复样式后再比较。
        if verify_parent and user32.IsWindow(hwnd) and int(user32.GetParent(hwnd) or 0) != old_parent:
            print('警告：恢复后父窗口不符合原始状态。', file=sys.stderr)
            restoration_ok = False
        if restoration_ok:
            print('测试窗口恢复检查通过，正在关闭。', flush=True)
        window.close()

    def finish():
        restore_and_close()
        app.quit()

    try:
        # SetParent 不会替调用者调整 WS_CHILD 与 WS_POPUP。
        child_style = ctypes.c_int32(((old_style & 0xffffffff) | 0x40000000) & ~0x80000000).value
        ctypes.set_last_error(0)
        result = user32.SetWindowLongPtrW(hwnd, -16, child_style)
        if not result and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
        style_changed = True
        ctypes.set_last_error(0)
        previous = user32.SetParent(hwnd, host)
        parent_error = ctypes.get_last_error()
        # 上一个父窗口为 NULL 时，返回零也可能表示成功。
        if previous or parent_error == 0:
            attached = True
        if int(user32.GetParent(hwnd) or 0) != host:
            raise OSError(parent_error, '窗口未能挂接到预期宿主')
        if not user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0027):
            raise ctypes.WinError(ctypes.get_last_error())
        print('窗口父关系已改变；是否位于图标后方及能否显示，仍须人工验证。', flush=True)
        QTimer.singleShot(duration_ms, finish)
        app.exec()
    finally:
        if attached or style_changed:
            restore_and_close()
        else:
            window.close()
    return 0 if restoration_ok else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attach', action='store_true', help='对独立测试窗口执行 15 秒挂接实验')
    args = parser.parse_args()
    snapshot = inspect_desktop()
    host = select_host(snapshot)
    print(json.dumps({'candidate_hwnd': host, 'snapshot': snapshot}, ensure_ascii=False, indent=2), flush=True)
    if not host:
        print('未发现唯一兼容候选，不执行挂接。', file=sys.stderr)
        return 1
    if not args.attach:
        print('只读模式；未修改窗口关系。')
        return 0
    return attach_experiment(host)


if __name__ == '__main__':
    raise SystemExit(main())
