#!/usr/bin/env python3
import subprocess
import sys
import os
import platform
import time
import locale
import socket
import webbrowser
import shutil
import importlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from importlib import import_module
from pkgutil import iter_modules
from pathlib import Path

DEBUG = os.environ.get('YTIMP4_DEBUG', '0') == '1'
SELF_HEAL = os.environ.get('YTIMP4_SELF_HEAL', '1') == '1'
SPOOF_MODE = os.environ.get('YTIMP4_SPOOF', '0') == '1'

def debug_log(msg):
    if DEBUG:
        timestamp = time.strftime("%H:%M:%S")
        print(f"[DEBUG {timestamp}] {msg}")

def find_project_root():
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "ytimp4.py").exists():
            debug_log(f"Found project root at {current}")
            return current
        current = current.parent
    debug_log(f"Using current directory as project root: {Path(__file__).resolve().parent}")
    return Path(__file__).resolve().parent

PROJECT_ROOT = find_project_root()
SETUP_DIR = Path(__file__).resolve().parent

debug_log(f"PROJECT_ROOT: {PROJECT_ROOT}")
debug_log(f"SETUP_DIR: {SETUP_DIR}")

os.chdir(PROJECT_ROOT)

def is_admin():
    if platform.system() == "Windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    else:
        try:
            return os.geteuid() == 0
        except:
            return False

ADMIN = is_admin()
debug_log(f"Admin privileges: {ADMIN}")

if not ADMIN:
    print("Running without administrator privileges.")
    print("The application will still work normally.\n")

try:
    from colorama import init, Fore, Style
    init()
    COLORS = True
    debug_log("Colorama loaded successfully")
