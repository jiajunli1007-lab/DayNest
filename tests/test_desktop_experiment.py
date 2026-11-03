import unittest
import subprocess
import sys
from experiments.desktop_layer import select_host


class HostSelectionTest(unittest.TestCase):
    def test_requires_one_sibling_worker_and_icon_view(self):
        snapshot = {'shell_hwnd': 1, 'windows': [
            {'class': 'SHELLDLL_DefView', 'hwnd': 2, 'parent': 1},
            {'class': 'WorkerW', 'hwnd': 3, 'parent': 1},
            {'class': 'WorkerW', 'hwnd': 4, 'parent': 0}]}
        self.assertEqual(select_host(snapshot), 3)
        snapshot['windows'].append({'class': 'WorkerW', 'hwnd': 5, 'parent': 1})
        self.assertIsNone(select_host(snapshot))
        snapshot['windows'].pop()
        snapshot['windows'].pop(0)
        self.assertIsNone(select_host(snapshot))

    @unittest.skipUnless(sys.platform == 'win32', 'Windows only')
    def test_same_process_window_parent_is_restored(self):
        code = '''from PySide6.QtWidgets import QApplication, QWidget
from experiments.desktop_layer import attach_experiment
app=QApplication(["test", "-platform", "windows"])
host=QWidget(); host.show(); app.processEvents()
result=attach_experiment(int(host.winId()), 100)
host.close()
raise SystemExit(result)
'''
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('测试窗口恢复检查通过', result.stdout)
