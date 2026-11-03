import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QPushButton, QWidget
from daynest.storage import Storage
from daynest.reminders import ReminderService

app = QApplication.instance() or QApplication(['test', '-platform', 'offscreen'])


class RepeatingTaskTest(unittest.TestCase):
    def test_weekly_occurrences_edit_single_and_future_and_skip(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            store = Storage(Path(folder) / 'data.sqlite3')
            first = store.add_task('交作业', '2026-11-02', '20:00', '备注', 'weekly')
            weeks = store.tasks_between('2026-11-01', '2026-11-30')
            self.assertEqual([row[2] for row in weeks], ['2026-11-02', '2026-11-09', '2026-11-16', '2026-11-23', '2026-11-30'])
            self.assertEqual(len(store.tasks_between('2026-11-01', '2026-11-30')), 5)
            single = weeks[1][0]
            store.update_task(single, '提前交', '2026-11-10', '18:00', '', 'weekly', 'one')
            self.assertEqual(store.tasks_for('2026-11-10')[0][1], '提前交')
            self.assertEqual(store.tasks_for('2026-11-09'), [])
            store.delete_task(weeks[2][0])
            self.assertEqual(store.tasks_for('2026-11-16'), [])
            store.update_task(first, '周任务', '2026-11-02', '19:00', '', 'weekly', 'future')
            self.assertEqual(store.tasks_for('2026-11-10')[0][1], '提前交')
            self.assertEqual(store.tasks_for('2026-11-16'), [])
            self.assertEqual(store.tasks_for('2026-11-23')[0][1], '周任务')
            store.close()

    def test_month_end_and_completed_instances_are_independent(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            store = Storage(Path(folder) / 'data.sqlite3')
            first = store.add_task('账单', '2027-01-31', repeat_rule='monthly')
            rows = store.tasks_between('2027-01-01', '2027-04-30')
            self.assertEqual([r[2] for r in rows], ['2027-01-31', '2027-02-28', '2027-03-31', '2027-04-30'])
            store.complete_task(first, True)
            self.assertEqual(store.task(first)[3], 1)
            self.assertEqual(store.tasks_for('2027-02-28')[0][2], 0)
            store.close()

    def test_change_future_rule_preserves_completed_and_rebuilds_dates(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'data.sqlite3'
            store = Storage(path)
            first = store.add_task('周计划', '2026-11-02', repeat_rule='weekly')
            store.tasks_between('2026-11-01', '2026-12-01')
            completed = store.tasks_for('2026-11-09')[0][0]
            store.complete_task(completed, True)
            store.update_task(first, '日计划', '2026-11-03', '', '', 'daily', 'future')
            self.assertEqual(store.task(completed)[3], 1)
            self.assertEqual(store.tasks_for('2026-11-03')[0][1], '日计划')
            self.assertEqual(store.tasks_for('2026-11-04')[0][1], '日计划')
            store.close()
            store = Storage(path)
            self.assertEqual(store.task_repeat(first), 'daily')
            self.assertEqual(store.tasks_for('2026-11-05')[0][1], '日计划')
            store.close()

    def test_snooze_survives_restart_and_can_be_completed(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / 'data.sqlite3'
            store = Storage(path)
            task = store.add_task('提醒我', '2026-11-02', '09:00')
            clock = lambda: datetime(2026, 11, 2, 9, 0)
            parent = QWidget()
            service = ReminderService(store, parent, start=False, clock=clock)
            service.check()
            later = next(button for button in service.cards[task].findChildren(QPushButton) if button.text().startswith('稍后'))
            later.menu().actions()[0].trigger()
            self.assertFalse(service.cards)
            store.close()
            store = Storage(path)
            service = ReminderService(store, parent, start=False, clock=clock)
            service.check(datetime(2026, 11, 2, 9, 9, 59))
            self.assertFalse(service.cards)
            service.check(datetime(2026, 11, 2, 9, 10))
            self.assertIn(task, service.cards)
            service.complete(service.cards[task])
            self.assertEqual(store.task(task)[3], 1)
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            store.close()

    def test_exit_with_open_card_keeps_reminder_due(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            store = Storage(Path(folder) / 'data.sqlite3')
            task = store.add_task('尚未处理', '2026-11-02', '09:00')
            parent = QWidget()
            service = ReminderService(store, parent, start=False)
            service.check(datetime(2026, 11, 2, 9, 0))
            self.assertIn(task, service.cards)
            service.shutdown()
            self.assertFalse(service.cards)
            self.assertEqual(store.due_reminders(datetime(2026, 11, 2, 9, 1))[0][0], task)
            store.close()