except ImportError:
    COLORS = False
    debug_log("Colorama not found, installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "colorama", "-q"])
    from colorama import init, Fore, Style
    init()
    COLORS = True
    debug_log("Colorama installed and loaded")

def print_colored(text, color=None):
    if COLORS and color:
        if color == "red":
            print(Fore.RED + text + Style.RESET_ALL)
        elif color == "white":
            print(Fore.WHITE + text + Style.RESET_ALL)
        elif color == "gray":
            print(Fore.LIGHTBLACK_EX + text + Style.RESET_ALL)
        elif color == "yellow":
            print(Fore.YELLOW + text + Style.RESET_ALL)
        elif color == "green":
            print(Fore.GREEN + text + Style.RESET_ALL)
        else:
            print(text)
    else:
        print(text)

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
os.environ['PIP_NO_CACHE_DIR'] = '1'
os.environ['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'

if platform.system() == "Windows":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass
else:
    locale.setlocale(locale.LC_ALL, 'C.UTF-8')

installed_cache = {}

def is_package_installed(package_name):
    if package_name in installed_cache:
        debug_log(f"Package {package_name} in cache: {installed_cache[package_name]}")
        return installed_cache[package_name]
    
    base_name = package_name.replace('-', '_').split('[')[0].split('>')[0].split('<')[0]
    debug_log(f"Checking package: {package_name} (base: {base_name})")
    
    if SPOOF_MODE:
        debug_log(f"SPOOF MODE: Pretending {package_name} is installed")
        installed_cache[package_name] = True
        return True
    
    try:
        import_module(base_name)
        installed_cache[package_name] = True
        debug_log(f"Package {package_name} is installed")
        return True
    except ImportError as e:
        installed_cache[package_name] = False
        debug_log(f"Package {package_name} not installed: {e}")
        
        if SELF_HEAL and not SPOOF_MODE:
            debug_log(f"Self-healing: Attempting to install {package_name}")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", package_name, "-q", "--no-cache-dir"], 
                             capture_output=True, timeout=60)
                try:
                    import_module(base_name)
                    installed_cache[package_name] = True
                    debug_log(f"Self-heal successful for {package_name}")
                    return True
                except ImportError:
                    pass
            except Exception as heal_err:
                debug_log(f"Self-heal failed for {package_name}: {heal_err}")
        
        return False

def parse_requirements(requirements_path):
    debug_log(f"Parsing requirements from {requirements_path}")
    if not os.path.exists(requirements_path):
        debug_log(f"Requirements file not found: {requirements_path}")
        return []
    
    packages = []
    try:
        with open(requirements_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('--'):
                    match = re.match(r'^([a-zA-Z0-9\-_]+)', line)
                    if match:
                        packages.append(match.group(1))
                        debug_log(f"  Line {line_num}: found package {match.group(1)}")
    except Exception as e:
        debug_log(f"Error parsing requirements: {e}")
    
    debug_log(f"Total packages found: {len(packages)}")
    return packages

def check_missing_packages_parallel(requirements_path, max_workers=8):
    debug_log(f"Checking missing packages with {max_workers} workers")
    if not os.path.exists(requirements_path):
        debug_log(f"Requirements file not found: {requirements_path}")
        return []
    
    packages = parse_requirements(requirements_path)
    if not packages:
        debug_log("No packages found in requirements")
        return []
    
    print_colored(f"  Checking {len(packages)} packages...", "gray")
    debug_log(f"Checking {len(packages)} packages...")
    
    missing = []
    checked = 0
    lock = threading.Lock()
    
    def check_package(pkg):
        nonlocal checked
        debug_log(f"Checking package: {pkg}")
        if not is_package_installed(pkg):
            with lock:
                missing.append(pkg)
                debug_log(f"Package {pkg} is MISSING")
        with lock:
            checked += 1
            if checked % 20 == 0 or checked == len(packages):
                print_colored(f"    Checked {checked}/{len(packages)} packages...", "gray")
                debug_log(f"Progress: {checked}/{len(packages)}")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(check_package, pkg) for pkg in packages]
        for future in as_completed(futures):
            future.result()
    
    debug_log(f"Found {len(missing)} missing packages: {missing}")
    
    if SPOOF_MODE and missing:
        print_colored(f"  SPOOF MODE: Ignoring {len(missing)} missing packages", "yellow")
        return []
    
    print_colored(f"  Found {len(missing)} missing packages", "yellow" if missing else "green")
    return missing

def install_packages_parallel(python_exe, packages, max_workers=8):
    debug_log(f"Installing {len(packages)} packages with {max_workers} workers")
    if not packages:
        return
    
    if SPOOF_MODE:
        print_colored(f"\n  SPOOF MODE: Skipping installation of {len(packages)} packages", "yellow")
        return
    
    print_colored(f"\n  Installing {len(packages)} package(s) in parallel ({max_workers} workers)...", "white")
    
    installed_count = 0
    failed_count = 0
    lock = threading.Lock()
    
    def install_package(pkg):
        nonlocal installed_count, failed_count
        debug_log(f"Installing package: {pkg}")
        try:
            result = subprocess.run(
                [python_exe, "-m", "pip", "install", pkg, "-q", "--no-cache-dir", "--no-deps"],
                capture_output=True,
                timeout=90
            )
            with lock:
                if result.returncode == 0:
                    installed_count += 1
                    debug_log(f"Successfully installed {pkg}")
                    print_colored(f"    [{installed_count + failed_count}/{len(packages)}] + {pkg}", "green")
                else:
                    failed_count += 1
                    debug_log(f"Failed to install {pkg} (attempt 1): {result.stderr[:200]}")
                    print_colored(f"    [{installed_count + failed_count}/{len(packages)}] ? {pkg} (retrying)", "yellow")
                    retry_result = subprocess.run(
                        [python_exe, "-m", "pip", "install", pkg, "-q", "--no-cache-dir"],
                        capture_output=True,
                        timeout=120
                    )
                    if retry_result.returncode == 0:
                        with lock:
                            installed_count += 1
                            failed_count -= 1
                            debug_log(f"Successfully installed {pkg} on retry")
                            print_colored(f"    [{installed_count + failed_count}/{len(packages)}] + {pkg} (retry)", "green")
        except Exception as e:
            with lock:
                failed_count += 1
                debug_log(f"Exception installing {pkg}: {e}")
                print_colored(f"    [{installed_count + failed_count}/{len(packages)}] x {pkg}: {str(e)[:40]}", "red")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(install_package, pkg) for pkg in packages]
        for future in as_completed(futures):
            future.result()
    
    debug_log(f"Installation complete: {installed_count} installed, {failed_count} failed")
    print_colored(f"\n  Installation complete: {installed_count} installed, {failed_count} failed", 
                  "green" if failed_count == 0 else "yellow")

