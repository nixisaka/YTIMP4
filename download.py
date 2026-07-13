#!/usr/bin/env python3
import os
import subprocess
import sys
import re
import time
import json
import threading
import sqlite3
import shutil
import urllib.parse
import argparse
import urllib.request
import zipfile
from pathlib import Path
from flask import Flask, render_template_string, request, send_file, jsonify
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

DOWNLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

ARCHIVE_FOLDER = os.path.join(os.path.dirname(__file__), "archives")
os.makedirs(ARCHIVE_FOLDER, exist_ok=True)

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

download_progress = {}
download_files = {}
download_queue = []
active_downloads = 0
active_lock = threading.Lock()
max_concurrent = 3

cpu_count = os.cpu_count() or 4

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        "youtube_api_key": "",
        "download_queue": [],
        "settings": {
            "max_concurrent_downloads": 3,
            "default_format": "mp4",
            "default_quality": "best",
            "save_subtitles": False,
            "subtitle_language": "en"
        }
    }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

config = load_config()
YOUTUBE_API_KEY = config.get("youtube_api_key", "")
download_queue = config.get("download_queue", [])
max_concurrent = config.get("settings", {}).get("max_concurrent_downloads", 3)

def save_queue():
    config["download_queue"] = download_queue
    save_config(config)

def convert_vtt_to_srt(vtt_path, srt_path):
    try:
        with open(vtt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        start_idx = 0
        for i, line in enumerate(lines):
            if '-->' in line:
                start_idx = max(0, i - 1)
                break
        
        cleaned_lines = []
        for line in lines[start_idx:]:
            if line.strip() and not line.strip().startswith('NOTE'):
                if 'align:' in line and '-->' not in line:
                    continue
                cleaned_lines.append(line.rstrip())
        
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cleaned_lines))
        
        if os.path.exists(vtt_path):
            os.remove(vtt_path)
        
        return True
    except Exception as e:
        logger.error(f"Error converting VTT to SRT: {e}")
        return False

def download_subtitles(video_id, language='en'):
    try:
        output_template = os.path.join(DOWNLOAD_FOLDER, f"{video_id}.%(ext)s")
        
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--write-subs",
            "--sub-lang", language,
            "--skip-download",
            "--sub-format", "vtt",
            "-o", output_template,
            f"https://www.youtube.com/watch?v={video_id}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        possible_files = [
            os.path.join(DOWNLOAD_FOLDER, f"{video_id}.{language}.vtt"),
            os.path.join(DOWNLOAD_FOLDER, f"{video_id}.vtt"),
            os.path.join(DOWNLOAD_FOLDER, f"{video_id}.en.vtt"),
        ]
        
        for sub_file in possible_files:
            if os.path.exists(sub_file) and os.path.getsize(sub_file) > 0:
                srt_file = sub_file.replace('.vtt', '.srt')
                if convert_vtt_to_srt(sub_file, srt_file):
                    return srt_file
                return sub_file
        
        return None
        
    except subprocess.TimeoutExpired:
        logger.error(f"Subtitle download timeout for {video_id}")
        return None
    except Exception as e:
        logger.error(f"Subtitle download error: {e}")
        return None

def check_deno():
    try:
        subprocess.run(["deno", "--version"], capture_output=True)
        return True
    except:
        return False

def check_ffmpeg():
    ffmpeg_paths = [
        "ffmpeg.exe",
        os.path.join(os.path.dirname(__file__), "ffmpeg.exe"),
        shutil.which("ffmpeg")
    ]
    
    for p in ffmpeg_paths:
        if p and os.path.exists(p):
            return p
    
    if sys.platform == 'win32':
        try:
            ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            zip_path = os.path.join(os.path.dirname(__file__), "ffmpeg.zip")
            ffmpeg_exe = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
            
            print("Downloading ffmpeg...")
            urllib.request.urlretrieve(ffmpeg_url, zip_path)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file in zip_ref.namelist():
                    if file.endswith("ffmpeg.exe"):
                        with zip_ref.open(file) as source, open(ffmpeg_exe, 'wb') as target:
                            target.write(source.read())
                        break
            
            os.remove(zip_path)
            print("FFmpeg downloaded successfully")
            return ffmpeg_exe
        except Exception as e:
            print(f"Failed to download ffmpeg: {e}")
            return None
    
    return None

