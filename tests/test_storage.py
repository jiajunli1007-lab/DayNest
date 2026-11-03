import tempfile
import unittest
from pathlib import Path
from daynest.storage import Storage


class StorageTest(unittest.TestCase):
    def test_tasks_persist_and_are_isolated_by_date(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / 'daynest.sqlite3'
            storage = Storage(path)
            first = storage.add_task('  提交作业  ', '2026-10-30')
            second = storage.add_task('下周事项', '2026-11-01')
            storage.complete_task(first, True)
            storage.close()
            reopened = Storage(path)
            self.assertEqual(reopened.tasks_for('2026-10-30'), [(first, '提交作业', 1)])
            self.assertEqual(reopened.tasks_for('2026-11-01'), [(second, '下周事项', 0)])
            reopened.delete_task(first)
            self.assertEqual(reopened.tasks_for('2026-10-30'), [])
            with self.assertRaises(ValueError):
                reopened.add_task('  ', '2026-10-30')
            reopened.close()

    def test_notes_settings_backup_and_restore(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            store = Storage(root / 'daynest.sqlite3')
            store.add_task('原始', '2026-10-30')
            store.save_note('2026-10-30', '早安')
            store.set_setting('opacity', 60)
            backup = root / 'backup.sqlite3'
            store.backup_to(backup)
            with self.assertRaises(FileExistsError):
                store.backup_to(backup)
            store.save_note('2026-10-30', '修改后')
            safety = store.restore_from(backup)
            self.assertTrue(safety.exists())
            self.assertEqual(store.get_note('2026-10-30'), '早安')
            self.assertEqual(store.get_setting('opacity'), '60')
            self.assertEqual(len(store.tasks_for('2026-10-30')), 1)
            old = Storage(safety)
            self.assertEqual(old.get_note('2026-10-30'), '修改后')
            old.close()
            bad = root / 'invalid.sqlite3'
            bad.write_text('not a database', encoding='utf-8')
            with self.assertRaises(Exception):
                store.restore_from(bad)
            self.assertEqual(store.get_note('2026-10-30'), '早安')
            import sqlite3
            wrong_schema = root / 'wrong.sqlite3'
            invalid = sqlite3.connect(wrong_schema)
            invalid.executescript('CREATE TABLE tasks (id); CREATE TABLE notes (id); CREATE TABLE settings (id);')
            invalid.close()
            with self.assertRaises(ValueError):
                store.restore_from(wrong_schema)
            self.assertEqual(store.get_note('2026-10-30'), '早安')
            store.close()


if __name__ == '__main__':
    unittest.main()
