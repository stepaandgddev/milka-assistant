param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Milky'),
    [switch]$Autostart,
    [switch]$NoAutostart,
    [switch]$Uninstall,
    [switch]$Yes,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
$AppName = 'Milky'
$SourceDir = $PSScriptRoot
$ProgramsDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$ShortcutPath = Join-Path $ProgramsDir 'Milky.lnk'
$StartupDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
$StartupCmd = Join-Path $StartupDir 'milky-autostart.cmd'
$StartupShortcut = Join-Path $StartupDir 'Milky.lnk'

function Show-Usage {
    Write-Host @"
Milky installer

Usage:
  .\install.ps1 [-Autostart|-NoAutostart] [-InstallDir PATH] [-Yes]
  .\install.ps1 -Uninstall [-Yes]

Options:
  -Autostart      enable autostart
  -NoAutostart    disable autostart
  -InstallDir     install directory (default: %LOCALAPPDATA%\Milky)
  -Yes            do not ask questions
  -Uninstall      remove the application
  -Help           show this help
"@
}

if ($Help) {
    Show-Usage
    exit 0
}

if ($Autostart -and $NoAutostart) {
    throw 'Cannot use -Autostart and -NoAutostart together'
}

if (-not $SourceDir) {
    throw 'Run install.ps1 from the project directory'
}

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    throw 'Install directory is not specified'
}

$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
if ($InstallDir -ieq [System.IO.Path]::GetPathRoot($InstallDir)) {
    throw "Invalid install directory: $InstallDir"
}
$InstallDir = $InstallDir.TrimEnd([char[]]@('\', '/'))
$forbiddenDirs = @(
    $env:USERPROFILE,
    $env:LOCALAPPDATA,
    $env:APPDATA,
    $env:ProgramFiles,
    ${env:ProgramFiles(x86)},
    $env:WINDIR
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
if ($forbiddenDirs -contains $InstallDir) {
    throw "Invalid install directory: $InstallDir"
}

if ($Uninstall) {
    if (-not $Yes) {
        $answer = Read-Host "Remove $AppName from $InstallDir? [y/N]"
        if ($answer -notmatch '^(y|yes)$') {
            Write-Host 'Cancelled'
            exit 0
        }
    }
    $VenvPython = Join-Path $InstallDir 'venv\Scripts\python.exe'
    $AutostartScript = Join-Path $InstallDir 'autostart.py'
    if ((Test-Path $VenvPython) -and (Test-Path $AutostartScript)) {
        & $VenvPython $AutostartScript disable 2>$null | Out-Null
    }
    Remove-Item -Force -ErrorAction SilentlyContinue $ShortcutPath
    Remove-Item -Force -ErrorAction SilentlyContinue $StartupCmd
    Remove-Item -Force -ErrorAction SilentlyContinue $StartupShortcut
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $InstallDir
    Write-Host "$AppName has been removed"
    exit 0
}

$AutostartMode = 'keep'
if ($Autostart) {
    $AutostartMode = 'enable'
}
elseif ($NoAutostart) {
    $AutostartMode = 'disable'
}
elseif (-not $Yes) {
    if ((Test-Path $StartupCmd) -or (Test-Path $StartupShortcut)) {
        $answer = Read-Host 'Autostart is already enabled. Keep it? [Y/n]'
        if ($answer -match '^(n|no)$') {
            $AutostartMode = 'disable'
        }
    }
    else {
        $answer = Read-Host 'Add Milky to autostart? [y/N]'
        if ($answer -match '^(y|yes)$') {
            $AutostartMode = 'enable'
        }
    }
}

$pythonCommand = Get-Command py -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $pythonCommand) {
    throw 'Python was not found. Install Python 3.10+ and add it to PATH.'
}

& $pythonCommand.Source -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)'
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.10 or newer is required.'
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$files = @(
    'main.py',
    'ai_client.py',
    'settings_dialog.py',
    'settings_store.py',
    'autostart.py',
    'web_search.py',
    'milka_idle.svg',
    'requirements.txt',
    'requirements-search.txt',
    'README.md',
    'LICENSE',
    '.env.example'
)

if ($SourceDir -ne $InstallDir) {
    foreach ($file in $files) {
        $source = Join-Path $SourceDir $file
        if (Test-Path $source) {
            Copy-Item -LiteralPath $source -Destination $InstallDir -Force
        }
    }

    $gifsSource = Join-Path $SourceDir 'gifs'
    if (Test-Path $gifsSource) {
        $gifsTarget = Join-Path $InstallDir 'gifs'
        New-Item -ItemType Directory -Force -Path $gifsTarget | Out-Null
        Copy-Item -Path (Join-Path $gifsSource '*') -Destination $gifsTarget -Recurse -Force
    }
}

$envFile = Join-Path $InstallDir '.env'
$envExample = Join-Path $InstallDir '.env.example'
if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item -LiteralPath $envExample -Destination $envFile
}

$VenvDir = Join-Path $InstallDir 'venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Host 'Creating virtual environment...'
    & $pythonCommand.Source -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not create the virtual environment'
    }
}

Write-Host 'Installing dependencies...'
& $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $InstallDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    throw 'Could not install dependencies'
}

$env:MILKY_ICON_SOURCE = Join-Path $InstallDir 'milka_idle.svg'
$env:MILKY_ICON_TARGET = Join-Path $InstallDir 'milka_idle.ico'
$iconScript = @'
import os
from PySide6.QtGui import QImage
image = QImage(os.environ["MILKY_ICON_SOURCE"])
if not image.isNull():
    image.scaled(256, 256).save(os.environ["MILKY_ICON_TARGET"])
'@
$iconScript | & $VenvPython -
Remove-Item Env:MILKY_ICON_SOURCE -ErrorAction SilentlyContinue
Remove-Item Env:MILKY_ICON_TARGET -ErrorAction SilentlyContinue

$LauncherPath = Join-Path $InstallDir 'Milky.cmd'
$launcher = @'
@echo off
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" "%~dp0main.py" %*
'@
Set-Content -LiteralPath $LauncherPath -Value $launcher -Encoding ASCII

New-Item -ItemType Directory -Force -Path $ProgramsDir | Out-Null
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($ShortcutPath)
$VenvPythonw = Join-Path $VenvDir 'Scripts\pythonw.exe'
if (-not (Test-Path $VenvPythonw)) {
    $VenvPythonw = $VenvPython
}
$shortcut.TargetPath = $VenvPythonw
$shortcut.Arguments = '"' + (Join-Path $InstallDir 'main.py') + '"'
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Description = 'Milky AI pet'
$iconPath = Join-Path $InstallDir 'milka_idle.ico'
if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}
$shortcut.Save()

$AutostartScript = Join-Path $InstallDir 'autostart.py'
if ($AutostartMode -eq 'enable') {
    & $VenvPython $AutostartScript enable
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not enable autostart'
    }
}
elseif ($AutostartMode -eq 'disable') {
    & $VenvPython $AutostartScript disable
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not disable autostart'
    }
}

Write-Host ''
Write-Host "$AppName has been installed to $InstallDir"
Write-Host "Run: $LauncherPath"
Write-Host 'A shortcut has been added to the Start menu.'
if ($AutostartMode -eq 'enable') {
    Write-Host 'Autostart enabled.'
}
elseif ($AutostartMode -eq 'disable') {
    Write-Host 'Autostart disabled.'
}
