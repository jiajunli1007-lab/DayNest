"""生成供本机验证的 Windows 候选 ZIP；它不是已审核的公开发布包。"""

import argparse
import hashlib
import json
import os
import posixpath
import sys
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from tools.prepare_qt_materials import SOURCES

VC_RUNTIME_NAMES = frozenset({
    "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
    "vcruntime140.dll", "vcruntime140_1.dll",
})


def select_vc_runtimes(bundle, runtime_dir):
    """检查并选择统一的运行库；不修改原始构建目录。"""
    selected = {}
    present = set()
    for path in bundle.rglob("*"):
        name = path.name.lower()
        if path.is_file() and name in VC_RUNTIME_NAMES:
            replacement = runtime_dir / name
            if not replacement.is_file():
                raise ValueError(f"微软运行库缺少文件：{name}")
            selected[path] = replacement
            present.add(name)
    missing = VC_RUNTIME_NAMES - present
    if missing:
        raise ValueError("构建目录缺少预期运行库：" + ", ".join(sorted(missing)))
    return selected


def is_unused_pdf_component(relative_path):
    """应用不读取 PDF；避免自动收集的 PDF 插件扩大候选包范围。"""
    return relative_path.as_posix() in {
        "_internal/PySide6/Qt6Pdf.dll",
        "_internal/PySide6/plugins/imageformats/qpdf.dll",
    }


def validate_qt_notices(path):
    """拒绝缺少上游许可引用、路径不安全或损坏的资料包。"""
    with ZipFile(path) as notices:
        names = notices.namelist()
        if len(names) != len(set(names)) or notices.testzip():
            raise ValueError("Qt 许可资料有重复文件或损坏")
        expected = "".join(f"{digest}  {name}\n" for name, digest in SOURCES.items())
        if notices.read("SHA256SUMS.txt").decode("utf-8") != expected:
            raise ValueError("Qt 许可资料的源码校验记录不匹配")
        present = set(names)
        attributions = 0
        for name in names:
            entry = PurePosixPath(name)
            if (entry.is_absolute() or not entry.parts or
                    any(part in ("", ".", "..") or ":" in part or "\\" in part
                        for part in entry.parts)):
                raise ValueError("Qt 许可资料包含不安全路径")
            if name.endswith("/qt_attribution.json"):
                attributions += 1
                data = json.loads(notices.read(name), strict=False)
                for item in data if isinstance(data, list) else [data]:
                    ref = item.get("LicenseFile")
                    if ref and (not isinstance(ref, str) or
                                posixpath.normpath(posixpath.join(posixpath.dirname(name), ref)) not in present):
                        raise ValueError(f"Qt 许可引用缺失：{name}")
        if not attributions:
            raise ValueError("Qt 许可资料缺少上游归属信息")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True, help="构建后的 DayNest 目录")
    parser.add_argument("--output", type=Path, required=True, help="新 ZIP 路径；不得已存在")
    parser.add_argument("--qt-notices", type=Path, required=True, help="已整理的 Qt 许可资料 ZIP")
    parser.add_argument("--vc-runtime-dir", type=Path, help="包含微软原版 x64 运行库的目录")
    args = parser.parse_args()
    # AppContainer 可能无法查询真实路径；abspath 只规范化路径文本。
    root = Path(os.path.abspath(__file__)).parent.parent
    bundle = Path(os.path.abspath(args.bundle))
    output = Path(os.path.abspath(args.output))
    if not (bundle / "DayNest.exe").is_file() or not (bundle / "_internal").is_dir():
        parser.error("bundle 必须包含 DayNest.exe 和 _internal 目录")
    if bundle == output or bundle in output.parents:
        parser.error("输出 ZIP 不能位于输入目录内")
    if not output.parent.is_dir():
        parser.error("输出目录不存在")

    licenses = {
        "DayNest-MIT.txt": root / "LICENSE",
        "Python-LICENSE.txt": Path(sys.base_prefix) / "LICENSE.txt",
        "Python-Windows-CRT.txt": root / "docs/licenses/Python-Windows-CRT.txt",
        "Microsoft-VC-Runtime-2026.txt": root / "docs/licenses/Microsoft-VC-Runtime-2026.txt",
        "OpenSSL-3.5.9-LICENSE.txt": root / "docs/licenses/OpenSSL-3.5.9-LICENSE.txt",
        "Qt-Mesa-llvmpipe.txt": root / "docs/licenses/Qt-Mesa-llvmpipe.txt",
        "Qt-LLVM.txt": root / "docs/licenses/Qt-LLVM.txt",
        "PyInstaller-COPYING.txt": Path(sys.prefix) / "Lib/site-packages/pyinstaller-6.22.3.dist-info/licenses/COPYING.txt",
        "LGPL-3.0-only.txt": root / "docs/licenses/LGPL-3.0-only.txt",
        "GPL-3.0-only.txt": root / "docs/licenses/GPL-3.0-only.txt",
    }
    missing = [str(path) for path in licenses.values() if not path.is_file()]
    if missing:
        parser.error("缺少许可材料：" + ", ".join(missing))
    try:
        validate_qt_notices(args.qt_notices)
    except (BadZipFile, OSError, KeyError, ValueError) as exc:
        parser.error(f"Qt 许可材料无法通过检查：{exc}")
    try:
        runtimes = select_vc_runtimes(bundle, args.vc_runtime_dir) if args.vc_runtime_dir else {}
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    instructions = """DayNest Windows 内部候选包

本包仅供项目维护者在本机测试，尚未完成全部第三方许可和干净电脑验收，请勿公开分发。
解压整个 ZIP，打开 DayNest 文件夹，双击 DayNest.exe。不要单独移动 exe。
数据默认保存在当前 Windows 用户的本地应用数据目录，测试前请备份现有数据。
托盘、快捷键、提醒、多屏缩放与 Windows 不同版本的行为仍需真实桌面验证。
本包未签名，也不是安装程序。更多信息见包内 WINDOWS_RELEASE.md。
"""
    # x 模式保护已有文件；只读取构建目录，保留原始构建和以往测试包。
    with ZipFile(output, "x", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(bundle.rglob("*")):
            relative = path.relative_to(bundle)
            if path.is_file() and not is_unused_pdf_component(relative):
                archive.write(runtimes.get(path, path), Path("DayNest") / relative)
        archive.writestr("DayNest/内部测试说明.txt", instructions)
        archive.write(root / "docs/WINDOWS_RELEASE.md", "DayNest/WINDOWS_RELEASE.md")
        archive.write(root / "docs/QT_REPLACEMENT.md", "DayNest/QT_REPLACEMENT.md")
        for name, path in licenses.items():
            archive.write(path, "DayNest/licenses/" + name)
        if runtimes:
            unique = {path.name.lower(): path for path in runtimes.values()}
            hashes = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}\n"
                             for name, path in sorted(unique.items()))
            archive.writestr("DayNest/licenses/VC-Runtime-SHA256.txt", hashes)
        with ZipFile(args.qt_notices) as notices:
            for name in notices.namelist():
                archive.writestr("DayNest/licenses/Qt-upstream/" + name, notices.read(name))
    print("已创建内部候选包：", output)


if __name__ == "__main__":
    main()
