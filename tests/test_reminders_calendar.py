import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QDate, QEvent, QTime
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from daynest.calendar_view import CalendarView
from daynest.content import Content
from daynest.desktop_widget import DesktopWidget
from daynest.reminders import ReminderService
from daynest.storage import Storage
from daynest.tasks import TaskDialog
from daynest.window import MainWindow

app = QApplication.instance() or QApplication(['test', '-platform', 'offscreen'])


class ReminderCalendarTest(unittest.TestCase):
    def test_old_database_and_backup_are_migrated_without_losing_data(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            root = Path(folder)
            old = root / 'old.sqlite3'
            db = sqlite3.connect(old)
            db.executescript("""CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, due_date TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE notes (note_date TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT INTO tasks (title,due_date) VALUES ('旧待办','2026-10-31');""")
            db.close()
            store = Storage(root / 'current.sqlite3')
            store.restore_from(old)
            self.assertEqual(store.tasks_for('2026-10-31')[0][1], '旧待办')
            task_id = store.add_task('新提醒', '2026-11-01', '09:30', '带备注')
            self.assertEqual(store.task(task_id)[4:], ('09:30', '带备注'))
            store.close()
            reopened = Storage(old)
            self.assertTrue(reopened.pre_upgrade_backup.is_file())
            before = sqlite3.connect(reopened.pre_upgrade_backup)
            self.assertEqual(before.execute('SELECT title FROM tasks').fetchone()[0], '旧待办')
            before.close()
            self.assertEqual(reopened.task(1)[1], '旧待办')
            self.assertEqual(reopened.task(1)[4:], ('', ''))
            reopened.close()

    def test_reminder_due_once_and_edit_rearms(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            store = Storage(Path(folder) / 'data.sqlite3')
            task = store.add_task('交作业', '2026-10-31', '09:30', '附件')
            done = store.add_task('已完成', '2026-10-31', '09:30')
            store.complete_task(done, True)
            widget = QWidget()
            widget.tray = None
            service = ReminderService(store, widget, start=False)
            service.check(datetime(2026, 10, 31, 9, 29))
            self.assertEqual(len(service.cards), 0)
            service.check(datetime(2026, 10, 31, 9, 30))
            self.assertEqual(len(service.cards), 1)
            self.assertEqual(service.cards[task].name.text(), '交作业')
            self.assertNotIn(done, service.cards)
            service.check(datetime(2026, 10, 31, 10, 0))
            self.assertEqual(len(service.cards), 1)
            store.update_task(task, '交作业', '2026-10-31', '11:00', '附件')
            service.check(datetime(2026, 10, 31, 11, 0))
            self.assertEqual(len(service.cards), 1)
            self.assertEqual(service.cards[task].original[2], '11:00')
            service.complete(service.cards[task])
            self.assertEqual(store.task(task)[3], 1)
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            store.close()

    def test_editor_calendar_and_desktop_calendar_share_tasks(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            store = Storage(Path(folder) / 'data.sqlite3')
            store.add_task('看书', '2026-10-23', '20:00')
            editor = MainWindow(store)
            editor.content = Content(store)
            editor.body.addWidget(editor.content)
            widget = DesktopWidget(store, editor)
            widget.calendar_date = QDate(2026, 10, 23)
            widget.set_preset('calendar')
            buttons = widget.calendar.findChildren(QPushButton)
            self.assertTrue(any('看书' in button.text() for button in buttons))
            selected = next(button for button in buttons if button.text() == '24' and not button.isHidden())
            selected.click()
            self.assertEqual(editor.content.tasks.selected_date(), '2026-10-24')
            widget.open_calendar_tasks()
            self.assertIs(editor.content.tabs.currentWidget(), editor.content.tasks)
            dialog = TaskDialog('2026-10-24', parent=editor)
            dialog.title_input.setText('新事项')
            dialog.remind.setChecked(True)
            dialog.time.setTime(QTime(18, 15))
            dialog.details.setPlainText('备注')
            self.assertEqual(dialog.values(), ('新事项', '2026-10-24', '18:15', '备注', 'none'))
            dialog.repeat.setCurrentIndex(dialog.repeat.findData('weekly'))
            self.assertEqual(dialog.values()[-1], 'weekly')
            self.assertTrue(dialog.findChild(QPushButton, 'saveTask'))
            widget.quit_app()
            store.close()
