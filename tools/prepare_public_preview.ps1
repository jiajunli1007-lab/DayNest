# 构建并验证面向下载者的预览附件；此脚本不发布 Release。
$ErrorActionPreference = 'Stop'
. .\tools\prepare_preview_draft.ps1

$assets = Join-Path $PWD '.build-tmp\public-preview-assets'
$wheels = Join-Path $PWD '.build-tmp\public-preview-wheels'
New-Item -ItemType Directory -Path $assets, $wheels -ErrorAction Stop | Out-Null
$candidate = Join-Path $PWD '.build-tmp\draft-assets\candidate.zip'
$sources = Join-Path $PWD '.build-tmp\draft-qt-materials\DayNest-Qt源码材料-v3-待审核.zip'
Invoke-Python -B -m tools.stage_windows_preview --candidate $candidate --qt-sources $sources --output-dir $assets --release-preview
$app = Join-Path $assets 'DayNest-Windows-x64-preview.zip'
$source = Join-Path $assets 'DayNest-Qt-6.12.0-sources.zip'

# 从 PyPI 下载官方 wheel，并以固定 SHA-256 和逐文件对比检查二进制来源。
Invoke-Python -m pip download --disable-pip-version-check --no-deps --index-url https://pypi.org/simple --dest $wheels 'PySide6_Essentials==6.12.0' 'shiboken6==6.12.0'
Invoke-Python -B -m tools.audit_preview_wheels --package $app --qt-sources $source --wheel-dir $wheels --release-preview

$check = Join-Path $PWD '.build-tmp\public-preview-smoke'
New-Item -ItemType Directory -Path $check -ErrorAction Stop | Out-Null
Expand-Archive -LiteralPath $app -DestinationPath $check
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
foreach ($key in @('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH')) {
    Remove-Item -LiteralPath "Env:$key" -ErrorAction SilentlyContinue
}
for ($i = 1; $i -le 3; $i++) {
    $data = Join-Path $check "data-$i"
    New-Item -ItemType Directory -Path $data -ErrorAction Stop | Out-Null
    $p = Start-Process -FilePath (Join-Path $check 'DayNest\DayNest.exe') -ArgumentList @('--data-dir', ('"' + $data + '"'), '--smoke-test', '-platform', 'offscreen') -PassThru
    if (-not $p.WaitForExit(30000)) { $p.Kill(); throw "预览包第 $i 次启动测试超时。" }
    if ($p.ExitCode -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $data 'daynest.sqlite3'))) {
        throw "预览包第 $i 次启动测试失败：$($p.ExitCode)"
    }
}

$appHash = (Get-FileHash -LiteralPath $app -Algorithm SHA256).Hash.ToLowerInvariant()
$sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$notes = @"
## DayNest Windows 预览版

DayNest 是一款 Windows 桌面日历、待办和便签应用，由 [@jiajunli1007-lab](https://github.com/jiajunli1007-lab) 发起和维护。

### 下载与启动

下载 ``DayNest-Windows-x64-preview.zip`` 并完整解压，打开解压后的 ``DayNest`` 文件夹，双击 ``DayNest.exe``。请保留旁边的 ``_internal`` 文件夹；无需单独安装 Python。

### 预览版须知

- 已在 Windows 11 本机和 GitHub Windows 构建环境做基本验证；其他电脑的兼容性仍需测试。
- 程序未签名，Windows 可能显示安全提示；请从本项目发布页下载并核对下方 SHA-256。
- 提醒仅在程序运行时检查；窗口靠后模式不是真正的 Windows 壁纸层。
- 数据保存在本机，可在程序中备份和恢复。

### 源码与许可

DayNest 代码采用 MIT 许可证。Qt、PySide6、Python、微软运行库及其他依赖使用各自的许可证，详细说明在程序包 ``licenses`` 文件夹内。使用附带的微软运行库前，请阅读并同意适用于微软组件的[运行库许可](https://aka.ms/VCRedistLicense)。Qt 6.12.0 和 PySide6 6.12.0 的官方源码见本页的源码附件；更换动态库的说明在程序包内。尚未独立复现 Qt 上游源码构建。

### SHA-256

``````text
$appHash  DayNest-Windows-x64-preview.zip
$sourceHash  DayNest-Qt-6.12.0-sources.zip
``````
"@
$draftNotes = "> 草稿：尚未公开发布；完成发布前检查后再公开。`n`n" + $notes
$draftNotes | Set-Content -LiteralPath (Join-Path $assets 'draft-notes.md') -Encoding UTF8
$notes | Set-Content -LiteralPath (Join-Path $assets 'release-notes.md') -Encoding UTF8
Write-Output '公开预览版候选附件已完成验证；尚未公开发布。'