def get_browser_cookies():
    cookies_found = []
    local_app_data = Path(os.environ.get('LOCALAPPDATA', ''))
    roaming_app_data = Path(os.environ.get('APPDATA', ''))

    if local_app_data:
        chrome_path = local_app_data / 'Google' / 'Chrome' / 'User Data' / 'Default' / 'Cookies'
        if chrome_path.exists():
            try:
                temp_db = os.path.join(os.path.dirname(__file__), 'temp_cookies.db')
                shutil.copy2(chrome_path, temp_db)
                conn = sqlite3.connect(temp_db)
                c = conn.cursor()
                c.execute("SELECT name, value, host_key, path, is_secure, expires_utc FROM cookies WHERE host_key LIKE '%youtube.com%' OR host_key LIKE '%google.com%'")
                cookies = c.fetchall()
                conn.close()
                os.remove(temp_db)
                if cookies:
                    cookies_found.append(('Chrome', [(c[0], c[1], c[2], c[3], c[4], c[5]) for c in cookies]))
            except:
                pass

    if roaming_app_data:
        firefox_path = roaming_app_data / 'Mozilla' / 'Firefox' / 'Profiles'
        if firefox_path.exists():
            for profile in firefox_path.iterdir():
                if profile.is_dir():
                    cookie_db = profile / 'cookies.sqlite'
                    if cookie_db.exists():
                        try:
                            temp_db = os.path.join(os.path.dirname(__file__), 'temp_cookies.db')
                            shutil.copy2(cookie_db, temp_db)
                            conn = sqlite3.connect(temp_db)
                            c = conn.cursor()
                            c.execute("SELECT name, value, host, path, isSecure, expiry FROM moz_cookies WHERE host LIKE '%youtube.com%' OR host LIKE '%google.com%'")
                            cookies = c.fetchall()
                            conn.close()
                            os.remove(temp_db)
                            if cookies:
                                cookies_found.append(('Firefox', [(c[0], c[1], c[2], c[3], c[4], c[5]) for c in cookies]))
                                break
                        except:
                            continue
    return cookies_found

def save_cookies(cookies):
    with open(COOKIE_FILE, 'w') as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n\n")
        for name, value, host, path, is_secure, expiry in cookies:
            secure_flag = 'TRUE' if is_secure else 'FALSE'
            domain = host if host.startswith('.') else '.' + host
            f.write(f"{domain}\tTRUE\t{path}\t{secure_flag}\t{expiry}\t{name}\t{value}\n")

def clear_cookies():
    try:
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)
        return True
    except:
        return False

def extract_video_id(url):
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/live/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})'
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def process_queue():
    global active_downloads
    
    with active_lock:
        while download_queue and active_downloads < max_concurrent:
            item = download_queue.pop(0)
            active_downloads += 1
            thread = threading.Thread(
                target=run_ytdlp_download,
                args=(item['cmd'], item['download_id'], item['output'], 
                      item.get('video_id', ''), item.get('quality', 'best'), 
                      item.get('title', ''))
            )
            thread.daemon = True
            thread.start()
    
    save_queue()

def add_to_queue(cmd, download_id, output, video_id, quality, title):
    download_queue.append({
        'cmd': cmd,
        'download_id': download_id,
        'output': output,
        'video_id': video_id,
        'quality': quality,
        'title': title
    })
    save_queue()
    process_queue()

def run_ytdlp_download(cmd, download_id, output_path, video_id='', quality='best', title=''):
    global active_downloads
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        def read_stream(stream, is_stderr=False):
            for line in iter(stream.readline, ''):
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                
                percent_match = re.search(r'(\d+(?:\.\d+)?)%', line)
                speed_match = re.search(r'(\d+(?:\.\d+)?\s*[kKMGT]?B/s)', line)
                eta_match = re.search(r'ETA\s+(\d+(?::\d+)?(?::\d+)?)', line)
                
                if percent_match:
                    percent = float(percent_match.group(1))
                    speed = speed_match.group(1) if speed_match else ''
                    eta = eta_match.group(1) if eta_match else ''
                    download_progress[download_id] = {
                        'percent': percent, 
                        'speed': speed, 
                        'eta': eta, 
                        'completed': False
                    }
                elif is_stderr and 'ERROR' in line:
                    logger.error(f"Download error: {line}")
                    download_progress[download_id] = {'percent': 0, 'error': line, 'completed': False}
            
            stream.close()
        
        stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, False))
        stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, True))
        stdout_thread.start()
        stderr_thread.start()
        
        return_code = process.wait()
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        
        if return_code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            download_progress[download_id] = {'percent': 100, 'completed': True}
            download_files[download_id] = output_path
            logger.info(f"Download completed: {output_path}")
            
            save_subtitles = config.get("settings", {}).get("save_subtitles", False)
            if save_subtitles and video_id:
                subtitle_lang = config.get("settings", {}).get("subtitle_language", "en")
                threading.Thread(target=download_subtitles, args=(video_id, subtitle_lang)).start()
        else:
            error_msg = f"Download failed with code {return_code}"
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass
            download_progress[download_id] = {'percent': 0, 'error': error_msg, 'completed': True}
            logger.error(error_msg)
            
    except Exception as e:
        logger.error(f"Download exception: {e}")
        download_progress[download_id] = {'percent': 0, 'error': str(e), 'completed': True}
    finally:
        with active_lock:
            active_downloads -= 1
        process_queue()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    
    if os.path.exists(COOKIE_FILE):
        os.remove(COOKIE_FILE)
    
    process_queue()
    
    print(f"YTIMP4 - CPU cores: {cpu_count}, Deno: {check_deno()}, FFmpeg: {check_ffmpeg()}")
    print(f"Archive folder: {ARCHIVE_FOLDER}")
    print(f"Server running on http://localhost:{args.port}")
    
    app.run(host='127.0.0.1', port=args.port, debug=False, threaded=True)

if __name__ == '__main__':
    main()