def repair_pip():
    debug_log("Checking pip health")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            debug_log("pip is broken, attempting repair")
            print_colored("  pip is broken. Attempting repair...", "yellow")
            subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], capture_output=True)
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], capture_output=True)
            debug_log("pip repair attempted")
            return True
    except Exception as e:
        debug_log(f"pip check failed: {e}")
    return True

def create_requirements_if_missing():
    requirements_path = PROJECT_ROOT / "requirements.txt"
    if not requirements_path.exists():
        debug_log("requirements.txt missing, creating default")
        default_requirements = [
            "flask>=2.0.0",
            "flask-cors>=4.0.0",
            "yt-dlp>=2023.0.0",
            "requests>=2.25.0",
            "beautifulsoup4>=4.9.0",
            "aiohttp>=3.8.0",
            "colorama>=0.4.4",
            "psutil>=5.8.0",
            "cryptography>=3.4.0"
        ]
        with open(requirements_path, 'w') as f:
            f.write("\n".join(default_requirements))
        debug_log("Created default requirements.txt")
        return True
    return False

def check_and_fix_venv():
    venv_path = PROJECT_ROOT / ".venv"
    if venv_path.exists():
        python_exe = venv_path / "Scripts" / "python.exe" if platform.system() == "Windows" else venv_path / "bin" / "python"
        if not python_exe.exists():
            debug_log("Venv exists but python missing, recreating")
            shutil.rmtree(venv_path)
            return False
    return venv_path.exists()

def check_deno_installed():
    debug_log("Checking Deno installation")
    try:
        result = subprocess.run(["deno", "--version"], check=True, capture_output=True)
        debug_log(f"Deno found: {result.stdout[:100]}")
        return True
    except Exception as e:
        debug_log(f"Deno not found: {e}")
        return False

def install_deno():
    print_colored("\nChecking Deno...", "white")
    debug_log("Installing Deno")
    
    if check_deno_installed():
        print_colored("  Deno already installed [OK]", "green")
        debug_log("Deno already installed")
        return True
    
    print_colored("  Deno not found. Installing...", "yellow")
    debug_log("Deno not found, starting installation")
    
    if platform.system() == "Windows":
        debug_log("Installing Deno via PowerShell")
        subprocess.run(["powershell", "-Command", "irm https://deno.land/install.ps1 | iex"], 
                      capture_output=True)
    else:
        debug_log("Installing Deno via curl")
        subprocess.run(["curl", "-fsSL", "https://deno.land/install.sh", "|", "sh"], 
                      shell=True, capture_output=True)
    
    if check_deno_installed():
        print_colored("  Deno installed successfully [OK]", "green")
        debug_log("Deno installed successfully")
        return True
    else:
        print_colored("  Deno installation failed. Continuing without Deno...", "yellow")
        debug_log("Deno installation failed")
        return False

def find_free_port():
    debug_log("Finding free port")
    for port in range(8080, 8090):
        sock = socket.socket()
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result != 0:
            debug_log(f"Found free port: {port}")
            return port
    debug_log("No free port found, using 8080")
    return 8080

