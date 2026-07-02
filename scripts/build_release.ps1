Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$releaseVersion = "0.5.1"
$releaseDir = Join-Path $projectRoot "release"
$stagingDir = Join-Path $releaseDir "PortScope-$releaseVersion-win64"
$zipPath = Join-Path $releaseDir "PortScope-$releaseVersion-win64.zip"
$iconPath = Join-Path $projectRoot "assets\\portscope.ico"

if (Test-Path $releaseDir) {
    if (Test-Path $stagingDir) {
        Remove-Item -LiteralPath $stagingDir -Recurse -Force
    }
    if (Test-Path $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
} else {
    New-Item -ItemType Directory -Path $releaseDir | Out-Null
}

python -m PyInstaller --noconfirm --clean --onefile --windowed --icon $iconPath --name PortScope app.py

New-Item -ItemType Directory -Path $stagingDir | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot "dist\\PortScope.exe") -Destination $stagingDir
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $stagingDir
Copy-Item -LiteralPath (Join-Path $projectRoot "LICENSE") -Destination $stagingDir
Copy-Item -LiteralPath (Join-Path $projectRoot "assets\\portscope-icon.png") -Destination $stagingDir

Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipPath -Force

Write-Host "Release lista:"
Write-Host "EXE : $stagingDir\\PortScope.exe"
Write-Host "ZIP : $zipPath"
