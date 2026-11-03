import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from tools.build_windows import remove_unused_virtual_keyboard
from tools.prepare_qt_materials import SOURCES
from tools.prepare_windows_candidate import validate_qt_notices


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

    def test_qt_notice_check_requires_referenced_license(self):
        manifest = ''.join(f'{digest}  {name}\n' for name, digest in SOURCES.items())
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / 'notices.zip'
            with ZipFile(path, 'w') as archive:
                archive.writestr('SHA256SUMS.txt', manifest)
                archive.writestr('upstream/component/qt_attribution.json', '{"LicenseFile":"LICENSE"}')
            with self.assertRaisesRegex(ValueError, '许可引用缺失'):
                validate_qt_notices(path)
            with ZipFile(path, 'a') as archive:
                archive.writestr('upstream/component/LICENSE', 'license text')
            validate_qt_notices(path)

    def test_qt_notice_check_rejects_traversal_paths(self):
        manifest = ''.join(f'{digest}  {name}\n' for name, digest in SOURCES.items())
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / 'notices.zip'
            with ZipFile(path, 'w') as archive:
                archive.writestr('SHA256SUMS.txt', manifest)
                archive.writestr('upstream/component/qt_attribution.json', '{}')
                archive.writestr('../outside.txt', 'unsafe')
            with self.assertRaisesRegex(ValueError, '不安全路径'):
                validate_qt_notices(path)
