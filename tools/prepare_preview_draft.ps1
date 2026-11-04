# 在 GitHub 的独立 Windows 环境构建并验证草稿附件。
$ErrorActionPreference = 'Stop'

function Invoke-Python {
    & '.\.venv-diagnostic\Scripts\python.exe' @args
    if ($LASTEXITCODE -ne 0) { throw "Python 命令失败，退出码：$LASTEXITCODE" }
}

python -m venv .venv-diagnostic
if ($LASTEXITCODE -ne 0) { throw '虚拟环境创建失败。' }
Invoke-Python -m pip install --disable-pip-version-check -r requirements-build.txt
Invoke-Python -B -m unittest discover -s tests
Invoke-Python -B -m tools.build_windows

$builds = @(Get-ChildItem -LiteralPath '.build-tmp' -Directory -Filter 'build-*')
if ($builds.Count -ne 1) { throw '预期恰好有一个新构建目录。' }
$bundle = Join-Path $builds[0].FullName 'dist\DayNest'

# 从已安装的 Visual Studio 公开版 Redistributable 目录中选择 x64 运行库。
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$installations = @(& $vswhere -products '*' -property installationPath)
$crt = $null
$required = @('msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'vcruntime140.dll', 'vcruntime140_1.dll')
foreach ($installation in $installations) {
    $root = Join-Path $installation 'VC\Redist\MSVC'
    if (-not (Test-Path -LiteralPath $root)) { continue }
    $versions = @(Get-ChildItem -LiteralPath $root -Directory | Where-Object { $_.Name -match '^\d+(\.\d+)+$' } | Sort-Object { [version]$_.Name } -Descending)
    foreach ($version in $versions) {
        $x64 = Join-Path $version.FullName 'x64'
        if (-not (Test-Path -LiteralPath $x64)) { continue }
        foreach ($dir in (Get-ChildItem -LiteralPath $x64 -Directory -Filter 'Microsoft.VC*.CRT')) {
            if (@($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $dir.FullName $_)) }).Count -eq 0) {
                $crt = $dir.FullName
                break
            }
        }
        if ($crt) { break }
    }
    if ($crt) { break }
}
if (-not $crt) { throw '找不到完整的 x64 Visual C++ 运行库。' }
foreach ($name in $required) {
    $signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $crt $name)
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
        throw "微软运行库签名检查失败：$name"
    }
}

$src = Join-Path $PWD '.build-tmp\draft-qt-sources'
$materials = Join-Path $PWD '.build-tmp\draft-qt-materials'
$assets = Join-Path $PWD '.build-tmp\draft-assets'
New-Item -ItemType Directory -Path $src, $materials, $assets -ErrorAction Stop | Out-Null
$qtFiles = @('qtbase', 'qtdeclarative', 'qtimageformats', 'qtshadertools', 'qtsvg')
foreach ($module in $qtFiles) {
    $name = "$module-everywhere-src-6.12.0.tar.xz"
    Invoke-WebRequest -Uri "https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/$name" -OutFile (Join-Path $src $name) -TimeoutSec 300
}
$pyside = 'pyside-setup-everywhere-src-6.12.0.tar.xz'
Invoke-WebRequest -Uri "https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/$pyside" -OutFile (Join-Path $src $pyside) -TimeoutSec 300
# 工具会核对每个上游 SHA-256，且不会覆盖既有材料。
Invoke-Python -B -m tools.prepare_qt_materials --source-dir $src --output-dir $materials
$notice = Join-Path $materials 'DayNest-Qt许可资料-v3-待审核.zip'
$qtSources = Join-Path $materials 'DayNest-Qt源码材料-v3-待审核.zip'
$candidate = Join-Path $assets 'candidate.zip'
Invoke-Python -B -m tools.prepare_windows_candidate --bundle $bundle --qt-notices $notice --vc-runtime-dir $crt --output $candidate
Invoke-Python -B -m tools.stage_windows_preview --candidate $candidate --qt-sources $qtSources --output-dir $assets

$app = Join-Path $assets 'DayNest-Windows-x64-preview-待审核.zip'
$source = Join-Path $assets 'DayNest-Qt-6.12.0-sources-待审核.zip'
$check = Join-Path $PWD '.build-tmp\draft-smoke'
New-Item -ItemType Directory -Path $check -ErrorAction Stop | Out-Null
Expand-Archive -LiteralPath $app -DestinationPath $check
$data = Join-Path $check 'data'
New-Item -ItemType Directory -Path $data -ErrorAction Stop | Out-Null

# 仅修改此步骤和子进程的环境，模拟没有 Python 路径的启动。
$oldPath = $env:PATH
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
foreach ($key in @('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH')) {
    Remove-Item -LiteralPath "Env:$key" -ErrorAction SilentlyContinue
}
$process = Start-Process -FilePath (Join-Path $check 'DayNest\DayNest.exe') -ArgumentList @('--data-dir', ('"' + $data + '"'), '--smoke-test', '-platform', 'offscreen') -PassThru
if (-not $process.WaitForExit(30000)) { $process.Kill(); throw '预览包启动测试超时。' }
if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $data 'daynest.sqlite3'))) {
    throw "预览包启动测试失败：$($process.ExitCode)"
}
$env:PATH = $oldPath

$appHash = (Get-FileHash -LiteralPath $app -Algorithm SHA256).Hash.ToLowerInvariant()
$sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$notes = Join-Path $assets 'draft-notes.txt'
@"
DayNest Windows 预览版草稿：尚未公开发布。

程序、运行库和 Qt 源码材料均为待审核附件。独立 Windows 构建、自动测试、
程序解压启动和数据库创建已通过；真实桌面交互、其他设备及许可细节仍需核验。
发布前需要检查 Qt 对应源码和替换方式，以及微软运行库的最终分发条件。

SHA-256:
$appHash  DayNest-Windows-x64-preview-待审核.zip
$sourceHash  DayNest-Qt-6.12.0-sources-待审核.zip
"@ | Set-Content -LiteralPath $notes -Encoding UTF8

Write-Output '待审核草稿附件已构建并验证，尚未公开发布。'
