import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from tools.prepare_qt_materials import SOURCES
from tools.prepare_windows_candidate import VC_RUNTIME_NAMES
from tools.stage_windows_preview import check_candidate, check_names, check_sources, main


class PreviewStagingTest(unittest.TestCase):
    def test_public_preview_omits_internal_notices_and_keeps_source(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            candidate = root / 'candidate.zip'
            source = root / 'sources.zip'
            output = root / 'output'
            output.mkdir()
            runtime = b'official runtime'
            digest = hashlib.sha256(runtime).hexdigest()
            qt = b'official source'
            source_hashes = {'qt.tar.xz': hashlib.sha256(qt).hexdigest()}
            with ZipFile(candidate, 'w') as archive:
                archive.writestr('DayNest/DayNest.exe', b'executable')
                archive.writestr('DayNest/内部测试说明.txt', b'internal')
                archive.writestr('DayNest/WINDOWS_RELEASE.md', b'internal')
                archive.writestr('DayNest/QT_REPLACEMENT.md', b'internal')
                archive.writestr('DayNest/licenses/LGPL-3.0-only.txt', b'license')
                archive.writestr('DayNest/licenses/Microsoft-VC-Runtime-2026.txt', b'notice')
                archive.writestr('DayNest/licenses/Qt-upstream/SHA256SUMS.txt',
                                 ''.join(f'{h}  {n}\n' for n, h in source_hashes.items()))
                archive.writestr('DayNest/licenses/VC-Runtime-SHA256.txt',
                                 ''.join(f'{digest}  {name}\n' for name in sorted(VC_RUNTIME_NAMES)))
                for name in VC_RUNTIME_NAMES:
                    archive.writestr('DayNest/_internal/' + name, runtime)
            with ZipFile(source, 'w') as archive:
                archive.writestr('sources/qt.tar.xz', qt)
            args = ['stage', '--candidate', str(candidate), '--qt-sources', str(source),
                    '--output-dir', str(output), '--release-preview']
            with patch('tools.stage_windows_preview.SOURCES', source_hashes), patch('sys.argv', args):
                main()
            with ZipFile(output / 'DayNest-Windows-x64-preview.zip') as archive:
                names = archive.namelist()
                self.assertNotIn('DayNest/内部测试说明.txt', names)
                self.assertNotIn('DayNest/WINDOWS_RELEASE.md', names)
                self.assertEqual(names.count('DayNest/QT_REPLACEMENT.md'), 1)
                self.assertIn('DayNest/使用说明.txt', names)
            with ZipFile(output / 'DayNest-Qt-6.12.0-sources.zip') as archive:
                self.assertEqual(archive.read('sources/qt.tar.xz'), qt)

    def test_source_check_detects_tampering(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / 'sources.zip'
            with ZipFile(path, 'w') as archive:
                archive.writestr('sources/qt.tar.xz', b'tampered')
            with patch('tools.stage_windows_preview.SOURCES', {'qt.tar.xz': hashlib.sha256(b'original').hexdigest()}):
                with ZipFile(path) as archive, self.assertRaisesRegex(ValueError, '源码校验失败'):
                    check_sources(archive)

    def test_candidate_rejects_modified_runtime(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / 'candidate.zip'
            content = b'original'
            digest = hashlib.sha256(content).hexdigest()
            with ZipFile(path, 'w') as archive:
                archive.writestr('DayNest/DayNest.exe', b'exe')
                archive.writestr('DayNest/licenses/LGPL-3.0-only.txt', b'license')
                archive.writestr('DayNest/licenses/Microsoft-VC-Runtime-2026.txt', b'notice')
                archive.writestr('DayNest/licenses/Qt-upstream/SHA256SUMS.txt',
                                 ''.join(f'{h}  {n}\n' for n, h in SOURCES.items()))
                archive.writestr('DayNest/licenses/VC-Runtime-SHA256.txt',
                                 ''.join(f'{digest}  {name}\n' for name in sorted(VC_RUNTIME_NAMES)))
                for name in VC_RUNTIME_NAMES:
                    archive.writestr('DayNest/_internal/' + name,
                                     b'modified' if name == 'msvcp140.dll' else content)
            with ZipFile(path) as archive, self.assertRaisesRegex(ValueError, '运行库校验失败'):
                check_candidate(archive)

    def test_archive_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / 'unsafe.zip'
            with ZipFile(path, 'w') as archive:
                archive.writestr('../outside.txt', b'data')
            with ZipFile(path) as archive, self.assertRaisesRegex(ValueError, '不安全路径'):
                check_names(archive)
