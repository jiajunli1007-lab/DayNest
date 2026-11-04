# Windows 发布准备记录

当前状态：**内部候选包，不可作为公开发布包**。本文件记录已经取得的证据和仍需完成的工作，不构成许可证符合性结论。

## 构建和验证

- 使用项目内 `.venv-diagnostic` 中的 Python 3.15.0、PySide6 6.12.0 和 PyInstaller 6.22.3，在 Windows 11 上使用 `python -m tools.build_windows` 构建。
- 所生成的目录式程序包含 `DayNest.exe` 和 `_internal`，必须一起分发。目标机器不需要另外安装 Python。
- 对解压后的候选包以 `--smoke-test` 和独立测试数据库运行三次，均正常退出；干净 Windows 电脑、多显示器等仍需验证。自动测试不能替代人工验收。
- 移除子进程的 Python、Qt 插件及虚拟环境变量，并将其 PATH 限制为 Windows 目录后，冒烟测试连续三次通过。一次运行时模块检查显示 Python 3.15 DLL、Qt Core/GUI/Widgets DLL 及检测到的 VC++ 运行库从程序包加载。这不是全新 Windows 电脑测试。
- 未进行代码签名；不同电脑的 Windows 安全提示和兼容性尚未验证。

## 第三方许可调查

本项目代码采用 MIT；打包的 Python、PySide6、Qt、Shiboken、PyInstaller 引导程序、微软运行库及其内含的其他第三方组件分别适用各自的条款。实际分发前必须以最终程序包为准确认完整清单和通知内容。

- PySide6 6.12.0 的安装元数据列出 LGPL-3.0-only、GPL-2.0-only 或 GPL-3.0-only；Qt 官方说明有些模块仅在 GPL 下提供。不能将项目的 MIT 许可证视为覆盖依赖。旧测试包曾包含不使用的 Qt Virtual Keyboard，现有构建脚本已排除该模块。候选打包工具另外排除程序未使用的 Qt PDF DLL 和插件。其他图像插件等仍需逐一确认许可证及依赖。
- Qt 官方说明分发 LGPL 程序需要提供许可文本、声明、对应源码及用户替换或重新链接库的途径。应取得与实际分发二进制对应的完整源码和构建信息，确定可持续提供源码的方式，并实际验证用户可替换库；仅放置上游链接或版权声明不能证明所有义务均已满足。
- `licenses/` 中 LGPL-3.0 和 GPL-3.0 文本从 Qt 6.12.0 官方源码取得，文件 Git blob 哈希已与上游一致。工具已整理上游许可文本和归属记录，v3 资料包中 92 份归属记录的 87 处明确许可文件引用均可找到；这不代表实际二进制所需材料已全面核对。
- 已从 Qt 官方站点取得 Qt 6.12.0 的 qtbase、qtdeclarative、qtimageformats、qtshadertools、qtsvg 和 PySide6 源码压缩包，分别通过官方 SHA-256 校验；qtshadertools 用于补充 Qt Quick 的构建工具源码。这些文件暂存在本机构建目录，尚未公开提供，也还需要核对它们是否完整对应实际二进制及其编译选项。
- 构建目录内 12 个 Qt6 DLL 与本机 PySide6 安装文件的 SHA-256 一致；候选包排除了其中未使用的 Qt6Pdf.dll。这只能说明文件与安装环境一致，不能证明上游源码完整对应。
- 已从 PyPI 下载 Windows x64 的 PySide6 Essentials 和 Shiboken 6.12.0 wheel，并分别核对 PyPI 公布的 SHA-256。v12 候选包中 37 个 PySide6 二进制与 Essentials wheel 的对应文件逐个 SHA-256 一致，两个 Shiboken 二进制与其 wheel 一致；核对时排除了单独统一的微软运行库。这证明这些文件来自相应上游发行包，不证明源码构建过程已经独立复现。
- 候选包包含 Qt 官方所述的 Mesa llvmpipe 软件渲染库 `opengl32sw.dll`，已收录 Qt 6.12 上游的 Mesa 与 LLVM 归属资料；具体二进制及构建来源仍需核对。运行环境查询显示 Python 使用 OpenSSL 3.5.9 和 SQLite 3.53.4。
- 候选包附带 Python、PyInstaller、OpenSSL、DayNest 的许可证以及 Python Windows CRT 的附加条件。微软运行库、SQLite 及其他实际二进制的完整对应说明仍需核实。
- PySide 6.12.0 官方发行说明称 Python 3.15 为初步支持；当前本机测试通过不代表其他环境兼容性已经验证。
- CPython 官方附带 Windows CRT 再分发附加条件，已纳入候选包；PySide6 和 Shiboken 中的 VC++ DLL 与 Python 安装目录中的同名文件并不完全一致，不能据此认定它们具有相同再分发依据。微软文档将运行库再分发与 Visual Studio 许可关联，当前尚未确认相应分发权。便携版以开箱即用为目标，实验性的系统运行库方案不作为当前发布方案。
- 2026-11-04：本机检测到 Visual Studio 2026 Build Tools 的 VC Redistributable 目录，含 14.51.36247.0 版 x64 运行库。仅在 `.build-tmp/crt-uniform-experiment-20261104/` 的隔离副本中，将 10 个原运行库 DLL 统一替换为该目录中的同名文件，未修改已有候选 ZIP 或系统文件。限制子进程 PATH 并清除 Python、Qt 环境变量后，使用三个独立数据目录连续启动和退出三次，退出码均为 0，数据库均已创建。另一次运行时模块检查确认五种不同名称的运行库 DLL 均从隔离副本加载。该实验为核对文件来源提供依据；它不能证明 Build Tools 的安装或替换行为已取得公开再分发许可，也不能替代干净电脑及人工功能验证。现有 v7 候选 ZIP 不包含本实验的替换。
- 随后用户自行安装 Visual Studio Community 2026，`vswhere` 报告安装完成。微软将运行库分发与 Visual Studio 许可和分发要求关联；安装状态本身不能代替逐项核对许可证义务。打包脚本支持从指定目录统一选取微软运行库，并在包内记录各文件 SHA-256；v9 内部候选包完成 ZIP 完整性检查，解压后以独立数据目录和受限 PATH 连续启动退出三次。其他电脑和许可要求仍需核验。
- 当前库的运行时信息为 Qt 6.12.0、MSVC 2022、共享动态库；PySide6 与 Shiboken 均为 6.12.0。Python 3.15 运行时使用的 PySide 二进制报告以 Python 3.14.3 limited API 构建；本机运行成功不代表全部组合均已验证。
- 在隔离副本中，将 `Qt6Core.dll` 替换为来自 Qt 官方 Windows MSVC 2022 6.12.0 安装包、SHA-256 不同的构建后，程序三次冒烟启动退出成功。该安装包的上游 SHA-1 校验一致，其 SHA-256 为 `219d1b86def3be418e31d704572bc4acc91b2ec373c65595c9fb12b42bf098dc`；提取的 DLL SHA-256 为 `39175459c4837c8cc0f709a637fb6eadb25d696785109c8393559ec876f02703`。这不是修改过源码的替换测试。
- 尝试替换 Qt 6.12.1 开发快照时程序无法正常启动；静态检查显示当前 PySide6 所需的 `QtPrivate_6_12_0` 符号在该快照库中缺失。后续替换须验证精确版本及二进制兼容性。

