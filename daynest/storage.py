"""业务数据持久化：使用 Python 自带的 SQLite，不依赖界面。"""

import calendar
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path


class Storage:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.pre_upgrade_backup = None
        existing_tasks = self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tasks'").fetchone()
        if existing_tasks:
            columns = {row[1] for row in self.db.execute('PRAGMA table_info(tasks)')}
            if not {'series_id', 'snooze_until', 'skipped'}.issubset(columns):
                # 先备份旧数据库，再为重复事项和稍后提醒增加字段。
                backup = self.path.with_name('daynest-before-v6-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
                self.backup_to(backup)
                self.pre_upgrade_backup = backup
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                due_date TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS notes (note_date TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS task_series (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, anchor_date TEXT NOT NULL,
                reminder_time TEXT NOT NULL DEFAULT '', details TEXT NOT NULL DEFAULT '',
                repeat_rule TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
            );
        """)
        self.db.commit()
        self._migrate_tasks()

    def _migrate_tasks(self):
        # 老版本数据库及备份只新增字段，不改动已有事项。
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(tasks)')}
        with self.db:
            self.db.execute("""CREATE TABLE IF NOT EXISTS task_series (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, anchor_date TEXT NOT NULL,
                reminder_time TEXT NOT NULL DEFAULT '', details TEXT NOT NULL DEFAULT '',
                repeat_rule TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1)""")
            for name, definition in (('reminder_time', "TEXT NOT NULL DEFAULT ''"),
                                     ('details', "TEXT NOT NULL DEFAULT ''"),
                                     ('reminded', 'INTEGER NOT NULL DEFAULT 0'),
                                     ('series_id', 'INTEGER'),
                                     ('occurrence_date', "TEXT NOT NULL DEFAULT ''"),
                                     ('modified', 'INTEGER NOT NULL DEFAULT 0'),
                                     ('skipped', 'INTEGER NOT NULL DEFAULT 0'),
                                     ('snooze_until', "TEXT NOT NULL DEFAULT ''")):
                if name not in columns:
                    self.db.execute(f'ALTER TABLE tasks ADD COLUMN {name} {definition}')
            self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS task_occurrence ON tasks(series_id, occurrence_date) WHERE series_id IS NOT NULL")

    def add_task(self, title, due_date, reminder_time='', details='', repeat_rule='none'):
        title = title.strip()
        if not title:
            raise ValueError("待办内容不能为空")
        date.fromisoformat(due_date)
        if repeat_rule not in ('none', 'daily', 'weekly', 'monthly'):
            raise ValueError('不支持的重复规则')
        with self.db:
            series_id = None
            if repeat_rule != 'none':
                series_id = self.db.execute('INSERT INTO task_series (title, anchor_date, reminder_time, details, repeat_rule) VALUES (?, ?, ?, ?, ?)',
                                            (title, due_date, reminder_time, details, repeat_rule)).lastrowid
            cursor = self.db.execute("INSERT INTO tasks (title, due_date, reminder_time, details, series_id, occurrence_date) VALUES (?, ?, ?, ?, ?, ?)",
                                     (title, due_date, reminder_time, details, series_id, due_date if series_id else ''))
        return cursor.lastrowid

    def update_task(self, task_id, title, due_date, reminder_time='', details='', repeat_rule=None, scope='one'):
        title = title.strip()
        if not title:
            raise ValueError('待办内容不能为空')
        date.fromisoformat(due_date)
        row = self.db.execute('SELECT series_id, occurrence_date, reminder_time, due_date FROM tasks WHERE id=? AND skipped=0', (task_id,)).fetchone()
        if not row:
            raise ValueError('待办不存在')
        series_id, occurrence, old_time, old_date = row
        repeat_rule = repeat_rule if repeat_rule is not None else self.task_repeat(task_id)
        if repeat_rule not in ('none', 'daily', 'weekly', 'monthly') or scope not in ('one', 'future'):
            raise ValueError('重复规则或修改范围无效')
        if series_id and scope == 'one' and repeat_rule != self.task_repeat(task_id):
            raise ValueError('修改单次事项时不能更改重复规则，请选择“本次及以后”')
        if series_id and scope == 'future' and repeat_rule != 'none':
            conflict = self.db.execute("SELECT 1 FROM tasks WHERE series_id=? AND occurrence_date=? AND id!=? AND (completed=1 OR modified=1 OR skipped=1 OR reminded=1 OR snooze_until!='')",
                                       (series_id, due_date, task_id)).fetchone()
            if conflict:
                raise ValueError('该日期已有单独处理过的重复事项，请选择其他日期')
        with self.db:
            if series_id and scope == 'future':
                # 已完成或单独修改过的事项保留；只重建未修改的未来实例。
                self.db.execute('UPDATE task_series SET title=?, anchor_date=?, reminder_time=?, details=?, repeat_rule=?, active=? WHERE id=?',
                                (title, due_date, reminder_time, details, repeat_rule, int(repeat_rule != 'none'), series_id))
                self.db.execute("DELETE FROM tasks WHERE series_id=? AND occurrence_date>=? AND id!=? AND completed=0 AND modified=0 AND skipped=0 AND reminded=0 AND snooze_until=''",
                                (series_id, occurrence, task_id))
                if repeat_rule != 'none':
                    # 当前实例保留原 ID 和完成状态，未来按新日期生成。
                    self.db.execute('UPDATE tasks SET occurrence_date=? WHERE id=?', (due_date, task_id))
                else:
                    self.db.execute('UPDATE tasks SET series_id=NULL, occurrence_date=? WHERE id=?', ('', task_id))
            elif not series_id and repeat_rule != 'none':
                series_id = self.db.execute('INSERT INTO task_series (title, anchor_date, reminder_time, details, repeat_rule) VALUES (?, ?, ?, ?, ?)',
                                            (title, due_date, reminder_time, details, repeat_rule)).lastrowid
                self.db.execute('UPDATE tasks SET series_id=?, occurrence_date=? WHERE id=?', (series_id, due_date, task_id))
            reset = old_time != reminder_time or old_date != due_date
            self.db.execute('UPDATE tasks SET title=?, due_date=?, reminder_time=?, details=?, modified=?, reminded=CASE WHEN ? THEN 0 ELSE reminded END, snooze_until=CASE WHEN ? THEN ? ELSE snooze_until END WHERE id=?',
                            (title, due_date, reminder_time, details, int(bool(series_id) and scope == 'one'), int(reset), int(reset), '', task_id))

    def task_repeat(self, task_id):
        row = self.db.execute('SELECT s.repeat_rule FROM tasks t JOIN task_series s ON s.id=t.series_id WHERE t.id=? AND s.active=1', (task_id,)).fetchone()
        return row[0] if row else 'none'

    def _ensure_occurrences(self, first, last):
        start, end = date.fromisoformat(first), date.fromisoformat(last)
        if end < start:
            return
        series = self.db.execute('SELECT id, title, anchor_date, reminder_time, details, repeat_rule FROM task_series WHERE active=1 AND anchor_date<=?', (last,)).fetchall()
        with self.db:
            for series_id, title, anchor_text, reminder, details, rule in series:
                anchor = date.fromisoformat(anchor_text)
                earliest = max(start, anchor)
                if rule in ('daily', 'weekly'):
                    step = 1 if rule == 'daily' else 7
                    diff = (earliest - anchor).days
                    current = anchor + timedelta(days=((diff + step - 1) // step) * step)
                    occurrences = []
                    while current <= end:
                        occurrences.append(current)
                        current += timedelta(days=step)
                elif rule == 'monthly':
                    offset = max(0, (earliest.year - anchor.year) * 12 + earliest.month - anchor.month)
                    occurrences = []
                    while True:
                        absolute = anchor.year * 12 + anchor.month - 1 + offset
                        year, month0 = divmod(absolute, 12)
                        if year > 9999:
                            break
                        month = month0 + 1
                        current = date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))
                        if current > end:
                            break
                        if current >= earliest:
                            occurrences.append(current)
                        offset += 1
                else:
                    continue
                self.db.executemany('INSERT OR IGNORE INTO tasks (title,due_date,reminder_time,details,series_id,occurrence_date) VALUES (?,?,?,?,?,?)',
                                    [(title, day.isoformat(), reminder, details, series_id, day.isoformat()) for day in occurrences])

    def task(self, task_id):
        return self.db.execute('SELECT id, title, due_date, completed, reminder_time, details FROM tasks WHERE id=? AND skipped=0', (task_id,)).fetchone()

    def all_tasks(self):
        today = date.today()
        self._ensure_occurrences((today - timedelta(days=30)).isoformat(), (today + timedelta(days=60)).isoformat())
        return self.db.execute('SELECT id, title, due_date, completed, reminder_time, details FROM tasks WHERE skipped=0 ORDER BY completed, due_date, reminder_time, id DESC').fetchall()

    def tasks_between(self, first, last):
        self._ensure_occurrences(first, last)
        return self.db.execute('SELECT id, title, due_date, completed FROM tasks WHERE skipped=0 AND due_date BETWEEN ? AND ? ORDER BY due_date, completed, id DESC', (first, last)).fetchall()

    def due_reminders(self, now):
        self._ensure_occurrences((now.date() - timedelta(days=30)).isoformat(), now.date().isoformat())
        return self.db.execute("SELECT id, title, due_date, reminder_time FROM tasks WHERE skipped=0 AND completed=0 AND reminded=0 AND reminder_time != '' AND (CASE WHEN snooze_until != '' THEN snooze_until ELSE due_date || 'T' || reminder_time || ':00' END) <= ? ORDER BY due_date, reminder_time", (now.strftime('%Y-%m-%dT%H:%M:%S'),)).fetchall()

    def snooze_task(self, task_id, until):
        with self.db:
            self.db.execute('UPDATE tasks SET snooze_until=?, reminded=0, modified=CASE WHEN series_id IS NOT NULL THEN 1 ELSE modified END WHERE id=? AND completed=0 AND skipped=0', (until.strftime('%Y-%m-%dT%H:%M:%S'), task_id))

    def mark_reminded(self, task_id):
        with self.db:
            self.db.execute('UPDATE tasks SET reminded=1 WHERE id=?', (task_id,))

    def tasks_for(self, due_date):
        self._ensure_occurrences(due_date, due_date)
        return self.db.execute(
            "SELECT id, title, completed FROM tasks WHERE skipped=0 AND due_date = ? ORDER BY completed, id DESC", (due_date,)
        ).fetchall()

    def complete_task(self, task_id, completed):
        with self.db:
            self.db.execute("UPDATE tasks SET completed = ? WHERE id = ?", (int(completed), task_id))

    def delete_task(self, task_id):
        with self.db:
            row = self.db.execute('SELECT series_id FROM tasks WHERE id=?', (task_id,)).fetchone()
            if row and row[0]:
                self.db.execute('UPDATE tasks SET skipped=1, modified=1 WHERE id=?', (task_id,))
            else:
                self.db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def get_note(self, date):
        row = self.db.execute("SELECT body FROM notes WHERE note_date = ?", (date,)).fetchone()
        return row[0] if row else ""

    def save_note(self, date, body):
        with self.db:
            self.db.execute("INSERT INTO notes (note_date, body) VALUES (?, ?) ON CONFLICT(note_date) DO UPDATE SET body = excluded.body", (date, body))

    def get_setting(self, key, default=""):
        row = self.db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        with self.db:
            self.db.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))

    def backup_to(self, path):
        target = Path(path).absolute()
        if target == self.path.absolute():
            raise ValueError("备份路径不能是当前数据库")
        # 独占创建，防止覆盖现有备份或其他文件。
        with target.open('xb'):
            pass
        backup = sqlite3.connect(target)
        try:
            self.db.backup(backup)
        finally:
            backup.close()

    def restore_from(self, path):
        source_path = Path(path).absolute()
        if source_path == self.path.absolute():
            raise ValueError("不能从当前数据库恢复")
        source = sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)
        try:
            if source.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                raise ValueError("备份数据库完整性检查失败")
            tables = {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'tasks', 'notes', 'settings'}.issubset(tables):
                raise ValueError("该文件不是兼容的 DayNest 备份")
            expected = {'tasks': {'id', 'title', 'due_date', 'completed', 'created_at'},
                        'notes': {'note_date', 'body'}, 'settings': {'key', 'value'}}
            for table, columns in expected.items():
                actual = {row[1] for row in source.execute(f'PRAGMA table_info({table})')}
                if not columns.issubset(actual):
                    raise ValueError(f"备份数据表 {table} 不兼容")
            backup_path = self.path.with_name('daynest-before-restore-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
            self.backup_to(backup_path)
            # SQLite backup 在数据库层复制，避免直接替换已打开的文件。
            source.backup(self.db)
            self._migrate_tasks()
            return backup_path
        finally:
            source.close()

    def close(self):
        self.db.close()
