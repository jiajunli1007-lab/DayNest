import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class StartupTest(unittest.TestCase):
    def test_complete_app_starts_and_exits(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            command = [sys.executable, '-B', '-m', 'daynest', '--data-dir', directory,
                       '--smoke-test', '-platform', 'offscreen']
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(directory) / 'daynest.sqlite3').is_file())