参考官方资料：[Qt 许可](https://doc.qt.io/qt-6/licensing.html)、[Qt 第三方代码](https://doc.qt.io/qt-6/licenses-used-in-qt.html)、[Qt 开源许可证 FAQ](https://www.qt.io/faq/qt-open-source-licensing)、[PySide6 6.12 源码目录](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/)。

## 发布前剩余事项

1. 对最终包的每个 Qt 模块、插件和内含第三方组件完成许可与声明清单；核对 Python、OpenSSL、SQLite 和 VC++ 运行库再分发条款。
2. 保留并提供与所用二进制严格对应的 LGPL 源码和构建信息，验证接收者能替换库并运行；准备完整的版权及许可文件。
3. 在一台未安装 Python 和开发工具的 Windows 电脑上解压运行，人工验收桌面组件、待办、数据持久化、托盘、快捷键和退出。
4. 确认打包内容无个人数据、凭据和构建机器路径，计算 SHA-256；记录未签名及兼容性限制。
5. 创建 GitHub Release，上传最终 ZIP 与校验值，并更新 README 的下载入口。当前 GitHub 连接未提供 Release 创建或附件上传接口，需要可用的发布渠道。

已取得的官方源码压缩包 SHA-256，供后续对应和完整性核验：

```text
099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751  pyside-setup-everywhere-src-6.12.0.tar.xz
a951bd163c7b80fc6b8c88d7668fb56abf91c152373e13c10666763238131307  qtbase-everywhere-src-6.12.0.tar.xz
311f3a2603e1973bb59baef9dfa740a376de713157d4782ee043681e889c9260  qtdeclarative-everywhere-src-6.12.0.tar.xz
0943132b5db8de6b6a7f1d162682173e8763c7ed94e80fd39113292845f67762  qtimageformats-everywhere-src-6.12.0.tar.xz
c7d84f436e1aaef39fdcadebf2bd71bdf24dc69497e13f2e0198873cbbfea2ab  qtshadertools-everywhere-src-6.12.0.tar.xz
e4ab39534ec97987b1b9b60ef7f4d325d5912a69f8c713a01753174a4029331  qtsvg-everywhere-src-6.12.0.tar.xz
```

## 内部候选包

使用 `python -m tools.prepare_windows_candidate --bundle <构建目录中的 dist/DayNest> --qt-notices <Qt许可资料 ZIP> --vc-runtime-dir <微软 x64 运行库目录> --output <新的 ZIP 路径>`。`--vc-runtime-dir` 用于在 ZIP 内统一运行库并记录校验值，不会修改输入构建；省略该参数则保留原构建中的运行库。Qt 许可资料可通过 `python -m tools.prepare_qt_materials --source-dir <源码归档目录> --output-dir <输出目录>` 整理。脚本不会覆盖既有 ZIP，并会在包内标注其为内部候选；不能把该候选包当作已经完成许可审核的公开发布物。
