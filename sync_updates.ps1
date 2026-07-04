$ErrorActionPreference = "Stop"

function Show-Menu {
    Clear-Host
    Write-Host ""
    Write-Host "░██     ░██ ░██████████░██████░███     ░███ ░█████████     ░████                 ░██████████  ░██████     ░██████   ░██         ░████████     ░██████   ░██    ░██ " -ForegroundColor Red
    Write-Host "░██   ░██      ░██      ░██  ░████   ░████ ░██     ░██   ░██ ██                     ░██     ░██   ░██   ░██   ░██  ░██         ░██    ░██   ░██   ░██   ░██  ░██  " -ForegroundColor Red
    Write-Host " ░██ ░██       ░██      ░██  ░██░██ ░██░██ ░██     ░██  ░██  ██                     ░██    ░██     ░██ ░██     ░██ ░██         ░██    ░██  ░██     ░██   ░██░██   " -ForegroundColor Red
    Write-Host "  ░████        ░██      ░██  ░██ ░████ ░██ ░█████████  ░██   ██      ░██████        ░██    ░██     ░██ ░██     ░██ ░██         ░████████   ░██     ░██    ░███    " -ForegroundColor Red
    Write-Host "   ░██         ░██      ░██  ░██  ░██  ░██ ░██         ░█████████                   ░██    ░██     ░██ ░██     ░██ ░██         ░██     ░██ ░██     ░██   ░██░██   " -ForegroundColor Red
    Write-Host "   ░██         ░██      ░██  ░██       ░██ ░██              ░██                     ░██     ░██   ░██   ░██   ░██  ░██         ░██     ░██  ░██   ░██   ░██  ░██  " -ForegroundColor Red
    Write-Host "   ░██         ░██    ░██████░██       ░██ ░██              ░██                     ░██      ░██████     ░██████   ░██████████ ░█████████    ░██████   ░██    ░██ " -ForegroundColor Red
    Write-Host ""
    Write-Host "                                     YTIMP4 - Toolbox" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════════════════════════" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  1. Sync Git Repository"
    Write-Host "  2. Install Dependencies"
    Write-Host "  3. Run Application"
    Write-Host "  4. Check Status"
    Write-Host "  5. Fix Common Issues"
    Write-Host "  6. Backup Project"
    Write-Host "  7. Clean Cache"
    Write-Host "  8. Open in Explorer"
    Write-Host "  9. Exit"
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════════════════════════" -ForegroundColor Gray
    Write-Host ""
}