def check_python():
    print_colored("Checking Python installation...", "white")
    debug_log("Checking Python installation")
    try:
        result = subprocess.run([sys.executable, "--version"], check=True, capture_output=True)
        debug_log(f"Python found: {result.stdout.decode().strip()}")
        print_colored("  Python found [OK]", "green")
        return True
    except Exception as e:
        debug_log(f"Python not found: {e}")
        print_colored("  Python not found. Please install Python from python.org", "red")
        webbrowser.open("https://python.org/downloads/")
        input("Press Enter after installing Python...")
        return check_python()

def check_venv_healthy(python_exe):
    debug_log(f"Checking venv health: {python_exe}")
    try:
        result = subprocess.run([python_exe, "-c", "import site; print(1)"], capture_output=True, text=True)
        is_healthy = result.returncode == 0
        debug_log(f"Venv healthy: {is_healthy}")
        return is_healthy
    except Exception as e:
        debug_log(f"Venv check exception: {e}")
        return False

def kill_existing_server(port):
    debug_log(f"Killing existing server on port {port}")
    if platform.system() == "Windows":
        result = subprocess.run(f"netstat -ano | findstr :{port}", shell=True, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                debug_log(f"Killing process {pid}")
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)

def cleanup_conflicting_files():
    debug_log("Cleaning up conflicting files")
    googleapi_path = PROJECT_ROOT / "googleapi.py"
    if googleapi_path.exists():
        debug_log(f"Removing {googleapi_path}")
        print_colored("Removing conflicting googleapi.py file...", "yellow")
        googleapi_path.unlink()
    
    googleapi_folder = PROJECT_ROOT / "googleapi"
    if googleapi_folder.exists() and googleapi_folder.is_dir():
        debug_log(f"Removing {googleapi_folder}")
        print_colored("Removing conflicting googleapi folder...", "yellow")
        shutil.rmtree(googleapi_folder)

def add_firewall_rule():
    if ADMIN and platform.system() == "Windows":
        debug_log("Adding firewall rule")
        print_colored("Adding Windows Firewall rule...", "gray")
        subprocess.run('netsh advfirewall firewall add rule name="YTIMP4" dir=in action=allow program="%USERPROFILE%\\.venv\\Scripts\\python.exe" enable=yes', shell=True, capture_output=True)
    else:
        debug_log("Skipping firewall rule (no admin)")
        print_colored("Skipping firewall rule (admin required)", "gray")

def open_browser(url):
    debug_log(f"Opening browser with URL: {url}")
    webbrowser.open(url)
    print_colored(f"Opened browser with {url}", "white")

def get_python_exe():
    debug_log("Getting Python executable path")
    venv_paths = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "bin" / "python",
        PROJECT_ROOT / "setup" / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / "setup" / ".venv" / "bin" / "python",
    ]
    
    for venv_path in venv_paths:
        if venv_path.exists():
            debug_log(f"Found Python at {venv_path}")
            return str(venv_path)
    
    debug_log(f"Using system Python: {sys.executable}")
    return sys.executable

