"""在项目内的全新目录构建 Windows 测试包，不覆盖旧构建。"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def remove_unused_virtual_keyboard(bundle):
    """仅移除本次新构建中未使用的虚拟键盘插件及其库。"""
    pyside = bundle / '_internal' / 'PySide6'
    for relative in ('Qt6VirtualKeyboard.dll', 'plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll'):
        path = pyside / relative
        if path.is_file():
            path.unlink()


def main():
    if sys.platform != 'win32':
        raise SystemExit('请在 Windows 上构建 Windows 版本。')
    root = Path(__file__).absolute().parent.parent
    if Path(sys.prefix) != root / '.venv-diagnostic':
        raise SystemExit('请使用项目 .venv-diagnostic 解释器构建。')
    work_root = root / '.build-tmp'
    work_root.mkdir(exist_ok=True)
    build = Path(tempfile.mkdtemp(prefix='build-', dir=work_root))
    temporary = build / 'temp'
    temporary.mkdir()
    env = os.environ.copy()
    for key in ('TEMP', 'TMP', 'TMPDIR'):
        env[key] = str(temporary)
    env['PYINSTALLER_CONFIG_DIR'] = str(build / 'cache')
    # 避免分析时从外部开发工具的 PATH 收集到同名但 ABI 不兼容的 DLL。
    # 这只改变构建子进程的 PATH，不改系统或当前终端的环境变量。
    windows = Path(env.get('SystemRoot', r'C:\Windows'))
    env['PATH'] = os.pathsep.join([str(windows / 'System32'), str(windows),
                                   str(Path(sys.executable).parent), str(Path(sys.base_prefix))])
    command = [sys.executable, '-I', '-B', '-m', 'PyInstaller', '--noconfirm',
               '--onedir', '--windowed', '--name', 'DayNest',
               '--distpath', str(build / 'dist'), '--workpath', str(build / 'work'),
               '--specpath', str(build / 'spec'), str(root / 'run_daynest.py')]
    print('构建目录：', build, flush=True)
    result = subprocess.run(command, cwd=root, env=env)
    if result.returncode == 0:
        unexpected_icu = build / 'dist' / 'DayNest' / '_internal' / 'icuuc.dll'
        if unexpected_icu.exists():
            print('构建意外收集了 icuuc.dll，已停止交付；请检查 DLL 来源。', file=sys.stderr)
            return 1
        remove_unused_virtual_keyboard(build / 'dist' / 'DayNest')
        print('测试包：', build / 'dist' / 'DayNest', flush=True)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