function Sync-Git {
    Write-Host ""
    Write-Host "░ Syncing Git Repository..." -ForegroundColor Cyan
    Write-Host ""
    
    $branch = git branch --show-current
    Write-Host "  Current branch: $branch" -ForegroundColor Yellow
    Write-Host ""
    
    Write-Host "  Fetching updates..." -ForegroundColor Gray
    git fetch origin
    Write-Host ""
    
    Write-Host "  Pulling latest changes..." -ForegroundColor Gray
    git pull origin $branch
    Write-Host ""
    
    $changes = git status --porcelain
    if ($changes) {
        Write-Host "  Changes detected:" -ForegroundColor Yellow
        git status --short
        Write-Host ""
        $choice = Read-Host "  Add and commit changes? (y/n)"
        if ($choice -eq "y") {
            git add .
            $msg = Read-Host "  Commit message"
            if ($msg) {
                git commit -m $msg
                Write-Host ""
                Write-Host "  Pushing to origin..." -ForegroundColor Gray
                git push origin $branch
            }
        }
    } else {
        Write-Host "  No changes detected" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "  Sync complete!" -ForegroundColor Green
    Read-Host "`nPress Enter to continue"
}

function Install-Dependencies {
    Write-Host ""
    Write-Host "░ Installing Dependencies..." -ForegroundColor Cyan
    Write-Host ""
    
    $requirements = @(
        "flask",
        "yt-dlp",
        "requests",
        "beautifulsoup4",
        "aiohttp",
        "colorama",
        "google-api-python-client"
    )
    
    foreach ($pkg in $requirements) {
        Write-Host "  Installing $pkg..." -ForegroundColor Gray
        pip install $pkg -q 2>&1 | Out-Null
        Write-Host "  $pkg [OK]" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "  Dependencies installed!" -ForegroundColor Green
    Read-Host "`nPress Enter to continue"
}

function Run-Application {
    Write-Host ""
    Write-Host "░ Starting YTIMP4..." -ForegroundColor Cyan
    Write-Host ""
    
    if (Test-Path "ytimp4.py") {
        Write-Host "  Opening http://localhost:8080..." -ForegroundColor Yellow
        Start-Process "http://localhost:8080"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "python ytimp4.py"
    } else {
        Write-Host "  ytimp4.py not found!" -ForegroundColor Red
    }
    
    Read-Host "`nPress Enter to continue"
}

function Check-Status {
    Write-Host ""
    Write-Host "░ Checking Status..." -ForegroundColor Cyan
    Write-Host ""
    
    $files = @(
        "ytimp4.py",
        "bootstrap.py",
        "requirements.txt",
        "start.bat",
        "config.json"
    )
    
    foreach ($file in $files) {
        if (Test-Path $file) {
            Write-Host "  $file [OK]" -ForegroundColor Green
        } else {
            Write-Host "  $file [MISSING]" -ForegroundColor Red
        }
    }
    
    Write-Host ""
    Write-Host "  Git Status:" -ForegroundColor Yellow
    git status --short
    
    Write-Host ""
    Write-Host "  Python Version:" -ForegroundColor Yellow
    python --version
    
    Read-Host "`nPress Enter to continue"
}

function Fix-CommonIssues {
    Write-Host ""
    Write-Host "░ Fixing Common Issues..." -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "  Creating missing directories..." -ForegroundColor Gray
    @("static/icons", "templates", "servers", "sync", "debugging", "setup").ForEach({
        New-Item -ItemType Directory -Path $_ -Force | Out-Null
        Write-Host "    $_ [OK]" -ForegroundColor Green
    })
    
    Write-Host ""
    Write-Host "  Running pip install..." -ForegroundColor Gray
    pip install flask yt-dlp requests beautifulsoup4 aiohttp colorama google-api-python-client -q
    
    Write-Host ""
    Write-Host "  Fixing git line endings..." -ForegroundColor Gray
    git config core.autocrlf true
    
    Write-Host ""
    Write-Host "  Done!" -ForegroundColor Green
    Read-Host "`nPress Enter to continue"
}

function Backup-Project {
    Write-Host ""
    Write-Host "░ Creating Backup..." -ForegroundColor Cyan
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupFolder = "backup_$timestamp"
    
    Write-Host "  Backup folder: $backupFolder" -ForegroundColor Yellow
    
    New-Item -ItemType Directory -Path $backupFolder -Force | Out-Null
    
    $files = @(
        "ytimp4.py",
        "bootstrap.py",
        "requirements.txt",
        "start.bat",
        "config.json"
    )
    
    foreach ($file in $files) {
        if (Test-Path $file) {
            Copy-Item -Path $file -Destination "$backupFolder\" -Force
            Write-Host "    $file backed up" -ForegroundColor Green
        }
    }
    
    if (Test-Path "templates") {
        Copy-Item -Path "templates" -Destination "$backupFolder\" -Recurse -Force
        Write-Host "    templates backed up" -ForegroundColor Green
    }
    
    if (Test-Path "static") {
        Copy-Item -Path "static" -Destination "$backupFolder\" -Recurse -Force
        Write-Host "    static backed up" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "  Backup complete: $backupFolder" -ForegroundColor Green
    Read-Host "`nPress Enter to continue"
}

function Clean-Cache {
    Write-Host ""
    Write-Host "░ Cleaning Cache..." -ForegroundColor Cyan
    
    Write-Host "  Removing Python cache..." -ForegroundColor Gray
    Remove-Item -Path "*.pyc" -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
    
    Write-Host "  Removing venv..." -ForegroundColor Gray
    Remove-Item -Path ".venv" -Recurse -Force -ErrorAction SilentlyContinue
    
    Write-Host "  Removing .vscode cache..." -ForegroundColor Gray
    Remove-Item -Path ".vscode" -Recurse -Force -ErrorAction SilentlyContinue
    
    Write-Host ""
    Write-Host "  Cache cleaned!" -ForegroundColor Green
    Read-Host "`nPress Enter to continue"
}

function Open-Explorer {
    Write-Host ""
    Write-Host "░ Opening Explorer..." -ForegroundColor Cyan
    explorer .
    Read-Host "`nPress Enter to continue"
}

do {
    Show-Menu
    $choice = Read-Host "Select option"
    
    switch ($choice) {
        "1" { Sync-Git }
        "2" { Install-Dependencies }
        "3" { Run-Application }
        "4" { Check-Status }
        "5" { Fix-CommonIssues }
        "6" { Backup-Project }
        "7" { Clean-Cache }
        "8" { Open-Explorer }
        "9" { Write-Host "`n░ Goodbye!" -ForegroundColor Green }
        default { Write-Host "`n  Invalid option" -ForegroundColor Red }
    }
} while ($choice -ne "9")
