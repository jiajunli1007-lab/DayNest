# 技术调研与复用记录

调研日期：2026-10-30。仅参考思路和公开 API；未复制任何所列项目源代码或资源。

- [Lively Wallpaper](https://github.com/lively-community/lively)：GPL-3.0，适合了解桌面壁纸产品能力。若复用其代码，需要遵守 GPL 及分发条件；目前不复用。
- [DeskX Wallpaper Engine](https://github.com/Felix-au/DeskX-Wallpaper-Engine)：MIT，提供 WorkerW 和独立交互组件的设计参考。复制或分发其代码需要保留版权与许可证声明；目前不复用。
- [DeskWidgets](https://github.com/VaticUI/DeskWidgets)：MIT，Python/PySide6 组件应用，提供体验设计参考。复制或分发其代码需要保留版权与许可证声明；目前不复用。
- [Qt 授权](https://doc.qt.io/qt-6/licensing.html)：Qt 各模块及第三方组件的许可可能不同，分发前必须逐项核对实际打包内容、许可和用户替换库等义务；不能只依据应用自己的许可证判断。
- Qt 将 Virtual Keyboard 列为 GPL 模块；PyInstaller 自动收集了该组件，但 DayNest 未使用它。构建脚本在独立的新构建目录中移除此插件与其动态库；Windows 输入法仍需要真实桌面验证。其余组件的许可仍待逐项核对。
- [PyInstaller 6.22.3](https://pypi.org/project/pyinstaller/6.22.3/) 支持 Python 3.15。其[许可](https://pyinstaller.org/en/latest/license.html)含打包应用的例外条款，但应用及依赖各自的许可义务仍需满足。

## 技术决策

保持 Python 3.15、PySide6 6.12 和 SQLite；用自编写代码实现。业务存储、Windows 热键和界面分层。默认普通窗口可工作，壁纸层单独实验并保留可靠降级。Qt 的透明背景不是 DWM 真正的模糊/亚克力效果；初期使用可调半透明视觉，真实玻璃效果留待验证。

Windows [SetParent](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setparent) 是公开接口，但 WorkerW/Progman 组合不是稳定桌面组件协议；DPI、输入、Explorer 重启和多个显示器都需真实桌面测试，不能凭句柄或调用成功就宣称通过。

## 阶段验收

- P0：普通窗口、透明度、置顶、托盘和热键基础；桌面层、打包和真实 Windows 行为单独验证。
- P1：待办与 SQLite 持久化；可恢复的窗口与托盘。
- P2：日期视图、便签、外观设置及数据库备份恢复。
- P3：许可证确认、打包、发布文档及真实机器验收；公开推送或发布前须经用户确认。
