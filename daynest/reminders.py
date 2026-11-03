"""应用运行期间显示待办卡片，并将稍后提醒时间保存在本地。"""

from datetime import datetime, timedelta

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QTimer
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMenu,
    QMessageBox, QPushButton, QVBoxLayout)


class ReminderCard(QDialog):
    def __init__(self, title, day, time, service, task_id):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.service = service
        self.task_id = task_id
        self.original = (title, day, time)
        self.resolved = False
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle('DayNest 待办提醒')
        self.setMinimumWidth(340)
        self.setStyleSheet('''
            QDialog { background: transparent; }
            QFrame#reminderPanel { background: rgba(244, 247, 250, 246); border: 1px solid rgba(255, 255, 255, 190); border-radius: 18px; }
            QLabel { color: #263b4b; font-family: "Microsoft YaHei UI"; font-size: 13px; }
            QLabel#brand { color: #718898; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
            QLabel#bell { color: #528aa2; background: #dcebf0; border-radius: 12px; font-size: 21px; }
            QLabel#reminderDate { color: #78909e; font-size: 11px; }
            QLabel#name { font-size: 18px; font-weight: 600; }
            QPushButton { color: #315f73; background: #fff; border: 1px solid #c8dce5; border-radius: 8px; padding: 8px 12px; }
            QPushButton#complete { color: white; background: #4e849c; }
            QPushButton#dismiss { color: #718898; background: transparent; border: none; font-size: 18px; padding: 0; }
            QMenu { background: #f7fafb; color: #263b4b; }
        ''')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(3, 3, 3, 3)
        panel = QFrame()
        panel.setObjectName('reminderPanel')
        outer.addWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(12)
        header = QHBoxLayout()
        brand = QLabel('DAYNEST')
        brand.setObjectName('brand')
        header.addWidget(brand)
        header.addStretch()
        dismiss = QPushButton('×')
        dismiss.setObjectName('dismiss')
        dismiss.setFixedSize(26, 26)
        dismiss.setToolTip('关闭提醒')
        dismiss.clicked.connect(self.close)
        header.addWidget(dismiss)
        layout.addLayout(header)
        main = QHBoxLayout()
        bell = QLabel('◷')
        bell.setObjectName('bell')
        bell.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bell.setFixedSize(44, 44)
        main.addWidget(bell)
        text = QVBoxLayout()
        self.name = QLabel(title)
        self.name.setObjectName('name')
        self.name.setWordWrap(True)
        text.addWidget(self.name)
        date_label = QLabel(f'{day}  {time}')
        date_label.setObjectName('reminderDate')
        text.addWidget(date_label)
        main.addLayout(text, 1)
        layout.addLayout(main)
        actions = QHBoxLayout()
        later = QPushButton('稍后提醒  ▾')
        menu = QMenu(later)
        menu.addAction('10 分钟后', lambda: self.service.snooze(self, 10))
        menu.addAction('1 小时后', lambda: self.service.snooze(self, 60))
        later.setMenu(menu)
        actions.addWidget(later)
        complete = QPushButton('完成')
        complete.setObjectName('complete')
        complete.clicked.connect(lambda: self.service.complete(self))
        actions.addWidget(complete)
        layout.addLayout(actions)

    def closeEvent(self, event):
        if not self.resolved and not self.service.dismiss(self):
            event.ignore()
            return
        self.service.cards.pop(self.task_id, None)
        event.accept()


class ReminderService:
    def __init__(self, storage, widget, start=True, clock=None, on_change=None):
        self.storage = storage
        self.widget = widget
        self.clock = clock or datetime.now
        self.on_change = on_change or (lambda: None)
        self.cards = {}
        self.timer = QTimer(widget)
        self.timer.setInterval(15_000)
        self.timer.timeout.connect(self.check)
        if start:
            self.timer.start()
            QTimer.singleShot(1000, self.check)

    def shutdown(self):
        self.timer.stop()
        for card in list(self.cards.values()):
            # 退出应用不算用户已读，下次启动时仍可看到。
            card.resolved = True
            card.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def check(self, now=None):
        try:
            for task_id, card in list(self.cards.items()):
                task = self.storage.task(task_id)
                if not task or task[3] or (task[1], task[2], task[4]) != card.original:
                    card.resolved = True
                    card.close()
            # 不把尚未操作的提醒重复弹出；同时最多展示三张。
            for task_id, title, day, time in self.storage.due_reminders(now or self.clock()):
                if task_id in self.cards or len(self.cards) >= 3:
                    continue
                card = ReminderCard(title, day, time, self, task_id)
                self.cards[task_id] = card
                card.show()
                screen = QApplication.primaryScreen()
                if screen:
                    area = screen.availableGeometry()
                    card.move(area.right() - card.width() - 20,
                              area.top() + 30 + (len(self.cards) - 1) * (card.height() + 12))
                card.raise_()
        except Exception as exc:
            print(f'待办提醒检查失败：{exc}')

    def snooze(self, card, minutes):
        try:
            self.storage.snooze_task(card.task_id, self.clock() + timedelta(minutes=minutes))
            card.resolved = True
            card.close()
        except Exception as exc:
            QMessageBox.warning(card, '无法稍后提醒', str(exc))

    def complete(self, card):
        try:
            self.storage.complete_task(card.task_id, True)
            card.resolved = True
            card.close()
            self.on_change()
        except Exception as exc:
            QMessageBox.warning(card, '无法完成待办', str(exc))

    def dismiss(self, card):
        try:
            self.storage.mark_reminded(card.task_id)
            return True
        except Exception as exc:
            QMessageBox.warning(card, '无法关闭提醒', str(exc))
            return False
