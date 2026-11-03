"""整理经校验的 Qt 源码和上游许可资料，供发布审查。"""

import argparse
import hashlib
import json
import posixpath
import tarfile
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile


# 官方发布服务器提供的 SHA-256；不接受版本相同但校验值不同的文件。
SOURCES = {
    "pyside-setup-everywhere-src-6.12.0.tar.xz": "099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751",
    "qtbase-everywhere-src-6.12.0.tar.xz": "a951bd163c7b80fc6b8c88d7668fb56abf91c152373e13c10666763238131307",
    "qtdeclarative-everywhere-src-6.12.0.tar.xz": "311f3a2603e1973bb59baef9dfa740a376de713157d4782ee043681e889c9260",
    "qtimageformats-everywhere-src-6.12.0.tar.xz": "0943132b5db8de6b6a7f1d162682173e8763c7ed94e80fd39113292845f67762",
    "qtsvg-everywhere-src-6.12.0.tar.xz": "e4ab39534ec97987b1b9b60ef7f4d3253d5912a69f8c713a01753174a4029331",
}


def verify_sources(source_dir):
    for name, expected in SOURCES.items():
        path = source_dir / name
        if not path.is_file():
            raise ValueError(f"缺少源码：{name}")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"源码 SHA-256 不匹配：{name}")


def is_notice(path):
    name = path.name.casefold()
    return (name == "qt_attribution.json" or "LICENSES" in path.parts
            or name.startswith(("license", "licence", "copying", "copyright", "notice")))


def valid_relative(path):
    return not path.is_absolute() and all(part not in ("", ".", "..") and ":" not in part
                                           and "\\" not in part for part in path.parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True, help="官方源码归档所在目录")
    parser.add_argument("--output-dir", type=Path, required=True, help="存放新生成 ZIP 的目录")
    args = parser.parse_args()
    if not args.output_dir.is_dir():
        parser.error("输出目录不存在")
    sources_zip = args.output_dir / "DayNest-Qt源码材料-v2-待审核.zip"
    notices_zip = args.output_dir / "DayNest-Qt许可资料-v2-待审核.zip"
    if sources_zip.exists() or notices_zip.exists():
        parser.error("输出文件已存在，停止以保护原有文件")
    verify_sources(args.source_dir)
    manifest = "".join(f"{digest}  {name}\n" for name, digest in SOURCES.items())
    info = ("Qt 6.12.0 与 PySide6 6.12.0 官方源码及 SHA-256 校验记录。\n"
            "材料供内部发布审核；是否完全对应二进制构建及分发义务仍需核实。\n")
    # 上游源码已经压缩，直接存储避免重复耗时压缩。
    with ZipFile(sources_zip, "x", compression=ZIP_STORED, allowZip64=True) as archive:
        archive.writestr("说明.txt", info)
        archive.writestr("SHA256SUMS.txt", manifest)
        for name in SOURCES:
            archive.write(args.source_dir / name, "sources/" + name)

    count = 0
    attributions = 0
    with ZipFile(notices_zip, "x", compression=ZIP_DEFLATED) as archive:
        archive.writestr("说明.txt", info + "保留上游许可、版权及 qt_attribution.json 文件；可能包含未使用组件。\n")
        archive.writestr("SHA256SUMS.txt", manifest)
        for name in SOURCES:
            collected = {}
            references = set()
            with tarfile.open(args.source_dir / name, "r:xz") as tar:
                for member in tar:
                    path = PurePosixPath(member.name)
                    if not member.isfile() or not valid_relative(path) or not is_notice(path):
                        continue
                    content = tar.extractfile(member).read()
                    if path.name == "qt_attribution.json":
                        # 检查资料可解析，但保留上游原文，避免更改版权声明。
                        entries = json.loads(content, strict=False)
                        for entry in entries if isinstance(entries, list) else [entries]:
                            ref = entry.get("LicenseFile")
                            if ref:
                                if not isinstance(ref, str):
                                    raise ValueError(f"无法识别许可文件引用：{path}")
                                target = PurePosixPath(posixpath.normpath(posixpath.join(str(path.parent), ref)))
                                if not valid_relative(target) or target.parts[0] != path.parts[0]:
                                    raise ValueError(f"许可文件引用超出源码目录：{path}")
                                references.add(target.as_posix())
                        attributions += 1
                    collected[path.as_posix()] = content
            missing = references - collected.keys()
            if missing:
                # 部分被引用的许可文件名称不以 LICENSE 开头，单独补齐。
                with tarfile.open(args.source_dir / name, "r:xz") as tar:
                    for member in tar:
                        if member.isfile() and member.name in missing:
                            collected[member.name] = tar.extractfile(member).read()
                missing = references - collected.keys()
                if missing:
                    raise ValueError(f"源码中的许可引用未找到：{sorted(missing)}")
            for path, content in collected.items():
                archive.writestr("upstream/" + path, content)
                count += 1
    print(f"源码材料：{sources_zip}；上游许可资料：{notices_zip}；文件 {count}，归属信息 {attributions}")


if __name__ == "__main__":
    main()
