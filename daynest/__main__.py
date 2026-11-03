"""用 `python -m daynest` 启动。"""

import argparse
import sys
from pathlib import Path
from PySide6.QtCore import QStandardPaths, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
from .hotkey import GlobalHotkey
from .content import Content
from .desktop_widget import DesktopWidget
from .storage import Storage
from .reminders import ReminderService
from .window import MainWindow


def main():
    parser = argparse.ArgumentParser(description="DayNest 桌面日历与待办")
    parser.add_argument("--data-dir", help="数据库目录；不指定时使用系统用户数据目录")
    parser.add_argument("--smoke-test", action="store_true", help="自动启动并退出，用于基本验证")
    args, qt_args = parser.parse_known_args()
    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName("DayNest")
    data_dir = Path(args.data_dir) if args.data_dir else Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    try:
        storage = Storage(data_dir / "daynest.sqlite3")
    except Exception as exc:
        QMessageBox.critical(None, "无法打开 DayNest 数据", str(exc))
        return 1
    editor = MainWindow(storage)
    content = Content(storage)
    editor.content = content
    editor.body.addWidget(content)
    editor.apply_style()
    editor.quit_guard = content.notes.flush
    widget = DesktopWidget(storage, editor)
    content.tasks.changed.connect(widget.refresh)
    content.tasks.date.dateChanged.connect(widget.select_calendar_date)
    content.settings_restored.connect(editor.load_settings)
    content.settings_restored.connect(widget.reload_from_storage)
    tray_available = False
    if not args.smoke_test:
        tray_available = widget.setup_tray()
    def refresh_after_reminder():
        content.tasks.refresh()
        content.tasks.changed.emit()

    reminders = ReminderService(storage, widget, on_change=refresh_after_reminder)
    app.setQuitOnLastWindowClosed(False)
    hotkey = GlobalHotkey(widget.open_editor)
    app.installNativeEventFilter(hotkey)
    if not args.smoke_test and not hotkey.register():
        widget.menu_button.setToolTip(hotkey.error)
        print(hotkey.error, file=sys.stderr)
    app.aboutToQuit.connect(hotkey.unregister)
    app.aboutToQuit.connect(content.notes.flush)
    app.aboutToQuit.connect(reminders.shutdown)
    app.aboutToQuit.connect(storage.close)
    widget.restore_position()
    mode = storage.get_setting('widget_mode', 'bottom') if tray_available else 'normal'
    widget.set_mode(mode if mode in ('normal', 'bottom', 'top') else 'normal')
    if args.smoke_test:
        QTimer.singleShot(200, widget.quit_app)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
