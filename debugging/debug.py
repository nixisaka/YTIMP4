#!/usr/bin/env python3
import subprocess
import sys
import os
import platform
from pathlib import Path

def find_project_root():
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "ytimp4.py").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent

def check_requirements():
    req_file = PROJECT_ROOT / "requirements.txt"
    if not req_file.exists():
        print("  [WARN] requirements.txt not found")
        return False
    print(f"  [OK] requirements.txt found")
    return True

def check_ffmpeg():
    ffmpeg_path = PROJECT_ROOT / "ffmpeg.exe"
    if not ffmpeg_path.exists():
        print("  [WARN] ffmpeg.exe not found")
        return False
    print(f"  [OK] ffmpeg.exe found ({ffmpeg_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return True

def check_venv():
    venv_paths = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "bin" / "python",
    ]
    for venv_path in venv_paths:
        if venv_path.exists():
            print(f"  [OK] Virtual environment found at {venv_path.parent.parent}")
            return True
    print("  [WARN] No virtual environment found")
    return False

def main():
    global PROJECT_ROOT
    PROJECT_ROOT = find_project_root()
    
    print("=" * 60)
    print("YTIMP4 Debug Mode")
    print("=" * 60)
    print(f"Project directory: {PROJECT_ROOT}")
    print(f"Platform: {platform.system()}")
    print(f"Python: {sys.version}")
    print()
    
    print("Checking project files:")
    check_ffmpeg()
    check_requirements()
    check_venv()
    print()
    
    ytimp4_path = PROJECT_ROOT / "ytimp4.py"
    
    if not ytimp4_path.exists():
        print(f"Error: ytimp4.py not found at {ytimp4_path}")
        sys.exit(1)
    
    venv_python = None
    venv_paths = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "bin" / "python",
    ]
    
    for venv_path in venv_paths:
        if venv_path.exists():
            venv_python = str(venv_path)
            print(f"Using virtual environment Python: {venv_python}")
            break
    
    python_exe = venv_python if venv_python else sys.executable
    
    cmd = [python_exe, str(ytimp4_path), "--port", "8080"]
    
    print(f"\nRunning: {' '.join(cmd)}")
    print()
    print("=" * 60)
    print("YTIMP4 is starting... (Press Ctrl+C to stop)")
    print("=" * 60)
    print()
    
    try:
        if platform.system() == "Windows":
            process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            print(f"Process started with PID: {process.pid}")
            print("You can close this window, YTIMP4 will keep running")
            print()
            print("Press Ctrl+C to stop the process...")
            process.wait()
        else:
            subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        if 'process' in locals():
            process.terminate()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("YTIMP4 has stopped")
    print("=" * 60)
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()