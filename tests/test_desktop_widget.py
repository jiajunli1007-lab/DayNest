import tempfile
import unittest
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QToolButton

from daynest.content import Content
from daynest.calendar_view import CalendarCell
from daynest.desktop_widget import DesktopWidget, SIZES
from daynest.storage import Storage
from daynest.window import MainWindow

app = QApplication.instance() or QApplication(['widget-test', '-platform', 'offscreen'])


class DesktopWidgetTest(unittest.TestCase):
    def test_calendar_has_room_for_task_caption_and_keeps_transparency(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            store = Storage(Path(directory) / 'data.sqlite3')
            for title in ('交作业', '看书', '复习'):
                store.add_task(title, '2026-11-02')
            editor = MainWindow(store)
            editor.content = Content(store)
            editor.body.addWidget(editor.content)
            widget = DesktopWidget(store, editor)
            widget.calendar_date = QDate(2026, 11, 2)
            widget.set_preset('calendar')
            widget.show()
            app.processEvents()
            cell = next(c for c in widget.calendar.findChildren(CalendarCell)
                        if c.number == 2 and not c.isHidden())
            self.assertEqual(len(cell.items), 3)
            self.assertGreaterEqual(cell.height(), 38)
            widget.set_opacity(0)
            app.processEvents()
            self.assertEqual(widget.grab().toImage().pixelColor(5, 250).alpha(), 0)
            widget.set_theme('dark')
            self.assertEqual(cell.theme, 'dark')
            widget.quit_app()
            store.close()

    def test_presets_and_background_only_transparency_persist(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            store = Storage(Path(directory) / 'data.sqlite3')
            editor = MainWindow(store)
            editor.content = Content(store)
            editor.body.addWidget(editor.content)
            widget = DesktopWidget(store, editor)
            self.assertFalse(widget.bottom_action.isEnabled())
            widget.show()
            app.processEvents()
            for preset, dimensions in SIZES.items():
                widget.set_preset(preset)
                self.assertEqual((widget.width(), widget.height()), dimensions)
                self.assertEqual(store.get_setting('widget_size'), preset)
            widget.set_preset('medium')
            for value, expected_alpha in ((0, 0), (35, 89), (70, 178), (100, 255)):
                widget.set_opacity(value)
                app.processEvents()
                self.assertEqual(widget.grab().toImage().pixelColor(180, 155).alpha(), expected_alpha)
                self.assertEqual(widget.windowOpacity(), 1.0)
            self.assertEqual(store.get_setting('widget_opacity'), '100')
            widget.set_theme('dark')
            self.assertEqual(store.get_setting('widget_theme'), 'dark')
            widget.quit_app()
            store.close()

    def test_drag_and_restore_position(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            store = Storage(Path(directory) / 'data.sqlite3')
            editor = MainWindow(store)
            editor.content = Content(store)
            editor.body.addWidget(editor.content)
            widget = DesktopWidget(store, editor)
            widget.move(200, 200)
            widget.show()
            app.processEvents()
            start = widget.pos()
            QTest.mousePress(widget.header, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(35, 8))
            QTest.mouseMove(widget.header, QPoint(95, 28), 10)
            QTest.mouseRelease(widget.header, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(95, 28))
            app.processEvents()
            self.assertNotEqual(widget.pos(), start)
            position = widget.pos()
            widget.quit_app()
            restored = DesktopWidget(store, editor)
            restored.restore_position()
            self.assertEqual(restored.pos(), position)
            restored.quit_app()
            store.close()

    def test_task_check_updates_database_and_editor(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            store = Storage(Path(directory) / 'data.sqlite3')
            editor = MainWindow(store)
            editor.content = Content(store)
            editor.body.addWidget(editor.content)
            widget = DesktopWidget(store, editor)
            editor.content.tasks.changed.connect(widget.refresh)
            editor.content.tasks.input.setText('从管理窗口添加')
            editor.content.tasks.add_task()
            self.assertTrue(any(label.text() == '从管理窗口添加' for label in widget.body.findChildren(QLabel)))
            task = store.add_task('小组件测试', date.today().isoformat())
            widget.refresh()
            widget.show()
            app.processEvents()
            buttons = [button for button in widget.body.findChildren(QToolButton) if button.toolTip() == '完成待办']
            self.assertTrue(buttons)
            QTest.mouseClick(buttons[0], Qt.MouseButton.LeftButton)
            rows = store.tasks_for(date.today().isoformat())
            self.assertEqual(next(row[2] for row in rows if row[0] == task), 1)
            self.assertTrue(any(editor.content.tasks.list.item(i).checkState() == Qt.CheckState.Checked
                                for i in range(editor.content.tasks.list.count())))
            widget.quit_app()
            store.close()
