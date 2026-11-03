"""窗口与托盘；桌面挂接实验不会改变这个稳定入口。"""

from PySide6.QtCore import Qt, QDate, QLocale, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QFrame, QHBoxLayout,
    QLabel, QMainWindow, QMenu, QPushButton, QSizeGrip, QSlider, QSystemTrayIcon, QVBoxLayout, QWidget)


def app_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#73c7c1"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 18, 18)
    painter.setPen(QColor("#142c35"))
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(32)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "D")
    painter.end()
    return QIcon(pixmap)


class DragBar(QFrame):
    """仅标题区响应拖动，避免影响控件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.offset = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.offset = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self.offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.offset = None
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    closing = Signal()

    def __init__(self, storage=None):
        super().__init__()
        self.storage = storage
        self.color = QColor("#f4f7f9")
        if storage:
            candidate = QColor(storage.get_setting("editor_background_v2", "#f4f7f9"))
            if candidate.isValid():
                self.color = candidate
        self.quitting = False
        self.quit_guard = None
        self.setWindowTitle("DayNest")
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        try:
            width = int(storage.get_setting("width", "560")) if storage else 560
            height = int(storage.get_setting("height", "560")) if storage else 560
        except ValueError:
            width, height = 560, 560
        self.resize(max(520, min(1600, width)), max(520, min(1200, height)))
        self.setMinimumSize(520, 520)
        self.outer = QWidget()
        self.setCentralWidget(self.outer)
        outer_layout = QVBoxLayout(self.outer)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        self.panel = QFrame()
        self.panel.setObjectName("panel")
        outer_layout.addWidget(self.panel)
        self.layout = QVBoxLayout(self.panel)
        self.layout.setContentsMargins(20, 16, 20, 20)
        self.layout.setSpacing(12)

        bar = DragBar()
        header = QHBoxLayout(bar)
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("DayNest")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        self.date_label = QLabel(self.today_text())
        self.date_timer = QTimer(self)
        self.date_timer.setInterval(60_000)
        self.date_timer.timeout.connect(self.update_today)
        self.date_timer.start()
        header.addWidget(self.date_label)
        appearance_toggle = QPushButton('···')
        appearance_toggle.setToolTip('管理窗口外观设置')
        appearance_toggle.setFixedSize(32, 32)
        header.addWidget(appearance_toggle)
        self.hide_button = QPushButton("隐藏")
        self.hide_button.setToolTip("隐藏到系统托盘")
        self.hide_button.clicked.connect(self.hide)
        self.hide_button.hide()
        header.addWidget(self.hide_button)
        self.close_button = QPushButton("×")
        self.close_button.setToolTip("关闭管理窗口")
        self.close_button.setFixedSize(32, 32)
        self.close_button.clicked.connect(self.close)
        header.addWidget(self.close_button)
        self.layout.addWidget(bar)

        self.body = QVBoxLayout()
        self.layout.addLayout(self.body, 1)
        self.appearance_panel = QWidget()
        controls = QHBoxLayout(self.appearance_panel)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(QLabel("管理窗口背景"))
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(30, 100)
        try:
            initial_opacity = int(storage.get_setting("opacity", "82")) if storage else 82
        except ValueError:
            initial_opacity = 82
        self.opacity.setValue(max(30, min(100, initial_opacity)))
        self.opacity.valueChanged.connect(self.apply_style)
        controls.addWidget(self.opacity, 1)
        self.opacity_label = QLabel(f"{self.opacity.value()}%")
        controls.addWidget(self.opacity_label)
        color_button = QPushButton("管理窗口颜色")
        color_button.clicked.connect(self.choose_color)
        controls.addWidget(color_button)
        self.on_top = QCheckBox("管理窗口置顶")
        self.on_top.toggled.connect(self.set_on_top)
        controls.addWidget(self.on_top)
        self.layout.addWidget(self.appearance_panel)
        self.appearance_panel.hide()
        appearance_toggle.clicked.connect(lambda: self.appearance_panel.setVisible(not self.appearance_panel.isVisible()))
        self.status = QLabel("普通窗口 · 拖动标题可移动")
        self.status.setWordWrap(True)
        self.layout.addWidget(self.status)
        self.status.hide()
        grip_line = QHBoxLayout()
        grip_line.addStretch()
        grip_line.addWidget(QSizeGrip(self))
        self.layout.addLayout(grip_line)
        self.tray = None
        self.apply_style()

    @staticmethod
    def today_text():
        locale = QLocale('zh_CN')
        return locale.toString(QDate.currentDate(), "yyyy年M月d日 dddd")

    def update_today(self):
        self.date_label.setText(self.today_text())

    def apply_style(self, *_):
        opacity = self.opacity.value()
        self.opacity_label.setText(f"{opacity}%")
        alpha = round(opacity * 255 / 100)
        light = self.color.lightness() > 180
        foreground = '#263b4b' if light else '#edf8f6'
        title_color = '#315d71' if light else '#b6efdf'
        field = '#f7f9fb' if light else '#263c46'
        field_text = '#263b4b' if light else '#edf8f6'
        field_border = '#d8e1e8' if light else '#46606a'
        highlight = '#dcebf0' if light else '#386c70'
        self.setStyleSheet(f"""
            QFrame#panel {{ background: rgba({self.color.red()}, {self.color.green()}, {self.color.blue()}, {alpha}); border: 1px solid rgba(220, 231, 236, 140); border-radius: 20px; }}
            QWidget {{ color: {foreground}; font-family: 'Microsoft YaHei UI'; font-size: 13px; }}
            QLabel#title {{ font-size: 22px; font-weight: 700; color: {title_color}; }}
            QLabel#pageTitle {{ font-size: 23px; font-weight: 700; color: {title_color}; }}
            QLabel#hint, QLabel#calendarWeekday {{ color: {title_color}; font-size: 11px; }}
            QLabel#calendarHeading {{ color: {title_color}; font-size: 16px; font-weight: 600; }}
            QPushButton {{ color: {field_text}; background: {field}; border: 1px solid {field_border}; border-radius: 9px; padding: 6px 10px; }}
            QPushButton:hover {{ background: {highlight}; }}
            QPushButton#addTask {{ color: white; background: #568ca4; border: none; border-radius: 11px; padding: 8px 14px; }}
            QPushButton#calendarCell {{ text-align: center; border: none; background: transparent; padding: 2px; }}
            QPushButton#calendarCell:hover, QPushButton#calendarSelected {{ background: {highlight}; border: none; padding: 2px; }}
            QLineEdit, QDateEdit, QTimeEdit, QListWidget, QTextEdit {{ background: {field}; color: {field_text}; border: 1px solid {field_border}; border-radius: 8px; padding: 7px; }}
            QListWidget#taskList {{ background: {field}; border: none; border-radius: 14px; padding: 8px; outline: none; }}
            QListWidget::item {{ padding: 3px 6px; border-radius: 5px; }}
            QListWidget::indicator {{ width: 14px; height: 14px; border: 1px solid #7c98a7; border-radius: 7px; }}
            QListWidget::indicator:checked {{ background: #4c91a8; border: 1px solid #4c91a8; }}
            QListWidget::item:selected {{ color: {field_text}; background: {highlight}; }}
            QTabBar::tab {{ color: {field_text}; background: transparent; padding: 7px 16px; border-radius: 7px; }}
            QTabBar::tab:selected {{ background: {highlight}; }}
            QTabWidget::pane {{ border: none; background: transparent; }}
        """)
        content = getattr(self, 'content', None)
        if content is not None:
            content.calendar.set_appearance('light' if light else 'dark', opacity)

    def choose_color(self):
        color = QColorDialog.getColor(self.color, self, "选择背景颜色")
        if color.isValid():
            self.color = color
            self.apply_style()

    def load_settings(self):
        if not self.storage:
            return
        try:
            opacity = int(self.storage.get_setting("opacity", "82"))
            width = int(self.storage.get_setting("width", "560"))
            height = int(self.storage.get_setting("height", "560"))
        except ValueError:
            opacity, width, height = 82, 560, 560
        color = QColor(self.storage.get_setting("editor_background_v2", "#f4f7f9"))
        self.color = color if color.isValid() else QColor("#f4f7f9")
        self.opacity.setValue(max(30, min(100, opacity)))
        self.resize(max(420, min(1600, width)), max(380, min(1200, height)))
        self.apply_style()

    def save_settings(self):
        if self.storage:
            try:
                self.storage.set_setting("opacity", self.opacity.value())
                self.storage.set_setting("editor_background_v2", self.color.name())
                self.storage.set_setting("width", self.width())
                self.storage.set_setting("height", self.height())
            except Exception as exc:
                self.status.setText(f"设置保存失败：{exc}")

    def set_on_top(self, enabled):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.show()  # Qt 改变窗口标志会隐藏窗口。

    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("DayNest")
        menu = QMenu(self)
        menu.addAction("显示 DayNest", self.show_window)
        menu.addAction("隐藏 DayNest", self.hide)
        menu.addAction("退出", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()
        self.hide_button.show()
        return True

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self.quitting = True
        if self.close():
            QApplication.quit()
        else:
            self.quitting = False

    def closeEvent(self, event):
        if self.quit_guard is not None and not self.quit_guard():
            event.ignore()
            return
        self.save_settings()
        self.closing.emit()
        event.accept()
