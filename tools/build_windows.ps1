$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}

foreach ($ConfigFile in @("config.json", "config.example.json")) {
  $ConfigPath = Join-Path $Root $ConfigFile
  if (-not (Test-Path $ConfigPath)) {
    throw "Build failed: $ConfigFile was not found in $Root"
  }

  & $Python -m json.tool $ConfigPath > $null
  if ($LASTEXITCODE -ne 0) {
    throw "Build failed: $ConfigFile is not valid JSON. Fix it before building."
  }
}

& $Python -m PyInstaller `
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

if (Test-Path (Join-Path $Root "OPERATOR_GUIDE.md")) {
  Copy-Item -Force (Join-Path $Root "OPERATOR_GUIDE.md") (Join-Path $Dist "OPERATOR_GUIDE.md")
}

if (Test-Path (Join-Path $Root "OPERATOR_GUIDE.html")) {
  Copy-Item -Force (Join-Path $Root "OPERATOR_GUIDE.html") (Join-Path $Dist "OPERATOR_GUIDE.html")
}

if (Test-Path (Join-Path $Root "OPERATOR_GUIDE.pdf")) {
  Copy-Item -Force (Join-Path $Root "OPERATOR_GUIDE.pdf") (Join-Path $Dist "OPERATOR_GUIDE.pdf")
}

if (Test-Path (Join-Path $Root "content")) {
  $ContentItems = Get-ChildItem -Force (Join-Path $Root "content")
  foreach ($Item in $ContentItems) {
    Copy-Item -Recurse -Force $Item.FullName $ContentDist
  }
}

$Exe = Join-Path $Dist "StandoffHistory.exe"
if (-not (Test-Path $Exe)) {
  throw "Build failed: StandoffHistory.exe was not created in $Dist"
}

$StartBat = Join-Path $Dist "START_STANDOFF.bat"
Set-Content -Encoding ASCII -Path $StartBat -Value @"
@echo off
setlocal
set "APP_DIR=%~dp0"
set "APP_EXE=%APP_DIR%StandoffHistory.exe"

if not exist "%APP_EXE%" (
  echo ERROR: StandoffHistory.exe was not found.
  echo.
  echo Start this file from the StandoffHistory folder:
  echo %APP_DIR%
  echo.
  echo Do not copy START_STANDOFF.bat to Desktop.
  echo Create a shortcut to START_STANDOFF.bat instead.
  echo.
  pause
  exit /b 1
)

cd /d "%APP_DIR%"
start "" "%APP_EXE%"
"@

$ShortcutBat = Join-Path $Dist "CREATE_DESKTOP_SHORTCUT.bat"
Set-Content -Encoding ASCII -Path $ShortcutBat -Value @"
@echo off
setlocal
set "APP_DIR=%~dp0"
set "TARGET=%APP_DIR%START_STANDOFF.bat"
set "SHORTCUT=%USERPROFILE%\Desktop\Standoff.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command "`$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%'); `$s.TargetPath='%TARGET%'; `$s.WorkingDirectory='%APP_DIR%'; `$s.Save()"

echo Desktop shortcut created:
echo %SHORTCUT%
pause
"@

Write-Host ""
Write-Host "Build ready:"
Write-Host $Dist
Write-Host ""
Write-Host "Run:"
Write-Host (Join-Path $Dist "StandoffHistory.exe")
