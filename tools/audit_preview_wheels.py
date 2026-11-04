"""校验预览包所含 Qt / Shiboken 文件与 PyPI 官方 wheel 是否一致。"""

import argparse
import hashlib
import re
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from tools.stage_windows_preview import check_candidate, check_sources


WHEELS = {
    "pyside6_essentials-6.12.0-cp310-abi3-win_amd64.whl": "c9a95102aa23c1f86516a30d5a9be37552d324eee7e567eb7508973f1218cb42",
    "shiboken6-6.12.0-cp310-abi3-win_amd64.whl": "a1906cb8116869178c64b6bab52623bbc8b4ceed7b30bfc3c9aa0f6e67f6438e",
}


def check_release_guides(package):
    names = set(package.namelist())
    required = {"DayNest/使用说明.txt", "DayNest/QT_REPLACEMENT.md"}
    internal = {"DayNest/内部测试说明.txt", "DayNest/WINDOWS_RELEASE.md"}
    if not required.issubset(names) or names.intersection(internal):
        raise ValueError("公开预览包缺少使用说明或包含内部审核文件")


def check_sensitive_patterns(package):
    """检查少数可识别的泄露模式；通过不代表证明没有其他敏感内容。"""
    patterns = (
        re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{128,}\s+-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    )
    for name in package.namelist():
        if name.endswith("/"):
            continue
        data = package.read(name)
        if any(pattern.search(data) for pattern in patterns):
            raise ValueError(f"程序包包含需要人工审查的敏感信息模式：{name}")


def check_wheel(package, wheel, folder):
    """检查指定组件的每个二进制；微软运行库由候选包清单单独验证。"""
    prefix = "DayNest/_internal/" + folder + "/"
    files = [name for name in package.namelist()
             if name.startswith(prefix) and name.lower().endswith((".dll", ".pyd"))
             and not PurePosixPath(name).name.lower().startswith(("msvcp", "vcruntime"))]
    if not files:
        raise ValueError(f"程序包缺少 {folder} 二进制文件")
    available = set(wheel.namelist())
    for name in files:
        original = name[len("DayNest/_internal/"):]
        if original not in available:
            raise ValueError(f"官方 wheel 中缺少文件：{original}")
        with package.open(name) as bundled, wheel.open(original) as upstream:
            if hashlib.file_digest(bundled, "sha256").digest() != hashlib.file_digest(upstream, "sha256").digest():
                raise ValueError(f"二进制与官方 wheel 不一致：{original}")
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--qt-sources", type=Path, required=True)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--release-preview", action="store_true")
    args = parser.parse_args()
    try:
        for name, expected in WHEELS.items():
            with (args.wheel_dir / name).open("rb") as source:
                actual = hashlib.file_digest(source, "sha256").hexdigest()
            if actual != expected:
                raise ValueError(f"官方 wheel SHA-256 不匹配：{name}")
        with (ZipFile(args.package) as package, ZipFile(args.qt_sources) as sources,
              ZipFile(args.wheel_dir / next(iter(WHEELS))) as pyside,
              ZipFile(args.wheel_dir / next(reversed(WHEELS))) as shiboken):
            check_candidate(package)
            check_sources(sources)
            if args.release_preview:
                check_release_guides(package)
                check_sensitive_patterns(package)
            pyside_count = check_wheel(package, pyside, "PySide6")
            shiboken_count = check_wheel(package, shiboken, "shiboken6")
    except (BadZipFile, OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"官方 wheel 对比通过：PySide6 {pyside_count} 个文件，Shiboken {shiboken_count} 个文件。")
    print("Qt 源码归档及候选包运行库清单校验通过；尚未独立复现 Qt 源码构建。")


if __name__ == "__main__":
    main()
