Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$releaseVersion = "0.5.0"
$releaseDir = Join-Path $projectRoot "release"
$stagingDir = Join-Path $releaseDir "PortScope-$releaseVersion-win64"
$zipPath = Join-Path $releaseDir "PortScope-$releaseVersion-win64.zip"

if (Test-Path $releaseDir) {
    Remove-Item -LiteralPath $releaseDir -Recurse -Force
}

python -m PyInstaller --noconfirm --clean --onefile --windowed --name PortScope app.py

New-Item -ItemType Directory -Path $stagingDir | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot "dist\\PortScope.exe") -Destination $stagingDir
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $stagingDir
Copy-Item -LiteralPath (Join-Path $projectRoot "LICENSE") -Destination $stagingDir

Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipPath -Force

Write-Host "Release lista:"
Write-Host "EXE : $stagingDir\\PortScope.exe"
Write-Host "ZIP : $zipPath"