def main():
    if SPOOF_MODE:
        print_colored("\n[SPOOF MODE ENABLED] - Bypassing missing packages", "yellow")
    if DEBUG:
        print_colored("\n[DEBUG MODE ENABLED]", "yellow")
        print_colored("Detailed logs will be shown below\n", "yellow")
    
    print_colored("", "white")
    print_colored("    __    __  ______  ______            ____    __ __", "red")
    print_colored("   /\\ \\  /\\ \\/\\__  _\\/\\__  _\\   /'\\_/`\\/\\  _`\\ /\\ \\\\ \\", "white")
    print_colored("   \\ `\\`\\\\/'/'\\/_/\\ \\/\\/_/\\ \\/  /\\      \\ \\ \\L\\ \\ \\ \\\\ \\", "white")
    print_colored("    `\\`\\ /'    \\ \\ \\   \\ \\ \\  \\ \\ \\__\\ \\ \\ ,__/\\ \\ \\\\ \\_", "red")
    print_colored("      `\\ \\ \\     \\ \\ \\   \\_\\ \\__\\ \\ \\_/\\ \\ \\ \\/  \\ \\__ ,__\\", "gray")
    print_colored("        \\ \\_\\     \\ \\_\\  /\\_____\\\\ \\_\\\\ \\_\\ \\_\\   \\/_/\\_\\_/", "gray")
    print_colored("         \\/_/      \\/_/  \\/_____/ \\/_/ \\/_/\\/_/      \\/_/", "red")
    print_colored("", "white")
    print_colored("=================================================================================", "red")
    print_colored(">>  YTIMP4 - YouTube Downloader", "white")
    print_colored("Developed by Livia", "white")
    print_colored("MIT LICENSE", "red")
    print_colored("This software is licensed under the MIT License.", "white")
    print_colored("You are free to use, modify, and distribute this software", "white")
    print_colored("for any purpose, provided that you include the original", "white")
    print_colored("copyright notice and this permission notice in all copies", "white")
    print_colored("or substantial portions of the software.", "white")
    print_colored("=================================================================================", "red")
    print_colored("", "white")
    
    repair_pip()
    create_requirements_if_missing()
    
    check_python()
    install_deno()
    
    cleanup_conflicting_files()
    
    venv_path = PROJECT_ROOT / ".venv"
    
    if platform.system() == "Windows":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"
    
    if venv_path.exists() and python_exe.exists():
        if check_venv_healthy(str(python_exe)):
            print_colored("Virtual environment checked and ready to go", "white")
        else:
            debug_log("Venv corrupted, recreating")
            print_colored("Virtual environment is corrupted. Recreating...", "yellow")
            shutil.rmtree(venv_path)
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)])
    else:
        debug_log("Creating new venv")
        print_colored("Creating virtual environment...", "yellow")
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)])
    
    python_exe = get_python_exe()
    
    requirements_path = PROJECT_ROOT / "requirements.txt"
    
    if requirements_path.exists():
        missing = check_missing_packages_parallel(str(requirements_path), max_workers=8)
        
        if missing and not SPOOF_MODE:
            install_packages_parallel(python_exe, missing, max_workers=8)
        elif not missing:
            print_colored("\n  All packages already installed! [OK]", "green")
        elif SPOOF_MODE:
            print_colored(f"\n  SPOOF MODE: Skipped {len(missing)} missing packages", "yellow")
    else:
        debug_log(f"Requirements file not found at {requirements_path}")
        print_colored(f"\n  No requirements.txt found at {requirements_path}", "yellow")
    
    add_firewall_rule()
    
    ytimp4_path = PROJECT_ROOT / "ytimp4.py"
    
    if not ytimp4_path.exists():
        debug_log(f"ytimp4.py not found at {ytimp4_path}")
        print_colored(f"\nError: ytimp4.py not found at {ytimp4_path}", "red")
        print_colored("Please ensure ytimp4.py is in the project root directory", "yellow")
        input("Press Enter to exit...")
        sys.exit(1)
    
    port = find_free_port()
    kill_existing_server(port)
    
    print_colored(f"\nStarting YTIMP4 on port {port}...", "red")
    
    open_browser(f"http://localhost:{port}")
    
    if platform.system() == "Windows":
        debug_log(f"Launching {python_exe} {ytimp4_path} --port {port}")
        subprocess.Popen([python_exe, str(ytimp4_path), "--port", str(port)])
    else:
        debug_log(f"Launching {python_exe} {ytimp4_path} --port {port}")
        subprocess.Popen([python_exe, str(ytimp4_path), "--port", str(port)])
    
    print_colored("\nYTIMP4 is running!", "white")
    print_colored(f"If browser didn't open, manually go to http://localhost:{port}", "yellow")
    print_colored("You can close this window, the app will keep running", "gray")
    
    if DEBUG:
        print_colored("\n[DEBUG MODE] Press Ctrl+C to stop debugging", "yellow")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        debug_log("Shutting down due to keyboard interrupt")
        print_colored("\nShutting down...", "red")

if __name__ == "__main__":
    main()