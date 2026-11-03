import unittest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from daynest.window import MainWindow
from daynest.storage import Storage
from daynest.tasks import TaskPane
from daynest.content import Content
from pathlib import Path
import tempfile

app = QApplication.instance() or QApplication(["daynest-test", "-platform", "offscreen"])


class WindowTest(unittest.TestCase):
    def test_window_controls(self):
        window = MainWindow()
        self.assertTrue(window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertTrue(window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        from PySide6.QtCore import QDate
        window.update_today()
        self.assertEqual(window.date_label.text(), window.today_text())
        window.opacity.setValue(40)
        self.assertEqual(window.opacity_label.text(), "40%")
        window.on_top.setChecked(True)
        self.assertTrue(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        window.on_top.setChecked(False)
        self.assertFalse(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        window.show()
        window.quit_guard = lambda: False
        window.quit_app()
        self.assertTrue(window.isVisible())
        window.quit_guard = None
        window.quit_app()

    def test_add_and_check_task_through_widgets(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            store = Storage(Path(directory) / 'data.sqlite3')
            pane = TaskPane(store)
            pane.input.setText('写报告')
            pane.add_task()
            self.assertEqual(pane.list.count(), 2)  # 分组标题和一条待办
            pane.list.item(1).setCheckState(Qt.CheckState.Checked)
            self.assertEqual(store.tasks_for(pane.selected_date())[0][2], 1)
            pane.list.setCurrentRow(1)
            pane.delete_task()
            self.assertEqual(pane.list.count(), 0)
            store.close()

    def test_calendar_updates_task_and_note_dates(self):
        from PySide6.QtCore import QDate
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            store = Storage(Path(directory) / 'data.sqlite3')
            content = Content(store)
            day = QDate(2026, 10, 30)
            content.calendar.setSelectedDate(day)
            self.assertEqual(content.tasks.selected_date(), '2026-10-30')
            content.notes.editor.setPlainText('一条便签')
            self.assertTrue(content.notes.flush())
            self.assertEqual(store.get_note('2026-10-30'), '一条便签')
            store.close()

    def test_restored_appearance_is_not_overwritten_on_close(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            store = Storage(Path(directory) / 'data.sqlite3')
            store.set_setting('opacity', 47)
            store.set_setting('editor_background_v2', '#1f3445')
            window = MainWindow(store)
            store.set_setting('opacity', 66)
            store.set_setting('editor_background_v2', '#304050')
            window.load_settings()
            self.assertEqual(window.opacity.value(), 66)
            self.assertEqual(window.color.name(), '#304050')
            window.quit_app()
            self.assertEqual(store.get_setting('opacity'), '66')
            store.close()


if __name__ == '__main__':
    unittest.main()
