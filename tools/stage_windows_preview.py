"""整理待审查的 Windows 预览版附件；不会创建或发布 GitHub Release。"""

import argparse
import hashlib
import shutil
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile

from tools.prepare_qt_materials import SOURCES
from tools.prepare_windows_candidate import VC_RUNTIME_NAMES


INSTALL_INFO = """DayNest Windows 预览版

1. 解压整个压缩包，打开 DayNest 文件夹，双击 DayNest.exe。
2. 请将 _internal 文件夹与 DayNest.exe 放在一起，不要只移动 exe。
3. 通过桌面组件的菜单调整尺寸、透明度和窗口模式。

本版本为 Windows x64 预览版，不需要另外安装 Python。本地测试使用 Windows 11；
不同设备的兼容性尚需验证。程序未签名，Windows 可能显示安全提示。
数据保存在当前用户的本地应用数据目录；可在程序中备份与恢复。
提醒仅在程序运行时检查。窗口靠后模式不是 Windows 真正的壁纸层。

DayNest 代码采用 MIT 许可证；本包中 Qt、PySide6、Python、微软运行库和
其他组件分别适用各自的许可，见 licenses 目录。Qt 和 PySide6 对应源码材料
应与此预览包一同提供；使用者可按 QT_REPLACEMENT.md 的说明更换兼容的库。
使用附带的微软运行库前，请阅读并同意适用于该组件的许可：
https://aka.ms/VCRedistLicense
"""

SOURCE_INFO = """Qt 6.12.0 / PySide6 6.12.0 官方源码材料

sources 目录中是 Qt 官方发布的原始源码压缩包，SHA256SUMS.txt 列出其校验值。
包含 qtbase、qtdeclarative、qtimageformats、qtshadertools、qtsvg 和 PySide6。
源码与所用二进制版本相同，但尚未独立复现上游二进制构建。
Qt 的其他第三方许可及归属信息见 DayNest 程序包内的 licenses 目录。
构建说明：https://doc.qt.io/qtforpython-6/building_from_source/index.html
"""

PUBLIC_QT_GUIDE = """# Qt 和 PySide6 源码与更换说明

本程序使用动态链接的 Qt 6.12.0、PySide6 6.12.0 和 Shiboken 6.12.0。
许可证和第三方组件声明位于 licenses 文件夹，DayNest 自身代码采用 MIT 许可。
同一发布页面的 Qt 源码附件提供官方 6.12.0 源码和 SHA-256 校验值。

如需更换 Qt 或 PySide6：

1. 退出 DayNest 并复制整个程序文件夹；建议在程序内另外备份个人数据。
2. 使用源码、Windows x64 和兼容工具链构建同一版本的共享库；必要时同时
   构建相匹配的 PySide6、Shiboken 和插件。官方说明：
   https://doc.qt.io/qt-6/windows-building.html
   https://doc.qt.io/qtforpython-6/building_from_source/windows.html
3. 在副本中替换 _internal/PySide6 下同名 DLL，或替换其 plugins 子目录中的
   插件及 _internal/shiboken6 中匹配的文件，然后启动检查。

已有测试使用不同的 Qt 官方 6.12.0 Qt6Core.dll 成功启动；自行修改源码后的
完整重建尚未独立验证。Qt 6.12.1 开发快照曾因私有接口不兼容而启动失败，
因此不能假设不同补丁版本的库可直接混用。LGPL 所授予的权利不受本说明限制。
"""


def check_names(archive):
    """拒绝重复、绝对和目录穿越路径。"""
    names = archive.namelist()
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("ZIP 包含重复路径")
    for name in names:
        path = PurePosixPath(name)
        if (path.is_absolute() or not path.parts or "\\" in name or
                any(part in (".", "..") or ":" in part for part in path.parts)):
            raise ValueError("ZIP 包含不安全路径")
    bad = archive.testzip()
    if bad:
        raise ValueError(f"ZIP 已损坏：{bad}")


def check_sources(archive):
    """核对源码归档本身，而不是只相信 ZIP 中的清单。"""
    check_names(archive)
    for name, expected in SOURCES.items():
        try:
            with archive.open("sources/" + name) as source:
                actual = hashlib.file_digest(source, "sha256").hexdigest()
        except KeyError as exc:
            raise ValueError(f"源码归档缺少文件：{name}") from exc
        if actual != expected:
            raise ValueError(f"源码校验失败：{name}")


