$ErrorActionPreference = "Stop"

function Show-Menu {
    Clear-Host
    Write-Host ""
    Write-Host "  ██████  ███████ ███    ███  ██████   " -ForegroundColor Red
    Write-Host "  ██   ██ ██      ████  ████ ██    ██  " -ForegroundColor White
    Write-Host "  ██████  █████   ██ ████ ██ ██    ██  " -ForegroundColor Red
    Write-Host "  ██   ██ ██      ██  ██  ██ ██    ██  " -ForegroundColor White
    Write-Host "  ██   ██ ███████ ██      ██  ██████   " -ForegroundColor Red
    Write-Host ""
    Write-Host "  YTIMP4 - TOOLBOX (REMO)" -ForegroundColor Red
    Write-Host "  YouTube Downloader & Manager" -ForegroundColor White
    Write-Host "  Developer: Livia" -ForegroundColor Gray
    Write-Host "  Contributors: FILipKOS, Lexxenaii" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  GitHub: https://github.com/nixisaka/YTIMP4" -ForegroundColor Gray
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  1. Sync Git Repository" -ForegroundColor White
    Write-Host "  2. Install Dependencies" -ForegroundColor White
    Write-Host "  3. Start Application" -ForegroundColor White
    Write-Host "  4. Run Bootstrap" -ForegroundColor White
    Write-Host "  5. Check Status" -ForegroundColor White
    Write-Host "  6. Repair Issues" -ForegroundColor White
    Write-Host "  7. Backup Project" -ForegroundColor White
    Write-Host "  8. Clear Cache" -ForegroundColor White
    Write-Host "  9. Open Explorer" -ForegroundColor White
    Write-Host "  10. Exit" -ForegroundColor White
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor DarkGray
    Write-Host ""
}

