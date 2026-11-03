"""待办列表和编辑窗口；存储逻辑由 Storage 负责。"""

from datetime import date, timedelta

from PySide6.QtCore import QDate, QSize, QTime, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateEdit, QDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QScrollArea,
    QMessageBox, QPushButton, QTextEdit, QTimeEdit, QToolButton, QVBoxLayout, QWidget)

from .window import DragBar


class TaskDialog(QDialog):
    def __init__(self, selected_date, task=None, parent=None, repeat_rule='none'):
        super().__init__(parent)
        self.setWindowTitle('编辑待办' if task else '添加待办')
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(360)
        self.resize(410, 560)
        screen = QApplication.primaryScreen()
        if screen:
            self.setMaximumHeight(max(350, screen.availableGeometry().height() - 30))
        self.setStyleSheet('''
            QDialog { background: transparent; }
            QFrame#taskDialogPanel { background: rgba(244, 247, 250, 246); border: 1px solid rgba(255, 255, 255, 190); border-radius: 20px; }
            QWidget { color: #304a5d; font-family: "Microsoft YaHei UI"; font-size: 12px; }
            QLabel#dialogBrand { color: #718898; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
            QLabel#pageTitle { color: #28485a; font-size: 20px; font-weight: 700; }
            QLabel#fieldLabel { color: #788d9b; font-size: 11px; font-weight: 600; }
            QLineEdit, QDateEdit, QTimeEdit, QTextEdit, QComboBox {
                background: rgba(255, 255, 255, 210); color: #263b4b; border: 1px solid #e2eaee; border-radius: 9px; padding: 7px;
            }
            QComboBox:disabled { background: #e5ebee; color: #657d8a; }
            QComboBox QAbstractItemView { background: #ffffff; color: #263b4b; selection-background-color: #dcebf0; }
            QCalendarWidget QWidget { background: #f6f9fa; color: #304a5d; }
            QCalendarWidget QWidget#qt_calendar_navigationbar { background: #dceaf0; }
            QCalendarWidget QToolButton { color: #315f73; background: transparent; border: none; padding: 4px; }
            QCalendarWidget QAbstractItemView:enabled { background: #f6f9fa; color: #304a5d; selection-background-color: #548ba1; selection-color: white; }
            QPushButton { color: #315f73; background: rgba(255, 255, 255, 180); border: 1px solid #e2eaee; border-radius: 9px; padding: 7px 12px; }
            QPushButton:hover { background: #dcebf0; }
            QPushButton#quickDate { background: #e6eef2; border: none; border-radius: 12px; padding: 5px 12px; }
            QPushButton#saveTask { color: white; background: #4b849c; border: none; font-size: 14px; font-weight: 600; padding: 10px; }
            QPushButton#saveTask:hover { background: #3f7690; }
            QPushButton#closeDialog { background: transparent; border: none; font-size: 19px; padding: 0; color: #778d99; }
            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
        ''')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        panel = QFrame()
        panel.setObjectName('taskDialogPanel')
        outer.addWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 18, 24, 22)
        layout.setSpacing(10)
        bar = DragBar()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        brand = QLabel('DAYNEST')
        brand.setObjectName('dialogBrand')
        brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        bar_layout.addWidget(brand)
        bar_layout.addStretch()
        close = QPushButton('×')
        close.setObjectName('closeDialog')
        close.setFixedSize(28, 28)
        close.setToolTip('取消')
        close.clicked.connect(self.reject)
        bar_layout.addWidget(close)
        layout.addWidget(bar)
        title = QLabel('编辑待办' if task else '添加待办')
        title.setObjectName('pageTitle')
        layout.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QVBoxLayout(content)
        form.setContentsMargins(0, 0, 2, 0)
        form.setSpacing(8)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        def add_field(label_text, field):
            label = QLabel(label_text)
            label.setObjectName('fieldLabel')
            form.addWidget(label)
            if isinstance(field, QWidget):
                form.addWidget(field)
            else:
                form.addLayout(field)

        self.title_input = QLineEdit(task[1] if task else '')
        self.title_input.setPlaceholderText('要做什么？')
        add_field('任务标题', self.title_input)
        self.date = QDateEdit(QDate.fromString(task[2] if task else selected_date, 'yyyy-MM-dd'))
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat('yyyy年M月d日')
        picker = self.date.calendarWidget()
        for name, glyph in (('qt_calendar_prevmonth', '‹'), ('qt_calendar_nextmonth', '›')):
            navigation = picker.findChild(QToolButton, name)
            if navigation:
                navigation.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
                navigation.setText(glyph)
                navigation.setAccessibleName('上个月' if glyph == '‹' else '下个月')
        quick_dates = QHBoxLayout()
        quick_dates.setSpacing(6)
        for name, days in (('今天', 0), ('明天', 1), ('下周', 7)):
            button = QPushButton(name)
            button.setObjectName('quickDate')
            button.clicked.connect(lambda _checked=False, offset=days: self.date.setDate(QDate.currentDate().addDays(offset)))
            quick_dates.addWidget(button)
        quick_dates.addStretch()
        form.addLayout(quick_dates)
        add_field('日期', self.date)
        row = QHBoxLayout()
        self.remind = QCheckBox('提醒')
        self.time = QTimeEdit(QTime(9, 0))
        self.time.setDisplayFormat('HH:mm')
        if task and task[4]:
            self.remind.setChecked(True)
            self.time.setTime(QTime.fromString(task[4], 'HH:mm'))
        self.time.setEnabled(self.remind.isChecked())
        self.remind.toggled.connect(self.time.setEnabled)
        row.addWidget(self.remind)
        row.addWidget(self.time, 1)
        add_field('提醒时间', row)
        self.repeat = QComboBox()
        for label, key in (('不重复', 'none'), ('每天', 'daily'), ('每周', 'weekly'), ('每月', 'monthly')):
            self.repeat.addItem(label, key)
        self.repeat.setCurrentIndex(max(0, self.repeat.findData(repeat_rule)))
        self.scope = QComboBox()
        self.scope.addItem('仅本次', 'one')
        self.scope.addItem('本次及以后', 'future')
        if task and repeat_rule != 'none':
            add_field('修改范围', self.scope)
            self.repeat.setEnabled(False)
            self.scope.currentIndexChanged.connect(lambda: self.repeat.setEnabled(self.scope.currentData() == 'future'))
        add_field('重复', self.repeat)
        self.details = QTextEdit()
        self.details.setPlaceholderText('可选')
        self.details.setFixedHeight(68)
        self.details.setPlainText(task[5] if task else '')
        add_field('备注（可选）', self.details)
        form.addStretch()
        save = QPushButton('保存')
        save.setObjectName('saveTask')
        save.clicked.connect(self.accept)
        layout.addWidget(save)

    def accept(self):
        if not self.title_input.text().strip():
            self.title_input.setFocus()
            return
        super().accept()

    def values(self):
        return (self.title_input.text().strip(), self.date.date().toString('yyyy-MM-dd'),
                self.time.time().toString('HH:mm') if self.remind.isChecked() else '',
                self.details.toPlainText().strip(), self.repeat.currentData())


