"""带待办摘要的月历，供管理窗口和桌面组件复用。"""

import calendar
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


class CalendarCell(QPushButton):
    """日期、圆点和事项摘要分开绘制，保持点击区域完整。"""

    def __init__(self, day, items, selected, theme='light', surface_opacity=70):
        self.number = day.day()
        self.items = items
        self.selected = selected
        self.theme = theme
        self.surface_opacity = surface_opacity
        snippet = items[0][:5] + ('…' if len(items[0]) > 5 else '') if items else ''
        extra = f' +{len(items)-1}' if len(items) > 1 else ''
        super().__init__(f'{self.number}\n{snippet}{extra}' if items else str(self.number))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName('calendarSelected' if selected else 'calendarCell')
        self.setToolTip('\n'.join(items) if items else day.toString('yyyy-MM-dd'))
        self.setAccessibleName(f'{day.toString("yyyy-MM-dd")} ' + '，'.join(items))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = self.theme == 'dark'
        line = QColor('#c8d5de' if not dark else '#a9bdc7')
        line.setAlpha(round(self.surface_opacity * .32))
        p.setPen(QPen(line, 1))
        p.drawLine(self.rect().topRight(), self.rect().bottomRight())
        p.drawLine(self.rect().bottomLeft(), self.rect().bottomRight())
        if self.underMouse():
            hover = QColor('#76aaba')
            hover.setAlpha(22)
            p.fillRect(self.rect().adjusted(1, 1, -1, -1), hover)
        number_font = QFont(self.font())
        number_font.setPixelSize(12)
        p.setFont(number_font)
        top = 1 if self.height() >= 34 else 0
        circle = self.rect().adjusted(0, top, 0, 0)
        circle.setHeight(19)
        circle.setWidth(19)
        circle.moveCenter(self.rect().center())
        circle.moveTop(top)
        if self.selected:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#4f8ba4'))
            p.drawEllipse(circle)
        p.setPen(QColor('#ffffff' if self.selected else ('#edf5f5' if dark else '#263d50')))
        p.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(self.number))
        if self.items and self.height() >= 34:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#77bdba' if dark else '#4f91a6'))
            p.drawEllipse(self.width() // 2 - 2, top + 20, 4, 4)
            font = QFont(self.font())
            font.setPixelSize(9 if self.height() < 44 else 10)
            p.setFont(font)
            p.setPen(QColor('#d1e4e5' if dark else '#557a8b'))
            content = self.items[0] + (f' +{len(self.items)-1}' if len(self.items) > 1 else '')
            text = p.fontMetrics().elidedText(content, Qt.TextElideMode.ElideRight, max(1, self.width() - 5))
            p.drawText(self.rect().adjusted(2, top + 24, -2, -1), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, text)


class CalendarView(QWidget):
    selectionChanged = Signal()
    addRequested = Signal()

    def __init__(self, storage, theme='light', surface_opacity=70):
        super().__init__()
        self.storage = storage
        self.theme = theme
        self.surface_opacity = surface_opacity
        self._selected = QDate.currentDate()
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(4)
        bar = QHBoxLayout()
        self.previous = QPushButton('‹')
        self.previous.setObjectName('calendarNav')
        self.previous.setFixedWidth(34)
        self.previous.clicked.connect(lambda: self.change_month(-1))
        self.next = QPushButton('›')
        self.next.setObjectName('calendarNav')
        self.next.setFixedWidth(34)
        self.next.clicked.connect(lambda: self.change_month(1))
        self.heading = QLabel()
        self.heading.setObjectName('calendarHeading')
        self.add_button = QPushButton('＋')
        self.add_button.setObjectName('calendarAdd')
        self.add_button.setToolTip('添加所选日期的待办')
        self.add_button.setFixedSize(30, 30)
        self.add_button.clicked.connect(self.addRequested)
        bar.addWidget(self.heading)
        bar.addWidget(self.previous)
        bar.addWidget(self.next)
        bar.addStretch()
        self.today_button = QPushButton('今天')
        self.today_button.setObjectName('calendarToday')
        self.today_button.clicked.connect(lambda: self.setSelectedDate(QDate.currentDate()))
        bar.addWidget(self.today_button)
        bar.addWidget(self.add_button)
        self.root.addLayout(bar)
        self.grid = QGridLayout()
        self.grid.setSpacing(2)
        self.root.addLayout(self.grid, 1)
        self.refresh()

    def selectedDate(self):
        return self._selected

    def setSelectedDate(self, value):
        if value.isValid() and value != self._selected:
            self._selected = value
            self.refresh()
            self.selectionChanged.emit()

    def change_month(self, amount):
        self.setSelectedDate(self._selected.addMonths(amount))

    def set_appearance(self, theme, opacity):
        self.theme, self.surface_opacity = theme, opacity
        for cell in self.findChildren(CalendarCell):
            cell.theme, cell.surface_opacity = theme, opacity
            cell.update()

    def refresh(self, *_):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        year, month = self._selected.year(), self._selected.month()
        self.heading.setText(f'{year}年{month}月')
        first = date(year, month, 1)
        last = date(year, month, calendar.monthrange(year, month)[1])
        tasks = {}
        for _id, title, due, completed in self.storage.tasks_between(first.isoformat(), last.isoformat()):
            if not completed:
                tasks.setdefault(due, []).append(title)
        for col, name in enumerate(('一', '二', '三', '四', '五', '六', '日')):
            label = QLabel(name)
            label.setObjectName('calendarWeekday')
            label.setFixedHeight(20)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(label, 0, col)
            self.grid.setColumnStretch(col, 1)
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
        for row in range(1, 7):
            self.grid.setRowStretch(row, 0)
        for row, week in enumerate(weeks, 1):
            self.grid.setRowStretch(row, 1)
            for col, number in enumerate(week):
                if not number:
                    continue
                day = QDate(year, month, number)
                items = tasks.get(day.toString('yyyy-MM-dd'), [])
                button = CalendarCell(day, items, day == self._selected, self.theme, self.surface_opacity)
                button.clicked.connect(lambda _checked=False, selected=day: self.setSelectedDate(selected))
                self.grid.addWidget(button, row, col)
