import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from tools.audit_preview_wheels import check_wheel


class PreviewWheelAuditTest(unittest.TestCase):
    def test_detects_changed_qt_binary(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            package_path = root / 'package.zip'
            wheel_path = root / 'wheel.zip'
            with ZipFile(package_path, 'w') as package:
                package.writestr('DayNest/_internal/PySide6/Qt6Core.dll', b'changed')
            with ZipFile(wheel_path, 'w') as wheel:
                wheel.writestr('PySide6/Qt6Core.dll', b'original')
            with ZipFile(package_path) as package, ZipFile(wheel_path) as wheel:
                with self.assertRaisesRegex(ValueError, '不一致'):
                    check_wheel(package, wheel, 'PySide6')

    def test_requires_upstream_binary(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            package_path = root / 'package.zip'
            wheel_path = root / 'wheel.zip'
            with ZipFile(package_path, 'w') as package:
                package.writestr('DayNest/_internal/shiboken6/shiboken6.pyd', b'data')
            with ZipFile(wheel_path, 'w'):
                pass
            with ZipFile(package_path) as package, ZipFile(wheel_path) as wheel:
                with self.assertRaisesRegex(ValueError, '官方 wheel 中缺少'):
                    check_wheel(package, wheel, 'shiboken6')
