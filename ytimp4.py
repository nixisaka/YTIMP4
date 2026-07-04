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
from flask import Flask, render_template, request, send_file, jsonify
import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {
            "youtube_api_key": "AIzaSyBXTPfHXAiof-IlskrPVWarp2j37TAKdW0",
            "download_queue": [],
            "settings": {
                "max_concurrent_downloads": 3,
                "default_format": "mp4",
                "default_quality": "best",
                "save_subtitles": False,
                "subtitle_language": "en"
            }
        }
    
    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key, default=None):
        return self.config.get(key, default)


class CookieManager:
    def __init__(self, cookie_file):
        self.cookie_file = cookie_file
    
    def get_browser_cookies(self):
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
    
    def save_cookies(self, cookies):
        with open(self.cookie_file, 'w') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n\n")
            for name, value, host, path, is_secure, expiry in cookies:
                secure_flag = 'TRUE' if is_secure else 'FALSE'
                domain = host if host.startswith('.') else '.' + host
                f.write(f"{domain}\tTRUE\t{path}\t{secure_flag}\t{expiry}\t{name}\t{value}\n")
    
    def clear_cookies(self):
        try:
            if os.path.exists(self.cookie_file):
                os.remove(self.cookie_file)
            return True
        except:
            return False
    
    def scan_and_save(self):
        browsers = self.get_browser_cookies()
        for browser_name, cookies in browsers:
            if cookies:
                self.save_cookies(cookies)
                return {'success': True, 'browser': browser_name}
        return {'success': False}
    
    def is_authenticated(self):
        if os.path.exists(self.cookie_file) and os.path.getsize(self.cookie_file) > 0:
            with open(self.cookie_file, 'r') as f:
                if 'LOGIN_INFO' in f.read():
                    return True
        return False


