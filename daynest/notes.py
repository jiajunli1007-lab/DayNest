"""按日期记录便签，输入停止后自动保存。"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget


class NotePane(QWidget):
    def __init__(self, storage, date):
        super().__init__()
        self.storage = storage
        self.date = date
        self.dirty = False
        layout = QVBoxLayout(self)
        self.label = QLabel()
        layout.addWidget(self.label)
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("记录这一刻……")
        layout.addWidget(self.editor, 1)
        save = QPushButton("保存便签")
        save.clicked.connect(self.flush)
        layout.addWidget(save)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self.flush)
        self.editor.textChanged.connect(self.changed)
        self.load(date)

    def load(self, date):
        if not self.flush():
            return False
        self.date = date
        self.label.setText(f"{date} 的便签")
        self.editor.blockSignals(True)
        try:
            self.editor.setPlainText(self.storage.get_note(date))
        finally:
            self.editor.blockSignals(False)
        self.dirty = False
        return True

    def changed(self):
        self.dirty = True
        self.timer.start()

    def flush(self):
        self.timer.stop()
        if not self.dirty:
            return True
        try:
            self.storage.save_note(self.date, self.editor.toPlainText())
        except Exception as exc:
            QMessageBox.critical(self, "便签保存失败", str(exc))
            return False
        self.dirty = False
        return True
