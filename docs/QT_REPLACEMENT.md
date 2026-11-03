# Qt 和 PySide6 源码及替换说明（待验证）

DayNest 的 Windows 目录式候选包使用 PySide6 和 Qt。候选包内 Qt 版本为 6.12.0，采用 Windows x86-64、MSVC 2022、动态库构建；PySide6 为 6.12.0。Qt、PySide6 和 Shiboken 的适用许可及第三方组件声明见 `licenses` 目录。DayNest 自身源码使用 MIT 许可证。

## 对应源码

正在整理的源码材料包含 PySide6 6.12.0 和 Qt 6.12.0 的 qtbase、qtdeclarative、qtimageformats、qtsvg 官方源码包及 SHA-256 列表。正式发布时需要让下载者同时获得源码材料，并再次核对它们与二进制构建的对应关系；目前材料尚未公开，不能把上游链接当作完成分发的证明。

Qt 和 PySide6 的构建说明：

- [Qt for Windows 从源码构建](https://doc.qt.io/qt-6/windows-building.html)
- [PySide6 从源码构建](https://doc.qt.io/qtforpython-6/building_from_source/index.html)
- [DayNest 项目源码](https://github.com/jiajunli1007-lab/DayNest)

## 更换动态库的思路

1. 退出 DayNest，先复制整个程序目录作为备份。数据库保存在用户数据目录，建议在管理窗口另外备份个人数据。
2. 从对应源码编译 Windows x86-64、与 Qt 6.12.0 和 MSVC 2022 二进制兼容的共享库；必要时同时编译相匹配的 PySide6、Shiboken 与 Qt 插件。详细构建条件以源码和官方文档为准。
3. 程序目录中 `_internal/PySide6` 下存放 Qt DLL 和 PySide6 模块；Qt 插件位于其 `plugins` 子目录，Shiboken 文件位于 `_internal/shiboken6`。可在备份副本中用兼容的自编译文件替换相应文件并保留名称，再启动程序检查。更换时可能需要配套替换相互依赖的库和插件。
4. 也可以从 DayNest 的项目源码重新构建应用，构建脚本和依赖版本见项目文档。Qt 和 PySide6 的构建工具链、兼容性和完整步骤仍需在干净环境验证。

**当前尚未完成使用修改过的 Qt 或 PySide6 构建替换并运行的实测。** 此文档是待验证的操作方向，不代表本候选包已经完成 LGPL 相关发布核验。
