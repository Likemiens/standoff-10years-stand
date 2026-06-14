$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

python -m PyInstaller `
  --noconfirm `
  --clean `
  --name StandoffHistory `
  --onedir `
  --windowed `
  --collect-all PySide6 `
  --hidden-import serial `
  --hidden-import serial.tools.list_ports `
  --hidden-import serial.tools.list_ports_windows `
  main.py

$Dist = Join-Path $Root "dist\StandoffHistory"
$ContentDist = Join-Path $Dist "content"
$LogsDist = Join-Path $Dist "logs"

New-Item -ItemType Directory -Force -Path $ContentDist | Out-Null
New-Item -ItemType Directory -Force -Path $LogsDist | Out-Null
New-Item -ItemType File -Force -Path (Join-Path $LogsDist "events.log") | Out-Null

Copy-Item -Force (Join-Path $Root "config.json") (Join-Path $Dist "config.json")
Copy-Item -Force (Join-Path $Root "config.example.json") (Join-Path $Dist "config.example.json")

if (Test-Path (Join-Path $Root "README.md")) {
  Copy-Item -Force (Join-Path $Root "README.md") (Join-Path $Dist "README.md")
}

if (Test-Path (Join-Path $Root "TEST_PLAN.md")) {
  Copy-Item -Force (Join-Path $Root "TEST_PLAN.md") (Join-Path $Dist "TEST_PLAN.md")
}

if (Test-Path (Join-Path $Root "content")) {
  $ContentItems = Get-ChildItem -Force (Join-Path $Root "content")
  foreach ($Item in $ContentItems) {
    Copy-Item -Recurse -Force $Item.FullName $ContentDist
  }
}

$StartBat = Join-Path $Dist "START_STANDOFF.bat"
Set-Content -Encoding ASCII -Path $StartBat -Value @"
@echo off
cd /d "%~dp0"
start "" "StandoffHistory.exe"
"@

Write-Host ""
Write-Host "Build ready:"
Write-Host $Dist
Write-Host ""
Write-Host "Run:"
Write-Host (Join-Path $Dist "StandoffHistory.exe")
