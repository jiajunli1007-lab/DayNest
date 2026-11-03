import sys
import unittest
from daynest.desktop_probe import inspect_desktop


class DesktopProbeTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32', 'Windows only')
    def test_read_only_probe_returns_structure(self):
        result = inspect_desktop()
        self.assertIn('shell_hwnd', result)
        self.assertIsInstance(result['windows'], list)
        self.assertTrue(all(item['class'] in {'Progman', 'WorkerW', 'SHELLDLL_DefView'} for item in result['windows']))