def check_candidate(archive):
    check_names(archive)
    names = set(archive.namelist())
    required = {
        "DayNest/DayNest.exe",
        "DayNest/licenses/LGPL-3.0-only.txt",
        "DayNest/licenses/Microsoft-VC-Runtime-2026.txt",
        "DayNest/licenses/VC-Runtime-SHA256.txt",
        "DayNest/licenses/Qt-upstream/SHA256SUMS.txt",
    }
    if not required.issubset(names):
        raise ValueError("候选包缺少程序或许可资料")
    expected_sources = "".join(f"{h}  {n}\n" for n, h in SOURCES.items())
    if archive.read("DayNest/licenses/Qt-upstream/SHA256SUMS.txt").decode("utf-8") != expected_sources:
        raise ValueError("候选包的 Qt 许可清单与源码不匹配")
    manifest = archive.read("DayNest/licenses/VC-Runtime-SHA256.txt").decode("utf-8")
    try:
        runtime_hashes = dict(line.split("  ", 1)[::-1] for line in manifest.splitlines())
    except ValueError as exc:
        raise ValueError("微软运行库清单格式错误") from exc
    if set(runtime_hashes) != VC_RUNTIME_NAMES:
        raise ValueError("微软运行库清单不完整")
    seen = set()
    for name in names:
        basename = PurePosixPath(name).name.lower()
        if basename in VC_RUNTIME_NAMES:
            seen.add(basename)
            with archive.open(name) as runtime:
                digest = hashlib.file_digest(runtime, "sha256").hexdigest()
            if digest != runtime_hashes[basename]:
                raise ValueError(f"微软运行库校验失败：{name}")
    if seen != VC_RUNTIME_NAMES:
        raise ValueError("候选包缺少微软运行库")
    if any(name.lower().endswith((".db", ".sqlite", ".sqlite3")) for name in names):
        raise ValueError("候选包包含数据库，停止处理")


def copy_entry(source, target, name):
    with source.open(name) as src, target.open(name, "w") as dst:
        shutil.copyfileobj(src, dst)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--qt-sources", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--release-preview", action="store_true", help="生成面向下载者命名的预览版文件")
    args = parser.parse_args()
    output = args.output_dir
    app_name = "DayNest-Windows-x64-preview.zip" if args.release_preview else "DayNest-Windows-x64-preview-待审核.zip"
    source_name = "DayNest-Qt-6.12.0-sources.zip" if args.release_preview else "DayNest-Qt-6.12.0-sources-待审核.zip"
    app_zip = output / app_name
    source_zip = output / source_name
    if not output.is_dir() or app_zip.exists() or source_zip.exists():
        parser.error("输出目录不存在，或输出文件已经存在")
    try:
        with ZipFile(args.candidate) as candidate, ZipFile(args.qt_sources) as sources:
            check_candidate(candidate)
            check_sources(sources)
            with ZipFile(app_zip, "x", compression=ZIP_DEFLATED, compresslevel=6) as out:
                for name in candidate.namelist():
                    excluded = {"DayNest/内部测试说明.txt", "DayNest/WINDOWS_RELEASE.md", "DayNest/使用说明.txt"}
                    if args.release_preview:
                        excluded.add("DayNest/QT_REPLACEMENT.md")
                    if name not in excluded:
                        copy_entry(candidate, out, name)
                out.writestr("DayNest/使用说明.txt", INSTALL_INFO)
                if args.release_preview:
                    out.writestr("DayNest/QT_REPLACEMENT.md", PUBLIC_QT_GUIDE)
            with ZipFile(source_zip, "x", compression=ZIP_STORED, allowZip64=True) as out:
                out.writestr("说明.txt", SOURCE_INFO)
                out.writestr("SHA256SUMS.txt", "".join(f"{h}  {n}\n" for n, h in SOURCES.items()))
                for name in SOURCES:
                    copy_entry(sources, out, "sources/" + name)
    except (BadZipFile, OSError, ValueError) as exc:
        parser.error(str(exc))
    print("预览版附件已整理，仍需完成发布审核：", app_zip, source_zip)


if __name__ == "__main__":
    main()