function Sync-Git {
    Write-Host ""
    Write-Host "  [*] Syncing Git Repository..." -ForegroundColor Red
    Write-Host ""
    
    $branch = git branch --show-current
    Write-Host "      Current branch: $branch" -ForegroundColor Yellow
    Write-Host ""
    
    Write-Host "      Fetching updates..." -ForegroundColor Gray
    git fetch origin
    Write-Host ""
    
    Write-Host "      Pulling latest changes..." -ForegroundColor Gray
    git pull origin $branch
    Write-Host ""
    
    $changes = git status --porcelain
    if ($changes) {
        Write-Host "      Changes detected:" -ForegroundColor Yellow
        git status --short
        Write-Host ""
        $choice = Read-Host "      Add and commit changes? (y/n)"
        if ($choice -eq "y") {
            git add .
            $msg = Read-Host "      Commit message"
            if ($msg) {
                git commit -m $msg
                Write-Host ""
                Write-Host "      Pushing to origin..." -ForegroundColor Gray
                git push origin $branch
            }
        }
    } else {
        Write-Host "      No changes detected" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "      Sync complete!" -ForegroundColor Green
    Read-Host "`nPress Enter to continue"
}

function Install-Dependencies {
    Write-Host ""
    Write-Host "  [*] Installing Dependencies..." -ForegroundColor Red
    Write-Host ""
    
    $requirements = @(
        "flask",
        "yt-dlp",
        "requests",
        "beautifulsoup4",
        "aiohttp",
        "colorama",
        "google-api-python-client",
        "psutil",
        "cryptography"
    )
    
    foreach ($pkg in $requirements) {
        Write-Host "      Installing $pkg..." -ForegroundColor Gray
        pip install $pkg -q 2>&1 | Out-Null
        Write-Host "      $pkg [OK]" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "      Dependencies installed!" -ForegroundColor Green
    Read-Host "`nPress Enter to continue"
}

function Start-Application {
    Write-Host ""
    Write-Host "  [*] Starting YTIMP4..." -ForegroundColor Red
    Write-Host ""
    
    if (Test-Path "ytimp4.py") {
        Write-Host "      Opening http://localhost:8080..." -ForegroundColor Yellow
        Start-Process "http://localhost:8080"
        Start-Process python -ArgumentList "ytimp4.py"
        Write-Host ""
        Write-Host "      Application started! Press Enter to return to menu." -ForegroundColor Green
    } else {
        Write-Host "      ytimp4.py not found!" -ForegroundColor Red
    }
    
    Read-Host "`nPress Enter to continue"
}

function Start-Bootstrap {
    Write-Host ""
    Write-Host "  [*] Running Bootstrap Setup..." -ForegroundColor Red
    Write-Host ""
    
    if (Test-Path "bootstrap.py") {
        Write-Host "      Running bootstrap.py..." -ForegroundColor Yellow
        python bootstrap.py
        Write-Host ""
        Write-Host "      Bootstrap complete!" -ForegroundColor Green
    } else {
        Write-Host "      bootstrap.py not found!" -ForegroundColor Red
    }
    
    Read-Host "`nPress Enter to continue"
}

function Get-Status {
    Write-Host ""
    Write-Host "  [*] Checking Status..." -ForegroundColor Red
    Write-Host ""
    
    $files = @(
        "ytimp4.py",
        "bootstrap.py",
        "requirements.txt",
        "start.bat",
        "config.json",
        "sync_updates.ps1"
    )
    
    Write-Host "      Project Files:" -ForegroundColor White
    foreach ($file in $files) {
        if (Test-Path $file) {
            Write-Host "        $file [OK]" -ForegroundColor Green
        } else {
            Write-Host "        $file [MISSING]" -ForegroundColor Red
        }
    }
    
    Write-Host ""
    Write-Host "      Folders:" -ForegroundColor White
    $folders = @("downloads", "archives", "static/icons", "templates", "servers", "sync", "debugging", "setup")
    foreach ($folder in $folders) {
        if (Test-Path $folder) {
            Write-Host "        $folder/ [OK]" -ForegroundColor Green
        } else {
            Write-Host "        $folder/ [MISSING]" -ForegroundColor Red
        }
    }
    
    Write-Host ""
    Write-Host "      Git Status:" -ForegroundColor Yellow
    git status --short
    
    Write-Host ""
    Write-Host "      Python Version:" -ForegroundColor Yellow
    python --version
    
    Read-Host "`nPress Enter to continue"
}

function Repair-CommonIssues {
    Write-Host ""
    Write-Host "  [*] Fixing Common Issues..." -ForegroundColor Red
    Write-Host ""
    
    Write-Host "      Creating missing directories..." -ForegroundColor Gray
    @("static/icons", "templates", "servers", "sync", "debugging", "setup", "downloads", "archives").ForEach({
        if (!(Test-Path $_)) {
            New-Item -ItemType Directory -Path $_ -Force | Out-Null
            Write-Host "        $_ [CREATED]" -ForegroundColor Green
        } else {
            Write-Host "        $_ [EXISTS]" -ForegroundColor Gray
        }
    })
    
    Write-Host ""
    Write-Host "      Checking requirements.txt..." -ForegroundColor Gray
    if (!(Test-Path "requirements.txt")) {
        @"
flask>=2.0.0
yt-dlp>=2023.0.0
requests>=2.25.0
beautifulsoup4>=4.9.0
aiohttp>=3.8.0
colorama>=0.4.4
google-api-python-client>=2.0.0
psutil>=5.8.0
cryptography>=3.4.0
"@ | Out-File -FilePath "requirements.txt" -Encoding UTF8
        Write-Host "        requirements.txt [CREATED]" -ForegroundColor Green
    } else {
        Write-Host "        requirements.txt [EXISTS]" -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "      Running pip install..." -ForegroundColor Gray
    pip install flask yt-dlp requests beautifulsoup4 aiohttp colorama google-api-python-client psutil cryptography -q
    
    Write-Host ""
    Write-Host "      Fixing git line endings..." -ForegroundColor Gray
    git config core.autocrlf true
    
    Write-Host ""
    Write-Host "      Done!" -ForegroundColor Green
    Read-Host "`nPress Enter to continue"
}

function Backup-Project {
    Write-Host ""
    Write-Host "  [*] Creating Backup..." -ForegroundColor Red
    
    $backupRoot = Join-Path $PWD "backups"
    if (!(Test-Path $backupRoot)) {
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
        Write-Host "      Created backups folder: $backupRoot" -ForegroundColor Gray
    }
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupFolder = Join-Path $backupRoot "backup_$timestamp"
    
    Write-Host "      Backup location: $backupFolder" -ForegroundColor Yellow
    
    New-Item -ItemType Directory -Path $backupFolder -Force | Out-Null
    
    $files = @(
        "ytimp4.py",
        "bootstrap.py",
        "requirements.txt",
        "start.bat",
        "config.json",
        "sync_updates.ps1"
    )
    
    $fileCount = 0
    foreach ($file in $files) {
        $source = Join-Path $PWD $file
        if (Test-Path $source) {
            $dest = Join-Path $backupFolder $file
            Copy-Item -Path $source -Destination $dest -Force
            Write-Host "        $file [OK]" -ForegroundColor Green
            $fileCount++
        } else {
            Write-Host "        $file [SKIPPED - not found]" -ForegroundColor Gray
        }
    }
    
    $folders = @("templates", "static", "servers", "sync", "downloads", "archives")
    $folderCount = 0
    foreach ($folder in $folders) {
        $source = Join-Path $PWD $folder
        if (Test-Path $source) {
            $dest = Join-Path $backupFolder $folder
            Copy-Item -Path $source -Destination $dest -Recurse -Force
            Write-Host "        $folder/ [OK]" -ForegroundColor Green
            $folderCount++
        } else {
            Write-Host "        $folder/ [SKIPPED - not found]" -ForegroundColor Gray
        }
    }
    
    $manifest = @"
Backup created: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Project: YTIMP4
Location: $PWD
Files backed up: $fileCount
Folders backed up: $folderCount
Total size: $(Get-ChildItem -Path $backupFolder -Recurse | Measure-Object -Property Length -Sum | ForEach-Object { [math]::Round($_.Sum / 1MB, 2) }) MB
"@
    $manifestPath = Join-Path $backupFolder "backup_manifest.txt"
    $manifest | Out-File -FilePath $manifestPath -Encoding UTF8
    
    Write-Host ""
    Write-Host "      Backup complete!" -ForegroundColor Green
    Write-Host "      Location: $backupFolder" -ForegroundColor Yellow
    Write-Host "      Files: $fileCount, Folders: $folderCount" -ForegroundColor Gray
    
    $openChoice = Read-Host "`n      Open backup folder? (y/n)"
    if ($openChoice -eq "y") {
        explorer $backupFolder
    }
    
    Read-Host "`nPress Enter to continue"
}

function Clear-Cache {
    Write-Host ""
    Write-Host "  [*] Cleaning Cache..." -ForegroundColor Red
    
    Write-Host "      Removing Python cache..." -ForegroundColor Gray
    Get-ChildItem -Path $PWD -Recurse -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $PWD -Recurse -Filter "__pycache__" -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "        Python cache cleaned" -ForegroundColor Green
    
    Write-Host "      Removing .venv..." -ForegroundColor Gray
    $venvPath = Join-Path $PWD ".venv"
    if (Test-Path $venvPath) {
        Remove-Item -Path $venvPath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "        .venv removed" -ForegroundColor Yellow
    } else {
        Write-Host "        .venv not found" -ForegroundColor Gray
    }
    
    Write-Host "      Removing .vscode cache..." -ForegroundColor Gray
    $vscodePath = Join-Path $PWD ".vscode"
    if (Test-Path $vscodePath) {
        Remove-Item -Path $vscodePath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "        .vscode removed" -ForegroundColor Yellow
    } else {
        Write-Host "        .vscode not found" -ForegroundColor Gray
    }
    
    Write-Host "      Removing temp files..." -ForegroundColor Gray
    Get-ChildItem -Path $PWD -Filter "temp_*.db" | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $PWD -Filter "*.log" | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "        Temp files cleaned" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "      Cache cleaned!" -ForegroundColor Green
    Read-Host "`nPress Enter to continue"
}

function Open-Explorer {
    Write-Host ""
    Write-Host "  [*] Opening Explorer..." -ForegroundColor Red
    explorer .
    Read-Host "`nPress Enter to continue"
}

$scriptPath = $MyInvocation.MyCommand.Path
$policy = Get-ExecutionPolicy
if ($policy -eq "Restricted" -or $policy -eq "AllSigned") {
    Write-Host "Execution policy is $policy. Restarting with bypass..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList "-ExecutionPolicy Bypass -File `"$scriptPath`"" -Wait
    exit
}

do {
    Show-Menu
    $choice = Read-Host "Select option (1-10)"
    
    switch ($choice) {
        "1" { Sync-Git }
        "2" { Install-Dependencies }
        "3" { Start-Application }
        "4" { Start-Bootstrap }
        "5" { Get-Status }
        "6" { Repair-CommonIssues }
        "7" { Backup-Project }
        "8" { Clear-Cache }
        "9" { Open-Explorer }
        "10" { Write-Host "`n  [*] Goodbye!" -ForegroundColor Green }
        default { Write-Host "`n      Invalid option. Please choose 1-10." -ForegroundColor Red }
    }
} while ($choice -ne "10")