class DownloadManager:
    def __init__(self, download_folder, cookie_file, config_manager):
        self.download_folder = download_folder
        self.cookie_file = cookie_file
        self.config_manager = config_manager
        self.download_progress = {}
        self.download_files = {}
        self.download_queue = []
        self.active_downloads = 0
        self.active_lock = threading.Lock()
        self.cpu_count = os.cpu_count() or 4
    
    def extract_video_id(self, url):
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
    
    def check_deno(self):
        try:
            subprocess.run(["deno", "--version"], capture_output=True)
            return True
        except:
            return False
    
    def check_ffmpeg(self):
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
    
    def get_video_info(self, url):
        video_id = self.extract_video_id(url)
        if not video_id:
            return {'error': 'Invalid URL'}
        if not os.path.exists(self.cookie_file):
            return {'error': 'No cookies. Scan browsers first.'}
        
        deno = self.check_deno()
        cmd = [sys.executable, "-m", "yt_dlp", "--cookies", self.cookie_file, "--no-playlist", "--dump-json", f"https://www.youtube.com/watch?v={video_id}"]
        if deno:
            cmd.extend(["--js-runtimes", "deno", "--remote-components", "ejs:npm"])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return {'error': f'yt-dlp error: {result.stderr[:200]}'}
            data = json.loads(result.stdout)
            return {
                'video_id': video_id,
                'title': data.get('title', 'Unknown'),
                'thumbnail': data.get('thumbnail', f'https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg'),
                'isLive': data.get('is_live', False),
                'uploader': data.get('uploader', 'YouTube')
            }
        except Exception as e:
            return {'error': str(e)}
    
    def download_subtitles(self, video_id, language='en'):
        try:
            output_template = os.path.join(self.download_folder, f"{video_id}.%(ext)s")
            
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
                os.path.join(self.download_folder, f"{video_id}.{language}.vtt"),
                os.path.join(self.download_folder, f"{video_id}.vtt"),
                os.path.join(self.download_folder, f"{video_id}.en.vtt"),
            ]
            
            for sub_file in possible_files:
                if os.path.exists(sub_file) and os.path.getsize(sub_file) > 0:
                    return sub_file
            
            return None
            
        except subprocess.TimeoutExpired:
            logger.error(f"Subtitle download timeout for {video_id}")
            return None
        except Exception as e:
            logger.error(f"Subtitle download error: {e}")
            return None
    
    def process_queue(self):
        with self.active_lock:
            max_concurrent = self.config_manager.get("settings", {}).get("max_concurrent_downloads", 3)
            while self.download_queue and self.active_downloads < max_concurrent:
                item = self.download_queue.pop(0)
                self.active_downloads += 1
                thread = threading.Thread(
                    target=self.run_ytdlp_download,
                    args=(item['cmd'], item['download_id'], item['output'], 
                          item.get('video_id', ''), item.get('quality', 'best'), 
                          item.get('title', ''))
                )
                thread.daemon = True
                thread.start()
        
        config = self.config_manager.config
        config["download_queue"] = self.download_queue
        self.config_manager.save_config()
    
    def add_to_queue(self, cmd, download_id, output, video_id, quality, title):
        self.download_queue.append({
            'cmd': cmd,
            'download_id': download_id,
            'output': output,
            'video_id': video_id,
            'quality': quality,
            'title': title
        })
        config = self.config_manager.config
        config["download_queue"] = self.download_queue
        self.config_manager.save_config()
        self.process_queue()
    
    def run_ytdlp_download(self, cmd, download_id, output_path, video_id='', quality='best', title=''):
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
                        self.download_progress[download_id] = {
                            'percent': percent, 
                            'speed': speed, 
                            'eta': eta, 
                            'completed': False
                        }
                    elif is_stderr and 'ERROR' in line:
                        logger.error(f"Download error: {line}")
                        self.download_progress[download_id] = {'percent': 0, 'error': line, 'completed': False}
                
                stream.close()
            
            stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, False))
            stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, True))
            stdout_thread.start()
            stderr_thread.start()
            
            return_code = process.wait()
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
            
            if return_code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.download_progress[download_id] = {'percent': 100, 'completed': True}
                self.download_files[download_id] = output_path
                logger.info(f"Download completed: {output_path}")
                
                save_subtitles = self.config_manager.get("settings", {}).get("save_subtitles", False)
                if save_subtitles and video_id:
                    subtitle_lang = self.config_manager.get("settings", {}).get("subtitle_language", "en")
                    threading.Thread(target=self.download_subtitles, args=(video_id, subtitle_lang)).start()
            else:
                error_msg = f"Download failed with code {return_code}"
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except:
                        pass
                self.download_progress[download_id] = {'percent': 0, 'error': error_msg, 'completed': True}
                logger.error(error_msg)
                
        except Exception as e:
            logger.error(f"Download exception: {e}")
            self.download_progress[download_id] = {'percent': 0, 'error': str(e), 'completed': True}
        finally:
            with self.active_lock:
                self.active_downloads -= 1
            self.process_queue()
    
    def start_download(self, video_id, dtype, download_id, quality='best'):
        if not video_id or not download_id:
            return 'Missing parameters', 400
        
        if not os.path.exists(self.cookie_file):
            return 'Not authenticated. Please scan browsers first.', 500
        
        if dtype == 'mp4':
            ffmpeg_path = self.check_ffmpeg()
            if not ffmpeg_path:
                return 'FFmpeg not found. Required for MP4 downloads.', 500
        
        title = video_id
        try:
            cmd_info = [sys.executable, "-m", "yt_dlp", "--cookies", self.cookie_file, 
                       "--no-playlist", "--dump-json", f"https://www.youtube.com/watch?v={video_id}"]
            
            if self.check_deno():
                cmd_info.extend(["--js-runtimes", "deno", "--remote-components", "ejs:npm"])
            
            result = subprocess.run(cmd_info, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                title = data.get('title', video_id)
                title = re.sub(r'[\\/*?:"<>|]', "", title)[:50]
        except Exception as e:
            logger.warning(f"Could not fetch title: {e}")
        
        output = os.path.join(self.download_folder, f'{title}_{download_id}.{dtype}')
        
        cmd = [sys.executable, "-m", "yt_dlp", "--cookies", self.cookie_file, "--no-playlist"]
        
        cmd.append("--live-from-start")
        cmd.extend(["--concurrent-fragments", str(min(self.cpu_count, 10)), "-N", str(min(self.cpu_count, 10))])
        cmd.extend(["--newline", "--progress", "-o", output])
        
        if dtype == 'mp3':
            cmd.extend([
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--embed-thumbnail",
                "--add-metadata"
            ])
            cmd.append(f"https://www.youtube.com/watch?v={video_id}")
        else:
            quality_formats = {
                'best': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                '1080p': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
                '720p': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
                '480p': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
            }
            format_str = quality_formats.get(quality, quality_formats['best'])
            cmd.extend(["--format", format_str, "--merge-output-format", "mp4", "--embed-thumbnail", "--add-metadata"])
            cmd.append(f"https://www.youtube.com/watch?v={video_id}")
        
        if self.check_deno():
            cmd.extend(["--js-runtimes", "deno", "--remote-components", "ejs:npm"])
        
        ffmpeg_path = self.check_ffmpeg()
        if ffmpeg_path:
            cmd.extend(["--ffmpeg-location", ffmpeg_path])

        self.add_to_queue(cmd, download_id, output, video_id, quality, title)
        return '', 202
    
    def get_progress(self, download_id):
        if download_id in self.download_progress:
            return self.download_progress[download_id]
        return {'percent': 0, 'completed': False}
    
    def get_file(self, download_id):
        if download_id in self.download_files and os.path.exists(self.download_files[download_id]):
            return self.download_files[download_id]
        return None
    
    def get_queue_status(self):
        return {'active': self.active_downloads, 'queued': len(self.download_queue)}


class UIManager:
    def __init__(self):
        self.icons_folder = os.path.join(os.path.dirname(__file__), '.icons')
    
    def get_icon_content(self, icon_name):
        icon_path = os.path.join(self.icons_folder, icon_name)
        if os.path.exists(icon_path):
            with open(icon_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ''
    
    def get_html(self):
        return render_template('index.html',
                             ICON_DOWNLOADER=self.get_icon_content('downloader.svg'),
                             ICON_INSTRUCTIONS=self.get_icon_content('instructions.svg'),
                             ICON_REFRESH=self.get_icon_content('refresh.svg'),
                             ICON_TRASH=self.get_icon_content('trash.svg'),
                             ICON_CHANNEL=self.get_icon_content('channel.svg'),
                             ICON_ARCHIVE=self.get_icon_content('archive.svg'))


class YTIMP4App:
    def __init__(self):
        self.app = Flask(__name__)
        
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'servers'))
        from servers import register_blueprints
        register_blueprints(self.app)
        
        from sync import register_sync_routes
        register_sync_routes(self.app)
        
        self.download_folder = os.path.join(os.path.dirname(__file__), "downloads")
        os.makedirs(self.download_folder, exist_ok=True)
        
        self.archive_folder = os.path.join(os.path.dirname(__file__), "archives")
        os.makedirs(self.archive_folder, exist_ok=True)
        
        self.cookie_file = os.path.join(os.path.dirname(__file__), "cookies.txt")
        self.config_file = os.path.join(os.path.dirname(__file__), "config.json")
        
        self.config_manager = ConfigManager(self.config_file)
        self.cookie_manager = CookieManager(self.cookie_file)
        self.download_manager = DownloadManager(self.download_folder, self.cookie_file, self.config_manager)
        self.ui_manager = UIManager()
        
        self._register_routes()
    
    def _register_routes(self):
        @self.app.route('/')
        def index():
            return self.ui_manager.get_html()
        
        @self.app.route('/api/get_settings')
        def get_settings():
            return jsonify({
                'youtube_api_key': self.config_manager.get('youtube_api_key', ''),
                'max_concurrent_downloads': self.config_manager.get('settings', {}).get('max_concurrent_downloads', 3),
                'default_format': self.config_manager.get('settings', {}).get('default_format', 'mp4'),
                'default_quality': self.config_manager.get('settings', {}).get('default_quality', 'best'),
                'save_subtitles': self.config_manager.get('settings', {}).get('save_subtitles', False),
                'subtitle_language': self.config_manager.get('settings', {}).get('subtitle_language', 'en')
            })
        
        @self.app.route('/api/save_settings', methods=['POST'])
        def save_settings():
            data = request.json
            self.config_manager.config['youtube_api_key'] = data.get('youtube_api_key', self.config_manager.get('youtube_api_key', ''))
            self.config_manager.config['settings']['max_concurrent_downloads'] = data.get('max_concurrent_downloads', 3)
            self.config_manager.config['settings']['default_format'] = data.get('default_format', 'mp4')
            self.config_manager.config['settings']['default_quality'] = data.get('default_quality', 'best')
            self.config_manager.config['settings']['save_subtitles'] = data.get('save_subtitles', False)
            self.config_manager.config['settings']['subtitle_language'] = data.get('subtitle_language', 'en')
            self.config_manager.save_config()
            return jsonify({'success': True})
        
        @self.app.route('/api/queue_status')
        def queue_status():
            return jsonify(self.download_manager.get_queue_status())
        
        @self.app.route('/api/subtitles')
        def subtitles():
            video_id = request.args.get('video_id', '')
            if not video_id:
                return jsonify({'error': 'No video ID provided'})
            
            language = self.config_manager.get("settings", {}).get("subtitle_language", "en")
            sub_file = self.download_manager.download_subtitles(video_id, language)
            
            if sub_file and os.path.exists(sub_file):
                try:
                    with open(sub_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    os.remove(sub_file)
                    return jsonify({'subtitles': content})
                except Exception as e:
                    logger.error(f"Error reading subtitle file: {e}")
                    return jsonify({'error': 'Failed to read subtitle file'})
            
            if language != 'en':
                sub_file = self.download_manager.download_subtitles(video_id, 'en')
                if sub_file and os.path.exists(sub_file):
                    try:
                        with open(sub_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        os.remove(sub_file)
                        return jsonify({'subtitles': content})
                    except Exception as e:
                        logger.error(f"Error reading subtitle file: {e}")
                        return jsonify({'error': 'Failed to read subtitle file'})
            
            return jsonify({'subtitles': None, 'error': 'No subtitles found'})
        
        @self.app.route('/api/scan', methods=['POST'])
        def scan():
            result = self.cookie_manager.scan_and_save()
            return jsonify(result)
        
        @self.app.route('/api/clear_cookies', methods=['POST'])
        def clear_cookies_route():
            success = self.cookie_manager.clear_cookies()
            return jsonify({'success': success})
        
        @self.app.route('/api/status')
        def status():
            return jsonify({'authenticated': self.cookie_manager.is_authenticated()})
        
        @self.app.route('/api/info')
        def info():
            url = request.args.get('url', '')
            return jsonify(self.download_manager.get_video_info(url))
        
        @self.app.route('/api/download')
        def download():
            video_id = request.args.get('video_id', '')
            dtype = request.args.get('type', 'mp4')
            download_id = request.args.get('download_id', '')
            quality = request.args.get('quality', 'best')
            
            result = self.download_manager.start_download(video_id, dtype, download_id, quality)
            if isinstance(result, tuple):
                return result[0], result[1]
            return result
        
        @self.app.route('/api/progress/<download_id>')
        def progress(download_id):
            return jsonify(self.download_manager.get_progress(download_id))
        
        @self.app.route('/api/get_file/<download_id>')
        def get_file(download_id):
            file_path = self.download_manager.get_file(download_id)
            if file_path:
                return send_file(file_path, as_attachment=True)
            return 'File not found', 404
    
    def run(self, port=8080, debug=False):
        if os.path.exists(self.cookie_file):
            os.remove(self.cookie_file)
        
        self.download_manager.process_queue()
        
        print(f"YTIMP4 - CPU cores: {self.download_manager.cpu_count}")
        print(f"Archive folder: {self.archive_folder}")
        print(f"Server running on http://localhost:{port}")
        
        self.app.run(host='127.0.0.1', port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--debug', action='store_true', default=False)
    args = parser.parse_args()
    
    app = YTIMP4App()
    app.run(port=args.port, debug=args.debug)