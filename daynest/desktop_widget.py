"""紧凑桌面组件；编辑数据的窗口独立存在。"""

import calendar
from datetime import date

from PySide6.QtCore import QDate, Qt, QTimer, Signal
from PySide6.QtGui import QActionGroup, QColor, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QGridLayout, QPushButton,
    QHBoxLayout, QLabel, QMenu, QMessageBox, QSlider, QSystemTrayIcon,
    QToolButton, QVBoxLayout, QWidget, QWidgetAction)

from .window import DragBar, app_icon
from .calendar_view import CalendarView


SIZES = {'small': (180, 180), 'medium': (360, 180), 'large': (360, 360), 'calendar': (560, 520)}


class TaskLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class DesktopWidget(QWidget):
    """背景透明度不影响文字；尺寸和位置保存在现有数据库。"""

    def __init__(self, storage, editor):
        super().__init__()
        self.storage = storage
        self.editor = editor
        self.tray = None
        self.quitting = False
        self.mode = 'normal'
        self.calendar_date = QDate.currentDate()
        self.preset = storage.get_setting('widget_size', 'medium')
        if self.preset not in SIZES:
            self.preset = 'medium'
        try:
            self.background_opacity = max(0, min(100, int(storage.get_setting('widget_opacity', '70'))))
        except ValueError:
            self.background_opacity = 70
        self.theme = storage.get_setting('widget_theme', 'light')
        if self.theme not in ('light', 'dark'):
            self.theme = 'light'
        self.setWindowTitle('DayNest 桌面组件')
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(*SIZES[self.preset])
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(18, 14, 18, 16)
        self.root.setSpacing(7)
        self.header = DragBar(self)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.brand = QLabel('DAYNEST')
        self.brand.setObjectName('brand')
        self.brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header_layout.addWidget(self.brand)
        header_layout.addStretch()
        self.menu_button = QToolButton()
        self.menu_button.setText('•••')
        self.menu_button.setToolTip('尺寸、透明度和更多设置')
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_button.setMenu(self.make_menu())
        header_layout.addWidget(self.menu_button)
        self.root.addWidget(self.header)
        self.body = QWidget()
        self.root.addWidget(self.body, 1)
        self.timer = QTimer(self)
        self.timer.setInterval(60_000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.rebuild()

    def make_menu(self):
        menu = QMenu(self)
        menu.addAction('打开日历和待办', self.open_editor)
        menu.addSeparator()
        sizes = menu.addMenu('组件尺寸')
        group = QActionGroup(sizes)
        group.setExclusive(True)
        for key, label in (('small', '小 · 180 × 180'), ('medium', '中 · 360 × 180'), ('large', '大 · 360 × 360'), ('calendar', '日历 · 560 × 520')):
            action = sizes.addAction(label)
            action.setCheckable(True)
            action.setChecked(key == self.preset)
            action.triggered.connect(lambda _checked=False, size=key: self.set_preset(size))
            group.addAction(action)
        self.size_actions = group
        colors = menu.addMenu('文字与背景')
        for key, label in (('light', '浅色'), ('dark', '深色')):
            action = colors.addAction(label)
            action.triggered.connect(lambda _checked=False, theme=key: self.set_theme(theme))
        transparency = menu.addMenu('背景不透明度')
        for value, label in ((0, '完全透明'), (35, '轻透明'), (70, '柔和'), (100, '不透明')):
            action = transparency.addAction(label)
            action.triggered.connect(lambda _checked=False, opacity=value: self.set_opacity(opacity))
        slider = QSlider(Qt.Orientation.Horizontal, transparency)
        slider.setRange(0, 100)
        slider.setValue(self.background_opacity)
        slider.setMinimumWidth(150)
        slider.valueChanged.connect(self.set_opacity)
        slider_action = QWidgetAction(transparency)
        slider_action.setDefaultWidget(slider)
        transparency.addAction(slider_action)
        self.opacity_slider = slider
        levels = menu.addMenu('窗口层级')
        for key, label in (('normal', '普通'), ('bottom', '桌面靠后（实验）'), ('top', '置顶')):
            action = levels.addAction(label)
            action.triggered.connect(lambda _checked=False, mode=key: self.set_mode(mode))
            if key == 'bottom':
                self.bottom_action = action
                action.setEnabled(False)  # 没有托盘时不能冒险让组件落到桌面后面。
        menu.addSeparator()
        self.hide_action = menu.addAction('隐藏到托盘', self.hide)
        self.hide_action.setEnabled(False)
        menu.addAction('退出 DayNest', self.quit_app)
        return menu

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        base = QColor('#f6f8fa' if self.theme == 'light' else '#1c2832')
        base.setAlpha(round(255 * self.background_opacity / 100))
        painter.setBrush(base)
        if self.background_opacity:
            edge = QColor('#ffffff' if self.theme == 'light' else '#a7bfca')
            edge.setAlpha(min(145, round(self.background_opacity * 1.4)))
            painter.setPen(QPen(edge, 1))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 24, 24)

    def apply_style(self):
        ink = '#263540' if self.theme == 'light' else '#f3f7f7'
        muted = '#677b88' if self.theme == 'light' else '#b6c8cd'
        accent = '#3f7f98' if self.theme == 'light' else '#9fe0d5'
        panel_alpha = round(self.background_opacity * .65)
        self.setStyleSheet(f"""
            QWidget {{ background: transparent; color: {ink}; font-family: 'Microsoft YaHei UI', 'Segoe UI'; }}
            QLabel#brand {{ color: {muted}; font-size: 10px; font-weight: 700; letter-spacing: 2px; }}
            QLabel#dateNumber {{ color: {ink}; font-size: 48px; font-weight: 600; }}
            QLabel#dateSmall {{ color: {muted}; font-size: 11px; font-weight: 600; }}
            QLabel#section {{ color: {muted}; font-size: 11px; font-weight: 600; }}
            QLabel#task {{ color: {ink}; font-size: 12px; }}
            QLabel#weekday {{ color: {muted}; font-size: 10px; }}
            QLabel#calendarDay {{ color: {ink}; font-size: 11px; }}
            QLabel#today {{ background: {accent}; color: white; border-radius: 11px; font-size: 11px; }}
            QLabel#calendarHeading {{ color: {ink}; font-size: 15px; font-weight: 600; }}
            QLabel#calendarWeekday {{ color: {muted}; font-size: 11px; }}
            QWidget#selectedTasks {{ background: rgba(255, 255, 255, {panel_alpha}); border-radius: 12px; }}
            QPushButton {{ color: {ink}; background: transparent; border: none; border-radius: 8px; padding: 3px; font-size: 11px; }}
            QPushButton:hover {{ background: rgba(105, 160, 176, 55); }}
            QPushButton#calendarSelected {{ background: transparent; }}
            QPushButton#calendarAdd {{ background: #588fa7; color: white; border-radius: 15px; font-size: 20px; padding: 0; }}
            QPushButton#calendarToday {{ color: {muted}; font-size: 11px; padding: 4px 8px; }}
            QPushButton#calendarNav {{ color: {muted}; font-size: 21px; padding: 0; }}
            QPushButton#moreTasks {{ color: {muted}; font-size: 11px; text-align: right; }}
            QToolButton {{ border: none; color: {muted}; font-size: 16px; font-weight: 600; padding: 2px; }}
            QToolButton:hover {{ color: {accent}; }}
            QToolButton::menu-indicator {{ image: none; }}
            QMenu {{ background: #f7f9fa; color: #263540; border: 1px solid #d5dfe3; border-radius: 8px; padding: 5px; }}
            QMenu::item {{ padding: 7px 22px 7px 12px; }}
            QMenu::item:selected {{ background: #e3edf0; border-radius: 5px; }}
        """)
        self.update()

    def date_block(self, compact=False):
        today = date.today()
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        month = QLabel(f'{today.year}  /  {today.month:02d}')
        month.setObjectName('dateSmall')
        number = QLabel(f'{today.day:02d}')
        number.setObjectName('dateNumber')
        weekday = QLabel(('星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日')[today.weekday()])
        weekday.setObjectName('dateSmall')
        for label in (month, number, weekday):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(label)
        if not compact:
            layout.addStretch()
        return holder

    def tasks_block(self, limit, selected_date=None, panel=False):
        holder = QWidget()
        if panel:
            holder.setObjectName('selectedTasks')
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(12, 8, 12, 8) if panel else layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        day = selected_date or date.today().isoformat()
        rows = self.storage.tasks_for(day)
        remaining = [row for row in rows if not row[2]]
        parsed = date.fromisoformat(day)
        when = f'{parsed.month}月{parsed.day}日' + ('  ·  今天' if day == date.today().isoformat() else '')
        heading = QLabel(f'{when if panel else "今天" if day == date.today().isoformat() else day}  ·  {len(remaining)} 项待办')
        heading.setObjectName('section')
        layout.addWidget(heading)
        if not remaining:
            empty = QLabel('给今天留一点空白')
            empty.setObjectName('task')
            layout.addWidget(empty)
        for task_id, title, _ in remaining[:limit]:
            line = QWidget()
            row = QHBoxLayout(line)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(5)
            check = QToolButton()
            check.setText('○')
            check.setToolTip('完成待办')
            check.clicked.connect(lambda _checked=False, task=task_id: self.complete_task(task))
            row.addWidget(check)
            label = TaskLabel(title)
            label.setObjectName('task')
            label.setToolTip(title)
            label.setWordWrap(False)
            label.setMinimumWidth(0)
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.clicked.connect(lambda task=task_id: self.edit_task(task))
            row.addWidget(label, 1)
            if panel:
                task = self.storage.task(task_id)
                if task and task[4]:
                    time = QLabel(task[4])
                    time.setObjectName('section')
                    row.addWidget(time)
            layout.addWidget(line)
        if not panel:
            layout.addStretch()
        return holder

    def calendar_block(self):
        today = date.today()
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(2)
        for column, day in enumerate(('一', '二', '三', '四', '五', '六', '日')):
            label = QLabel(day)
            label.setObjectName('weekday')
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(label, 0, column)
        for row, week in enumerate(calendar.Calendar(firstweekday=0).monthdayscalendar(today.year, today.month), 1):
            for column, day in enumerate(week):
                label = QLabel(str(day) if day else '')
                label.setObjectName('today' if day == today.day else 'calendarDay')
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setFixedSize(22, 22)
                grid.addWidget(label, row, column, Qt.AlignmentFlag.AlignHCenter)
        return holder

    def rebuild(self):
        old = self.body
        old.hide()
        self.body = QWidget()
        self.root.replaceWidget(old, self.body)
        old.deleteLater()
        if self.preset == 'small':
            layout = QVBoxLayout(self.body)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            layout.addWidget(self.date_block(True))
            count = sum(not row[2] for row in self.storage.tasks_for(date.today().isoformat()))
            label = QLabel(f'今天 · {count} 项待办')
            label.setObjectName('section')
            layout.addWidget(label)
            layout.addStretch()
        elif self.preset == 'medium':
            layout = QHBoxLayout(self.body)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(18)
            date_card = self.date_block()
            date_card.setFixedWidth(95)
            layout.addWidget(date_card)
            layout.addWidget(self.tasks_block(2), 1)
        elif self.preset == 'large':
            layout = QVBoxLayout(self.body)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            today = date.today()
            heading = QLabel(f'{today.year}年{today.month}月   ·   今天 {today.day} 日')
            heading.setObjectName('task')
            layout.addWidget(heading)
            layout.addWidget(self.calendar_block())
            layout.addWidget(self.tasks_block(3), 1)
        else:
            layout = QVBoxLayout(self.body)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            self.calendar = CalendarView(self.storage, self.theme, self.background_opacity)
            self.calendar.setSelectedDate(self.calendar_date)
            self.calendar.selectionChanged.connect(self.calendar_changed)
            self.calendar.addRequested.connect(self.add_calendar_task)
            layout.addWidget(self.calendar, 1)
            layout.addWidget(self.tasks_block(3, self.calendar_date.toString('yyyy-MM-dd'), panel=True))
            more = QPushButton('查看全部 / 添加待办  ›')
            more.setObjectName('moreTasks')
            more.clicked.connect(self.open_calendar_tasks)
            layout.addWidget(more)
        self.setFixedSize(*SIZES[self.preset])
        self.apply_style()

    def refresh(self):
        self.rebuild()

    def calendar_changed(self):
        self.calendar_date = self.calendar.selectedDate()
        self.editor.content.tasks.date.setDate(self.calendar_date)
        self.refresh()

    def select_calendar_date(self, day):
        if day != self.calendar_date:
            self.calendar_date = day
            if self.preset == 'calendar':
                self.refresh()

    def open_calendar_tasks(self):
        self.editor.content.tasks.date.setDate(self.calendar_date)
        self.editor.content.show_selected_tasks()
        self.open_editor()

    def add_calendar_task(self):
        self.editor.content.tasks.date.setDate(self.calendar_date)
        self.editor.content.show_selected_tasks()
        self.open_editor()
        self.editor.content.tasks.new_dialog()

    def edit_task(self, task_id):
        self.open_editor()
        self.editor.content.tabs.setCurrentWidget(self.editor.content.tasks)
        self.editor.content.tasks.edit_task(task_id)

    def set_preset(self, preset):
        if preset not in SIZES:
            return
        self.preset = preset
        for action, key in zip(self.size_actions.actions(), SIZES):
            action.setChecked(key == preset)
        self.storage.set_setting('widget_size', preset)
        self.rebuild()
        self.keep_on_screen()

    def set_theme(self, theme):
        self.theme = theme
        self.storage.set_setting('widget_theme', theme)
        if self.preset == 'calendar':
            self.calendar.set_appearance(theme, self.background_opacity)
        self.apply_style()

    def set_opacity(self, value):
        self.background_opacity = max(0, min(100, int(value)))
        self.opacity_slider.blockSignals(True)
        self.opacity_slider.setValue(self.background_opacity)
        self.opacity_slider.blockSignals(False)
        self.storage.set_setting('widget_opacity', self.background_opacity)
        if self.preset == 'calendar':
            self.calendar.set_appearance(self.theme, self.background_opacity)
        self.apply_style()

    def set_mode(self, mode):
        if mode not in ('normal', 'bottom', 'top'):
            return
        self.mode = mode
        self.storage.set_setting('widget_mode', mode)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, mode == 'top')
        self.setWindowFlag(Qt.WindowType.WindowStaysOnBottomHint, mode == 'bottom')
        self.show()

    def reload_from_storage(self):
        preset = self.storage.get_setting('widget_size', 'medium')
        self.preset = preset if preset in SIZES else 'medium'
        theme = self.storage.get_setting('widget_theme', 'light')
        self.theme = theme if theme in ('light', 'dark') else 'light'
        try:
            self.background_opacity = max(0, min(100, int(self.storage.get_setting('widget_opacity', '70'))))
        except ValueError:
            self.background_opacity = 70
        self.opacity_slider.blockSignals(True)
        self.opacity_slider.setValue(self.background_opacity)
        self.opacity_slider.blockSignals(False)
        for action, key in zip(self.size_actions.actions(), SIZES):
            action.setChecked(key == self.preset)
        self.rebuild()

    def complete_task(self, task_id):
        try:
            self.storage.complete_task(task_id, True)
            self.editor.content.tasks.refresh()
            self.editor.content.calendar.refresh()
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, '无法更新待办', str(exc))

    def open_editor(self):
        self.editor.show_window()
        self.editor.content.tasks.input.setFocus()

    def mouseDoubleClickEvent(self, event):
        self.open_editor()
        event.accept()

    def contextMenuEvent(self, event):
        self.menu_button.menu().exec(event.globalPos())

    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip('DayNest')
        menu = QMenu(self)
        menu.addAction('显示桌面组件', self.show_widget)
        menu.addAction('恢复普通窗口层级', lambda: self.set_mode('normal'))
        menu.addAction('打开日历和待办', self.open_editor)
        menu.addAction('退出', self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()
        self.hide_action.setEnabled(True)
        self.bottom_action.setEnabled(True)
        return True

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_widget()

    def show_widget(self):
        self.showNormal()
        if self.mode != 'bottom':
            self.raise_()

    def restore_position(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        try:
            x = int(self.storage.get_setting('widget_x', str(area.right() - self.width() - 30)))
            y = int(self.storage.get_setting('widget_y', str(area.top() + 50)))
        except ValueError:
            x, y = area.right() - self.width() - 30, area.top() + 50
        # 至少有一部分在任一显示器内，避免拔掉显示器后找不到组件。
        visible = any(s.availableGeometry().intersects(self.geometry().translated(x - self.x(), y - self.y())) for s in QApplication.screens())
        self.move(x, y) if visible else self.move(area.right() - self.width() - 30, area.top() + 50)

    def keep_on_screen(self):
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        x = max(area.left(), min(self.x(), area.right() - self.width() + 1))
        y = max(area.top(), min(self.y(), area.bottom() - self.height() + 1))
        self.move(x, y)

    def save_position(self):
        self.storage.set_setting('widget_x', self.x())
        self.storage.set_setting('widget_y', self.y())

    def quit_app(self):
        if self.editor.quit_guard is not None and not self.editor.quit_guard():
            return
        self.quitting = True
        self.editor.close()
        if self.close():
            QApplication.quit()
        else:
            self.quitting = False

    def closeEvent(self, event):
        if self.editor.quit_guard is not None and not self.editor.quit_guard():
            event.ignore()
            return
        try:
            self.save_position()
        except Exception as exc:
            QMessageBox.warning(self, '位置保存失败', str(exc))
        event.accept()
        if not self.quitting:
            self.editor.close()
            QApplication.quit()
