$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\astra\Desktop\YTIMP4"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFolder = "C:\Users\astra\Desktop\YTIMP4_backup_$Timestamp"

Write-Host ""
Write-Host "YTIMP4 - Sync & Save"
Write-Host "===================="
Write-Host ""

Write-Host "Checking Python..."
try {
    python --version
    Write-Host "[OK]" -ForegroundColor Green
} catch {
    Write-Host "Python not found!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Setting up virtual environment..."
if (Test-Path "$ProjectRoot\.venv\Scripts\Activate.ps1") {
    & "$ProjectRoot\.venv\Scripts\Activate.ps1"
    Write-Host "[OK] venv activated" -ForegroundColor Green
} else {
    Write-Host "Creating venv..."
    python -m venv "$ProjectRoot\.venv"
    & "$ProjectRoot\.venv\Scripts\Activate.ps1"
}

Write-Host ""
Write-Host "Checking packages..."
$requirements = @(
    "flask>=2.0.0",
    "yt-dlp>=2023.0.0",
    "requests>=2.25.0",
    "beautifulsoup4>=4.9.0",
    "aiohttp>=3.8.0",
    "colorama>=0.4.4",
    "google-api-python-client>=2.0.0"
)

foreach ($pkg in $requirements) {
    $pkgName = ($pkg -split '>=')[0]
    try {
        pip show $pkgName 2>&1 | Out-Null
        Write-Host "  $pkgName [OK]" -ForegroundColor Green
    } catch {
        Write-Host "  Installing $pkgName..."
        pip install $pkgName -q
        Write-Host "  $pkgName done" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Fixing bootstrap.py..."
$bootstrapPath = "$ProjectRoot\bootstrap.py"
if (Test-Path $bootstrapPath) {
    $content = Get-Content $bootstrapPath -Raw
    if ($content -match "split\('<')[0") {
        Write-Host "Missing bracket found. Fixing..." -ForegroundColor Yellow
        $content = $content -replace "split\('<')[0", "split('<')[0]"
        Set-Content -Path $bootstrapPath -Value $content -NoNewline
        Write-Host "Fixed" -ForegroundColor Green
    } else {
        Write-Host "bootstrap.py looks fine" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Updating requirements.txt..."
$reqPath = "$ProjectRoot\requirements.txt"
$reqContent = @"
flask>=2.0.0
yt-dlp>=2023.0.0
requests>=2.25.0
beautifulsoup4>=4.9.0
aiohttp>=3.8.0
colorama>=0.4.4
google-api-python-client>=2.0.0
"@

if (Test-Path $reqPath) {
    $current = Get-Content $reqPath -Raw
    if ($current -ne $reqContent) {
        Write-Host "Updating..."
        Set-Content -Path $reqPath -Value $reqContent
        Write-Host "Done" -ForegroundColor Green
    } else {
        Write-Host "Already up to date" -ForegroundColor Green
    }
} else {
    Write-Host "Creating..."
    Set-Content -Path $reqPath -Value $reqContent
    Write-Host "Created" -ForegroundColor Green
}

Write-Host ""
Write-Host "Checking start.bat..."
$batPath = "$ProjectRoot\start.bat"
$batContent = @'
@echo off
chcp 65001 > nul
title YTIMP4
cd /d "%~dp0"

echo Starting YTIMP4...
python bootstrap.py

timeout /t 2 /nobreak > nul
start http://localhost:8080
pause
'@

if (Test-Path $batPath) {
    $current = Get-Content $batPath -Raw
    if ($current -ne $batContent) {
        Write-Host "Updating..."
        Set-Content -Path $batPath -Value $batContent
        Write-Host "Done" -ForegroundColor Green
    } else {
        Write-Host "Already up to date" -ForegroundColor Green
    }
} else {
    Write-Host "Creating..."
    Set-Content -Path $batPath -Value $batContent
    Write-Host "Created" -ForegroundColor Green
}

Write-Host ""
Write-Host "Creating backup..."
if (!(Test-Path $BackupFolder)) {
    New-Item -ItemType Directory -Path $BackupFolder -Force | Out-Null
}

$filesToBackup = @(
    "bootstrap.py",
    "ytimp4.py",
    "config.json",
    "requirements.txt",
    "start.bat"
)

foreach ($file in $filesToBackup) {
    $src = Join-Path $ProjectRoot $file
    $dst = Join-Path $BackupFolder $file
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Force
        Write-Host "  $file backed up" -ForegroundColor Gray
    }
}
Write-Host "Backup saved to: $BackupFolder" -ForegroundColor Green

Write-Host ""
Write-Host "Generating sync.json..."
$syncPath = "$ProjectRoot\sync\sync.json"
$syncData = @{
    version = "1.0.0"
    last_scan = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    project_root = $ProjectRoot
    files = @{}
    folders = @{
        servers = @{
            path = "servers"
            files = @("__init__.py", "channel_lookup.py", "channel_processor.py")
        }
        templates = @{
            path = "templates"
            files = @("index.html", "style.css")
        }
        sync = @{
            path = "sync"
            files = @("sync.json", "sync_manager.py", "__init__.py")
        }
        debugging = @{
            path = "debugging"
            files = @("debug.bat", "debug.py")
        }
        setup = @{
            path = "setup"
            files = @("bootstrap.py", "start.bat")
        }
        icons = @{
            path = ".icons"
            files = @("downloader.svg", "instructions.svg", "refresh.svg", "trash.svg", "channel.svg", "archive.svg")
        }
    }
    dependencies = @{
        requirements_file = "requirements.txt"
        python_version = ">=3.8"
    }
    scripts = @{
        start = "start.bat"
        bootstrap = "bootstrap.py"
        main = "ytimp4.py"
    }
    ports = @{
        default = 8080
        range_start = 8080
        range_end = 8090
    }
}

$projectFiles = Get-ChildItem -Path $ProjectRoot -Recurse -File | Where-Object {
    $_.Name -notmatch "\.pyc$" -and
    $_.FullName -notmatch "\.venv" -and
    $_.FullName -notmatch "__pycache__" -and
    $_.FullName -notmatch "\.vscode" -and
    $_.FullName -notmatch "archives" -and
    $_.FullName -notmatch "downloads" -and
    $_.FullName -notmatch "static"
}

foreach ($file in $projectFiles) {
    $relPath = $file.FullName.Replace($ProjectRoot, "").TrimStart("\")
    $hash = Get-FileHash -Path $file.FullName -Algorithm MD5
    $syncData.files[$relPath] = @{
        size = $file.Length
        modified = $file.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
        hash = $hash.Hash
    }
}

$syncData | ConvertTo-Json -Depth 10 | Set-Content -Path $syncPath -Encoding UTF8
Write-Host "sync.json generated" -ForegroundColor Green

Write-Host ""
Write-Host "Verifying files..."
if (Test-Path "$ProjectRoot\ytimp4.py") {
    Write-Host "  ytimp4.py [OK]" -ForegroundColor Green
} else {
    Write-Host "  ytimp4.py [MISSING]" -ForegroundColor Red
}

if (Test-Path "$ProjectRoot\servers\__init__.py") {
    Write-Host "  servers/__init__.py [OK]" -ForegroundColor Green
} else {
    Write-Host "  servers/__init__.py [MISSING]" -ForegroundColor Red
}

if (Test-Path "$ProjectRoot\servers\channel_lookup.py") {
    Write-Host "  servers/channel_lookup.py [OK]" -ForegroundColor Green
} else {
    Write-Host "  servers/channel_lookup.py [MISSING]" -ForegroundColor Red
}

Write-Host ""
Write-Host "Testing bootstrap.py..."
try {
    python -m py_compile "$ProjectRoot\bootstrap.py"
    Write-Host "bootstrap.py compiles [OK]" -ForegroundColor Green
} catch {
    Write-Host "bootstrap.py has errors!" -ForegroundColor Red
}

Write-Host ""
Write-Host "Creating index.html with SVG icons..."
$svgHome = '<svg viewBox="0 0 24 24" style="width:20px;height:20px;fill:currentColor"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>'
$svgDownloader = '<svg viewBox="0 0 24 24" style="width:20px;height:20px;fill:currentColor"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>'
$svgChannel = '<svg viewBox="0 0 24 24" style="width:20px;height:20px;fill:currentColor"><path d="M10 15l5.5-3-5.5-3v6zM21 3H3c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H3V5h18v14z"/></svg>'
$svgSettings = '<svg viewBox="0 0 24 24" style="width:20px;height:20px;fill:currentColor"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>'
$svgInstructions = '<svg viewBox="0 0 24 24" style="width:20px;height:20px;fill:currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>'

$htmlPath = "$ProjectRoot\templates\index.html"
if (Test-Path $htmlPath) {
    $html = Get-Content $htmlPath -Raw
    $html = $html -replace '🏠', $svgHome
    $html = $html -replace '📥', $svgDownloader
    $html = $html -replace '📺', $svgChannel
    $html = $html -replace '⚙️', $svgSettings
    $html = $html -replace '❓', $svgInstructions
    Set-Content -Path $htmlPath -Value $html -Encoding UTF8
    Write-Host "index.html updated with SVG icons" -ForegroundColor Green
} else {
    Write-Host "index.html not found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============="
Write-Host "Sync Complete!"
Write-Host "============="
Write-Host ""
Write-Host "Backup: $BackupFolder"
Write-Host "Sync:   $syncPath"
Write-Host ""
Write-Host "To run:"
Write-Host "  start.bat"
Write-Host "  python bootstrap.py"
Write-Host "  python ytimp4.py"
Write-Host ""

Read-Host "Press Enter to exit"