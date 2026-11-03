import tempfile
import unittest
from pathlib import Path
from tools.build_windows import remove_unused_virtual_keyboard


class BuildTest(unittest.TestCase):
    def test_excludes_only_unused_virtual_keyboard(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            bundle = Path(directory)
            qt = bundle / '_internal' / 'PySide6'
            plugin = qt / 'plugins' / 'platforminputcontexts' / 'qtvirtualkeyboardplugin.dll'
            plugin.parent.mkdir(parents=True)
            plugin.write_bytes(b'test')
            library = qt / 'Qt6VirtualKeyboard.dll'
            library.write_bytes(b'test')
            other = qt / 'Qt6Core.dll'
            other.write_bytes(b'test')
            remove_unused_virtual_keyboard(bundle)
            self.assertFalse(plugin.exists())
            self.assertFalse(library.exists())
            self.assertEqual(other.read_bytes(), b'test')
