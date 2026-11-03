"""日历、待办、便签和备份操作的界面组合。"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QMenu,
    QPushButton, QTabWidget, QToolButton, QVBoxLayout, QWidget)
from .calendar_view import CalendarView
from .notes import NotePane
from .tasks import TaskPane


class Content(QWidget):
    settings_restored = Signal()
    def __init__(self, storage):
        super().__init__()
        self.storage = storage
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tasks = TaskPane(storage)
        self.calendar = CalendarView(storage)
        self.notes = NotePane(storage, self.tasks.selected_date())
        self.tabs.addTab(self.tasks, "待办")
        calendar_page = QWidget()
        calendar_layout = QVBoxLayout(calendar_page)
        calendar_layout.setContentsMargins(0, 5, 0, 0)
        calendar_layout.addWidget(self.calendar, 1)
        show_day = QPushButton('查看选中日期的待办  ›')
        show_day.clicked.connect(self.show_selected_tasks)
        calendar_layout.addWidget(show_day)
        self.tabs.addTab(calendar_page, "月历")
        self.tabs.addTab(self.notes, "便签")
        layout.addWidget(self.tabs, 1)
        self.calendar.selectionChanged.connect(self.calendar_changed)
        self.calendar.addRequested.connect(self.tasks.new_dialog)
        self.tasks.date.dateChanged.connect(self.date_changed)
        self.tasks.changed.connect(self.calendar.refresh)
        actions = QToolButton()
        actions.setText('备份与恢复  ⋯')
        actions.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(actions)
        menu.addAction('备份数据', self.backup)
        menu.addAction('恢复数据', self.restore)
        actions.setMenu(menu)
        self.tabs.setCornerWidget(actions)

    def calendar_changed(self):
        self.tasks.date.setDate(self.calendar.selectedDate())

    def show_selected_tasks(self):
        self.tasks.date_only.setChecked(True)
        self.tabs.setCurrentWidget(self.tasks)

    def date_changed(self, date):
        self.calendar.setSelectedDate(date)
        self.notes.load(date.toString("yyyy-MM-dd"))

    def backup(self):
        if not self.notes.flush():
            return
        name, _ = QFileDialog.getSaveFileName(self, "备份数据：请选择新的文件", "DayNest-backup.sqlite3", "SQLite 数据库 (*.sqlite3)")
        if not name:
            return
        try:
            self.storage.backup_to(name)
        except Exception as exc:
            QMessageBox.critical(self, "备份失败", f"{exc}\n请使用不存在的文件名。")
        else:
            QMessageBox.information(self, "备份完成", "数据已备份。")

    def restore(self):
        if not self.notes.flush():
            return
        name, _ = QFileDialog.getOpenFileName(self, "选择 DayNest 备份", "", "SQLite 数据库 (*.sqlite3 *.db)")
        if not name:
            return
        answer = QMessageBox.question(self, "恢复数据", "恢复将替换当前数据，并先创建一份安全备份。继续吗？")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            backup_path = self.storage.restore_from(name)
            self.tasks.refresh()
            self.calendar.refresh()
            self.tasks.changed.emit()
            self.notes.load(self.tasks.selected_date())
            self.settings_restored.emit()
        except Exception as exc:
            QMessageBox.critical(self, "恢复失败", str(exc))
        else:
            QMessageBox.information(self, "恢复完成", f"恢复前的数据备份在：\n{backup_path}")