class TaskPane(QWidget):
    changed = Signal()

    def __init__(self, storage):
        super().__init__()
        self.storage = storage
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)
        heading = QHBoxLayout()
        title = QLabel('待办事项')
        title.setObjectName('pageTitle')
        heading.addWidget(title)
        heading.addStretch()
        add = QPushButton('＋ 添加待办')
        add.setObjectName('addTask')
        add.clicked.connect(self.new_dialog)
        heading.addWidget(add)
        layout.addLayout(heading)
        quick = QHBoxLayout()
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat('M月d日')
        self.date.dateChanged.connect(self.refresh)
        quick.addWidget(self.date)
        self.input = QLineEdit()
        self.input.setPlaceholderText('快速添加到所选日期，按回车')
        self.input.returnPressed.connect(self.add_task)
        quick.addWidget(self.input, 1)
        self.date_only = QCheckBox('只看所选日期')
        self.date_only.toggled.connect(self.refresh)
        quick.addWidget(self.date_only)
        layout.addLayout(quick)
        self.list = QListWidget()
        self.list.setObjectName('taskList')
        self.list.itemChanged.connect(self.change_task)
        self.list.itemDoubleClicked.connect(self.edit_item)
        layout.addWidget(self.list, 1)
        actions = QHBoxLayout()
        hint = QLabel('双击待办可修改时间和备注')
        hint.setObjectName('hint')
        actions.addWidget(hint)
        actions.addStretch()
        edit = QPushButton('编辑')
        edit.clicked.connect(self.edit_selected)
        actions.addWidget(edit)
        delete = QPushButton('删除')
        delete.clicked.connect(self.delete_task)
        actions.addWidget(delete)
        layout.addLayout(actions)
        self.refresh()

    def selected_date(self):
        return self.date.date().toString('yyyy-MM-dd')

    def refresh(self, *_):
        self.list.blockSignals(True)
        try:
            self.list.clear()
            today = date.today().isoformat()
            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            groups = {'已过期': [], '今天': [], '明天': [], '之后': [], '已完成': []}
            for task in self.storage.all_tasks():
                day, done = task[2], task[3]
                if self.date_only.isChecked() and day != self.selected_date():
                    continue
                group = '已完成' if done else ('已过期' if day < today else '今天' if day == today else '明天' if day == tomorrow else '之后')
                groups[group].append(task)
            for name, tasks in groups.items():
                if not tasks:
                    continue
                header = QListWidgetItem(f'{name}   {len(tasks)}')
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                header.setForeground(QBrush(QColor('#618397')))
                header.setSizeHint(QSize(0, 36))
                font = header.font()
                font.setBold(True)
                header.setFont(font)
                self.list.addItem(header)
                for task_id, title, day, completed, reminder, _details in tasks:
                    suffix = ('  ·  ' + reminder) if reminder else ''
                    if name not in ('今天', '明天'):
                        suffix = '  ·  ' + day + suffix
                    item = QListWidgetItem(title + suffix)
                    item.setSizeHint(QSize(0, 34))
                    item.setToolTip('双击编辑：' + title)
                    item.setData(Qt.ItemDataRole.UserRole, task_id)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Checked if completed else Qt.CheckState.Unchecked)
                    self.list.addItem(item)
        finally:
            self.list.blockSignals(False)

    def add_task(self):
        title = self.input.text().strip()
        if not title:
            self.input.setFocus()
            return
        try:
            self.storage.add_task(title, self.selected_date())
            self.input.clear()
            self.refresh()
            self.changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, '无法保存待办', str(exc))

    def new_dialog(self):
        dialog = TaskDialog(self.selected_date(), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.storage.add_task(*dialog.values())
                self.refresh()
                self.changed.emit()
            except Exception as exc:
                QMessageBox.critical(self, '无法保存待办', str(exc))

    def edit_selected(self):
        self.edit_item(self.list.currentItem())

    def edit_item(self, item):
        task_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.edit_task(task_id)

    def edit_task(self, task_id):
        task = self.storage.task(task_id) if task_id is not None else None
        if not task:
            return
        dialog = TaskDialog(self.selected_date(), task, self, self.storage.task_repeat(task_id))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.storage.update_task(task_id, *dialog.values(), scope=dialog.scope.currentData())
                self.refresh()
                self.changed.emit()
            except Exception as exc:
                QMessageBox.critical(self, '无法更新待办', str(exc))

    def change_task(self, item):
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if task_id is None:
            return
        try:
            self.storage.complete_task(task_id, item.checkState() == Qt.CheckState.Checked)
            self.refresh()
            self.changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, '无法更新待办', str(exc))
            self.refresh()

    def delete_task(self):
        item = self.list.currentItem()
        task_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if task_id is not None:
            try:
                self.storage.delete_task(task_id)
                self.refresh()
                self.changed.emit()
            except Exception as exc:
                QMessageBox.critical(self, '无法删除待办', str(exc))
