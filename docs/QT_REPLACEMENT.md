# Qt 和 PySide6 源码及替换说明

DayNest 的 Windows 目录式预览包使用 PySide6 和 Qt。预览包内 Qt 版本为 6.12.0，采用 Windows x86-64、MSVC 2022、动态库构建；PySide6 为 6.12.0。Qt、PySide6 和 Shiboken 的适用许可及第三方组件声明见 `licenses` 目录。DayNest 自身源码使用 MIT 许可证。

## 对应源码

预览版的[发布页面](https://github.com/jiajunli1007-lab/DayNest/releases/tag/v0.1.0-preview.2)提供 PySide6 6.12.0 和 Qt 6.12.0 的 qtbase、qtdeclarative、qtimageformats、qtshadertools、qtsvg 官方源码包及 SHA-256 列表；尚未独立复现上游二进制构建。

Qt 和 PySide6 的构建说明：

- [Qt for Windows 从源码构建](https://doc.qt.io/qt-6/windows-building.html)
- [PySide6 从源码构建](https://doc.qt.io/qtforpython-6/building_from_source/index.html)
- [DayNest 项目源码](https://github.com/jiajunli1007-lab/DayNest)

## 更换动态库的思路

1. 退出 DayNest，先复制整个程序目录作为备份。数据库保存在用户数据目录，建议在管理窗口另外备份个人数据。
2. 从对应源码编译 Windows x86-64、与 Qt 6.12.0 和 MSVC 2022 二进制兼容的共享库；必要时同时编译相匹配的 PySide6、Shiboken 与 Qt 插件。详细构建条件以源码和官方文档为准。
3. 程序目录中 `_internal/PySide6` 下存放 Qt DLL 和 PySide6 模块；Qt 插件位于其 `plugins` 子目录，Shiboken 文件位于 `_internal/shiboken6`。可在备份副本中用兼容的自编译文件替换相应文件并保留名称，再启动程序检查。更换时可能需要配套替换相互依赖的库和插件。
4. 也可以从 DayNest 的项目源码重新构建应用，构建脚本和依赖版本见项目文档。Qt 和 PySide6 的构建工具链、兼容性和完整步骤仍需在干净环境验证。

在隔离测试副本中，已用另一份来自 Qt 官方 Windows MSVC 2022 6.12.0 安装包、SHA-256 不同的 `Qt6Core.dll` 替换原文件；程序连续三次冒烟启动退出成功。这验证了该同版本文件的替换路径，并不证明任意构建或修改都兼容。

另一次 Qt 6.12.1 开发快照替换测试未能启动：当前 PySide6 的 `QtCore.pyd` 引用了带有 6.12.0 私有版本标记的符号，而该 6.12.1 核心库没有对应符号。因此不能假设同一 6.12 系列的不同补丁版本可直接替换。

**当前尚未完成使用修改过的 Qt 或 PySide6 源码自行构建并替换运行的实测。** 此文档不构成许可证符合性结论。
