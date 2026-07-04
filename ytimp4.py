#!/usr/bin/env python3
import os
import subprocess
import sys
import re
import time
import json
import webbrowser
import threading
import sqlite3
import shutil
import asyncio
import aiohttp
import urllib.parse
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

download_progress = {}
download_files = {}

cpu_count = os.cpu_count() or 4

def check_deno():
    try:
        subprocess.run(["deno", "--version"], capture_output=True)
        return True
    except:
        return False

def check_ffmpeg():
    ffmpeg_paths = ["ffmpeg.exe", os.path.join(os.path.dirname(__file__), "ffmpeg.exe")]
    for p in ffmpeg_paths:
        if os.path.exists(p):
            return True
    return False

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

def run_ytdlp_download(cmd, download_id, output_path):
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )

        def read_stream(stream):
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
                    download_progress[download_id] = {'percent': percent, 'speed': speed, 'eta': eta, 'completed': False}
            stream.close()

        stdout_thread = threading.Thread(target=read_stream, args=(process.stdout,))
        stderr_thread = threading.Thread(target=read_stream, args=(process.stderr,))
        stdout_thread.start()
        stderr_thread.start()
        process.wait()
        stdout_thread.join()
        stderr_thread.join()

        if process.returncode == 0 and os.path.exists(output_path):
            download_progress[download_id] = {'percent': 100, 'completed': True}
            download_files[download_id] = output_path
        else:
            download_progress[download_id] = {'percent': 0, 'error': 'Download failed', 'completed': True}
    except Exception as e:
        download_progress[download_id] = {'percent': 0, 'error': str(e), 'completed': True}

ICON_DOWNLOADER = '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>'
ICON_INSTRUCTIONS = '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>'
ICON_REFRESH = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>'
ICON_TRASH = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>'
ICON_CHANNEL = '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M10 15l5.5-3-5.5-3v6zM21 3H3c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H3V5h18v14z"/></svg>'
ICON_ARCHIVE = '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M20 6h-8l-2-2H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 12H4V8h16v10z"/></svg>'

async def fetch_channel_html_async(session, channel_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        async with session.get(channel_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
            return await response.text()
    except Exception as e:
        logger.error(f"Failed to fetch channel: {e}")
        return None

def extract_channel_info(html_content):
    info = {}
    title_match = re.search(r'<title>(.*?)\s*-\s*YouTube</title>', html_content)
    if title_match:
        info['name'] = title_match.group(1)

    handle_match = re.search(r'"externalChannelId":"([^"]+)"', html_content)
    if not handle_match:
        handle_match = re.search(r'"channelHandle":"([^"]+)"', html_content)
    if handle_match:
        info['handle'] = handle_match.group(1)

    json_match = re.search(r'var ytInitialData = ({.*?});', html_content)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if 'contents' in data:
                two_column = data['contents'].get('twoColumnBrowseResultsRenderer', {})
                tabs = two_column.get('tabs', [])
                for tab in tabs:
                    tab_renderer = tab.get('tabRenderer', {})
                    content = tab_renderer.get('content', {})
                    section_list = content.get('sectionListRenderer', {})
                    for section in section_list.get('contents', []):
                        item_section = section.get('itemSectionRenderer', {})
                        for item in item_section.get('contents', []):
                            channel_about = item.get('channelAboutFullMetadataRenderer', {})
                            if channel_about:
                                if 'subscriberCountText' in channel_about:
                                    subs_text = channel_about['subscriberCountText'].get('simpleText', '')
                                    subs_match = re.search(r'([\d,\.]+)', subs_text)
                                    if subs_match:
                                        info['subscribers'] = subs_match.group(1).replace(',', '')
                                if 'viewCountText' in channel_about:
                                    views_text = channel_about['viewCountText'].get('simpleText', '')
                                    views_match = re.search(r'([\d,\.]+)', views_text)
                                    if views_match:
                                        info['views'] = views_match.group(1).replace(',', '')
                                break
        except Exception as e:
            logger.error(f"JSON parsing error: {e}")

    if 'subscribers' not in info:
        subs_match = re.search(r'"subscriberCountText":\{[^}]*"simpleText":"([^"]+)"', html_content)
        if subs_match:
            subs_text = subs_match.group(1)
            subs_num = re.sub(r'[^0-9]', '', subs_text)
            if subs_num:
                info['subscribers'] = subs_num

    if 'views' not in info:
        views_match = re.search(r'"viewCountText":\{[^}]*"simpleText":"([^"]+)"', html_content)
        if views_match:
            views_text = views_match.group(1)
            views_num = re.sub(r'[^0-9]', '', views_text)
            if views_num:
                info['views'] = views_num

    videos_match = re.search(r'"videoCountText":\{[^}]*"simpleText":"([^"]+)"', html_content)
    if videos_match:
        videos_text = videos_match.group(1)
        videos_num = re.sub(r'[^0-9]', '', videos_text)
        if videos_num:
            info['videos'] = videos_num

    id_match = re.search(r'"channelId":"([^"]+)"', html_content)
    if id_match:
        info['id'] = id_match.group(1)

    return info

def extract_community_posts(html_content):
    posts = []
    json_match = re.search(r'var ytInitialData = ({.*?});', html_content)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            contents = data.get('contents', {})
            two_column = contents.get('twoColumnBrowseResultsRenderer', {})
            tabs = two_column.get('tabs', [])
            for tab in tabs:
                tab_renderer = tab.get('tabRenderer', {})
                content = tab_renderer.get('content', {})
                section_list = content.get('sectionListRenderer', {})
                for section in section_list.get('contents', []):
                    item_section = section.get('itemSectionRenderer', {})
                    for item in item_section.get('contents', []):
                        post_thread = item.get('backstagePostThreadRenderer', {})
                        if post_thread:
                            post = post_thread.get('post', {})
                            backstage = post.get('backstagePostRenderer', {})
                            content_text = backstage.get('contentText', {})
                            runs = content_text.get('runs', [])
                            text = ''
                            for run in runs:
                                text += run.get('text', '')
                            published_time = backstage.get('publishedTimeText', {}).get('simpleText', '')
                            vote_count = backstage.get('voteCount', {}).get('simpleText', '0')
                            comment_count = backstage.get('commentCount', {}).get('simpleText', '0')
                            posts.append({
                                'text': text[:300],
                                'date': published_time,
                                'likes': vote_count,
                                'comments': comment_count
                            })
        except Exception as e:
            logger.error(f"Post extraction error: {e}")

    if not posts:
        post_pattern = r'"postText":\{"runs":\[([^\]]+)\]\}'
        text_matches = re.findall(post_pattern, html_content)
        date_pattern = r'"publishedTimeText":\{"simpleText":"([^"]+)"\}'
        dates = re.findall(date_pattern, html_content)
        for i in range(min(len(text_matches), len(dates), 5)):
            text = text_matches[i]
            text_clean = re.sub(r'\{[^}]*"text":"([^"]+)"[^}]*\}', r'\1', text)
            text_clean = re.sub(r'\\u0026', '&', text_clean)
            posts.append({
                'text': text_clean[:300],
                'date': dates[i] if i < len(dates) else '',
                'likes': '0',
                'comments': '0'
            })

    return posts

async def search_channels_async(query):
    results = []
    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9'}
            async with session.get(search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                html_content = await response.text()

            channel_ids = []
            id_pattern = r'"channelId":"([^"]+)"'
            found_ids = re.findall(id_pattern, html_content)
            for cid in found_ids:
                if cid not in channel_ids:
                    channel_ids.append(cid)
            channel_ids = channel_ids[:5]

            for cid in channel_ids:
                channel_url = f"https://www.youtube.com/channel/{cid}"
                channel_html = await fetch_channel_html_async(session, channel_url)
                if channel_html:
                    channel_info = extract_channel_info(channel_html)
                    if channel_info.get('name'):
                        channel_info['url'] = channel_url
                        channel_info['id'] = cid
                        community_posts = extract_community_posts(channel_html)
                        channel_info['community_posts'] = community_posts[:3]
                        results.append(channel_info)
        except Exception as e:
            logger.error(f"Search error: {e}")
    return results

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YTIMP4</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', -apple-system, Roboto, Arial, sans-serif;
            background-color: #1a1a1a;
            color: #e5e5e5;
        }

        .header {
            position: sticky;
            top: 0;
            z-index: 100;
            background-color: #2a2a2a;
            border-bottom: 1px solid #3a3a3a;
            padding: 0.75rem 1.5rem;
        }

        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            gap: 2rem;
            flex-wrap: wrap;
        }

        .logo {
            font-size: 1.4rem;
            font-weight: 600;
            letter-spacing: -0.5px;
        }

        .logo span:first-child {
            color: #ff0000;
        }

        .logo span:last-child {
            color: #ffffff;
            font-weight: 400;
        }

        .search-container {
            flex: 1;
            max-width: 600px;
            display: flex;
            gap: 0;
        }

        .search-input {
            flex: 1;
            padding: 0.6rem 1rem;
            background-color: #2a2a2a;
            border: 1px solid #4a4a4a;
            border-radius: 40px 0 0 40px;
            color: #ffffff;
            font-size: 0.9rem;
            outline: none;
        }

        .search-input:focus {
            border-color: #1c62b9;
        }

        .search-button {
            padding: 0.6rem 1.25rem;
            background-color: #4a4a4a;
            border: 1px solid #4a4a4a;
            border-left: none;
            border-radius: 0 40px 40px 0;
            color: #ffffff;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 500;
            transition: background 0.2s;
        }

        .search-button:hover {
            background-color: #5a5a5a;
        }

        .action-group {
            display: flex;
            gap: 0.75rem;
        }

        .action-btn {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            border-radius: 40px;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
            background: #3a3a3a;
            color: #e5e5e5;
        }

        .action-btn:hover {
            background-color: #4a4a4a;
        }

        .main-wrapper {
            display: flex;
            max-width: 1400px;
            margin: 0 auto;
            min-height: calc(100vh - 60px);
        }

        .sidebar {
            width: 240px;
            background-color: #2a2a2a;
            padding: 1rem 0.75rem;
            border-right: 1px solid #3a3a3a;
        }

        .nav-item {
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 0.6rem 0.75rem;
            margin: 0.25rem 0;
            border-radius: 10px;
            color: #aaaaaa;
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }

        .nav-item:hover {
            background-color: #3a3a3a;
            color: #ffffff;
        }

        .nav-item.active {
            background-color: #3a3a3a;
            color: #ffffff;
        }

        .nav-icon {
            width: 22px;
            height: 22px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }

        .content-area {
            flex: 1;
            padding: 2rem;
            background-color: #1a1a1a;
        }

        .downloader-page {
            display: block;
        }

        .instructions-page {
            display: none;
            max-width: 700px;
            margin: 0 auto;
        }

        .channel-page {
            display: none;
            max-width: 900px;
            margin: 0 auto;
        }

        .status-card {
            background: #2a2a2a;
            border-radius: 16px;
            padding: 1.25rem;
            margin-bottom: 1.5rem;
            text-align: center;
            border: 1px solid #3a3a3a;
        }

        .status-text {
            font-size: 0.9rem;
            color: #9ca3af;
            margin-bottom: 0.5rem;
        }

        .result-card {
            background: #2a2a2a;
            border-radius: 16px;
            overflow: hidden;
            display: none;
            border: 1px solid #3a3a3a;
        }

        .video-info {
            display: flex;
            gap: 1.5rem;
            flex-wrap: wrap;
            padding: 1.5rem;
        }

        .thumbnail {
            width: 320px;
            border-radius: 12px;
            object-fit: cover;
        }

        .thumbnail-container {
            position: relative;
        }

        .live-badge {
            position: absolute;
            bottom: 8px;
            left: 8px;
            background: #ff0000;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.65rem;
            font-weight: 600;
        }

        .details {
            flex: 1;
        }

        .video-title {
            font-size: 1.2rem;
            font-weight: 500;
            margin-bottom: 0.5rem;
        }

        .video-meta {
            color: #9ca3af;
            font-size: 0.8rem;
            margin-bottom: 1rem;
        }

        .actions {
            background: #3a3a3a;
            border-radius: 12px;
            padding: 1rem;
            margin-top: 1rem;
        }

        .download-buttons {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }

        .download-btn {
            flex: 1;
            padding: 0.7rem;
            border: none;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }

        .download-btn.mp4 {
            background: #cc0000;
            color: white;
        }

        .download-btn.mp4:hover {
            background: #aa0000;
        }

        .download-btn.mp3 {
            background: #1e5631;
            color: white;
        }

        .download-btn.mp3:hover {
            background: #164523;
        }

        .progress-container {
            display: none;
            margin-top: 1rem;
        }

        .progress-bar {
            width: 100%;
            height: 4px;
            background-color: #4a4a4a;
            border-radius: 2px;
            overflow: hidden;
        }

        .progress-fill {
            width: 0%;
            height: 100%;
            background-color: #ff0000;
            transition: width 0.3s;
        }

        .progress-text {
            font-size: 0.75rem;
            color: #9ca3af;
            margin-top: 0.5rem;
            text-align: center;
        }

        .progress-speed {
            font-size: 0.7rem;
            color: #6b7280;
            margin-top: 0.25rem;
            text-align: center;
        }

        .eta-text {
            font-size: 0.7rem;
            color: #6b7280;
            margin-top: 0.25rem;
            text-align: center;
        }

        .step-card {
            background: #2a2a2a;
            border: 1px solid #3a3a3a;
            border-radius: 14px;
            padding: 1.25rem;
            margin-bottom: 1rem;
            display: flex;
            gap: 1rem;
        }

        .step-number {
            width: 28px;
            height: 28px;
            background: #ff0000;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
            font-weight: 700;
            flex-shrink: 0;
        }

        .step-title {
            font-weight: 600;
            margin-bottom: 0.2rem;
        }

        .step-desc {
            font-size: 0.8rem;
            color: #9ca3af;
        }

        .error-message {
            background: #3a2a2a;
            border-left: 3px solid #ff0000;
            padding: 0.75rem;
            margin-top: 1rem;
            border-radius: 8px;
            display: none;
            font-size: 0.8rem;
            color: #ff8888;
        }

        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.95);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            flex-direction: column;
            gap: 1rem;
        }

        .loading-spinner {
            width: 48px;
            height: 48px;
            border: 3px solid #4a4a4a;
            border-top: 3px solid #ff0000;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        .loading-text {
            font-size: 0.9rem;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .features {
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid #3a3a3a;
            font-size: 0.7rem;
            color: #6b7280;
            flex-wrap: wrap;
        }

        .channel-input-group {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }

        .channel-input {
            flex: 1;
            padding: 0.6rem 1rem;
            background-color: #2a2a2a;
            border: 1px solid #4a4a4a;
            border-radius: 40px;
            color: #ffffff;
            font-size: 0.9rem;
            outline: none;
        }

        .channel-btn {
            padding: 0.6rem 1.25rem;
            background-color: #4a6a8a;
            border: none;
            border-radius: 40px;
            color: white;
            cursor: pointer;
        }

        .channel-result {
            margin-top: 1rem;
        }

        .channel-card {
            background: #2a2a2a;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 0.75rem;
            border: 1px solid #3a3a3a;
        }

        .channel-name {
            font-weight: 600;
            font-size: 1rem;
            margin-bottom: 0.25rem;
        }

        .channel-handle {
            color: #9ca3af;
            font-size: 0.8rem;
        }

        .channel-stats {
            display: flex;
            gap: 1rem;
            margin-top: 0.5rem;
            font-size: 0.75rem;
            color: #6b7280;
            flex-wrap: wrap;
        }

        .community-post {
            background: #3a3a3a;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1rem;
            border-left: 3px solid #4a6a8a;
        }

        .post-text {
            color: #e5e5e5;
            font-size: 0.85rem;
            margin-bottom: 0.5rem;
        }

        .post-date {
            color: #6b7280;
            font-size: 0.7rem;
            margin-bottom: 0.5rem;
        }

        .post-stats {
            display: flex;
            gap: 1rem;
            font-size: 0.7rem;
            color: #6b7280;
        }

        @media (max-width: 768px) {
            .header-content {
                flex-direction: column;
                gap: 0.75rem;
            }
            .search-container {
                width: 100%;
            }
            .main-wrapper {
                flex-direction: column;
            }
            .sidebar {
                width: 100%;
                border-right: none;
                border-bottom: 1px solid #3a3a3a;
                display: flex;
                overflow-x: auto;
                padding: 0.5rem;
            }
            .nav-item {
                white-space: nowrap;
            }
            .thumbnail {
                width: 100%;
            }
            .video-info {
                flex-direction: column;
            }
            .download-buttons {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="logo"><span>YT</span><span>IMP4</span></div>
            <div class="search-container">
                <input type="text" id="urlInput" class="search-input" placeholder="Paste YouTube URL...">
                <button id="fetchBtn" class="search-button">Fetch</button>
            </div>
            <div class="action-group">
                <button id="authBtn" class="action-btn"><span class="nav-icon">%REFRESH_ICON%</span>Scan Browsers</button>
                <button id="clearCookiesBtn" class="action-btn"><span class="nav-icon">%TRASH_ICON%</span>Clear Cookies</button>
            </div>
        </div>
    </div>
    <div class="main-wrapper">
        <div class="sidebar">
            <div class="nav-item active" data-page="downloader"><span class="nav-icon">%DOWNLOADER_ICON%</span><span>Downloader</span></div>
            <div class="nav-item" data-page="channel"><span class="nav-icon">%CHANNEL_ICON%</span><span>Channel Lookup</span></div>
            <div class="nav-item" data-page="instructions"><span class="nav-icon">%INSTRUCTIONS_ICON%</span><span>Instructions</span></div>
        </div>
        <div class="content-area">
            <div id="downloaderPage" class="downloader-page">
                <div class="status-card">
                    <div class="status-text" id="statusText">Ready</div>
                </div>
                <div id="resultCard" class="result-card">
                    <div class="video-info">
                        <div class="thumbnail-container"><img id="thumbnail" class="thumbnail"><div id="liveBadge" class="live-badge" style="display: none;">LIVE</div></div>
                        <div class="details">
                            <div class="video-title" id="title"></div>
                            <div class="video-meta" id="meta"></div>
                            <div class="actions">
                                <div class="download-buttons">
                                    <button id="downloadMp4Btn" class="download-btn mp4">Download MP4</button>
                                    <button id="downloadMp3Btn" class="download-btn mp3">Download MP3</button>
                                </div>
                                <div id="progressContainer" class="progress-container">
                                    <div class="progress-bar"><div id="progressFill" class="progress-fill"></div></div>
                                    <div id="progressText" class="progress-text">0%</div>
                                    <div id="progressSpeed" class="progress-speed"></div>
                                    <div id="progressEta" class="eta-text"></div>
                                </div>
                            </div>
                            <div class="features">
                                <span>Age-restricted videos</span>
                                <span>Live streams</span>
                                <span>Best quality merged</span>
                                <span>MP3 with thumbnail</span>
                            </div>
                        </div>
                    </div>
                </div>
                <div id="errorMsg" class="error-message"></div>
            </div>
            <div id="channelPage" class="channel-page">
                <div class="status-card">
                    <div class="status-text">Channel Lookup & Archive Tool</div>
                </div>
                <div class="channel-input-group">
                    <input type="text" id="channelInput" class="channel-input" placeholder="Enter YouTube channel name, handle, or URL..." autocomplete="off">
                    <button id="channelLookupBtn" class="channel-btn">Lookup Channel</button>
                    <button id="archiveChannelBtn" class="action-btn"><span class="nav-icon">%ARCHIVE_ICON%</span>Archive Channel</button>
                </div>
                <div id="channelResults" class="channel-result"></div>
                <div id="archiveStatus" style="margin-top: 0.5rem; font-size: 0.8rem; color: #6b7280;"></div>
            </div>
            <div id="instructionsPage" class="instructions-page">
                <div class="step-card">
                    <div class="step-number">1</div>
                    <div class="step-content">
                        <div class="step-title">Channel Lookup</div>
                        <div class="step-desc">Search for YouTube channels by name, handle, or URL</div>
                    </div>
                </div>
                <div class="step-card">
                    <div class="step-number">2</div>
                    <div class="step-content">
                        <div class="step-title">View Community Posts</div>
                        <div class="step-desc">Extract and display recent community posts from the channel</div>
                    </div>
                </div>
                <div class="step-card">
                    <div class="step-number">3</div>
                    <div class="step-content">
                        <div class="step-title">Archive Channel</div>
                        <div class="step-desc">Save channel HTML data and community posts to local archive</div>
                    </div>
                </div>
                <div class="step-card">
                    <div class="step-number">4</div>
                    <div class="step-content">
                        <div class="step-title">Download Videos</div>
                        <div class="step-desc">Paste any YouTube URL to download MP4 or MP3</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div id="loadingOverlay" class="loading-overlay"><div class="loading-spinner"></div><div id="loadingText" class="loading-text">Processing...</div></div>
    <script>
        const urlInput = document.getElementById('urlInput');
        const fetchBtn = document.getElementById('fetchBtn');
        const authBtn = document.getElementById('authBtn');
        const clearCookiesBtn = document.getElementById('clearCookiesBtn');
        const resultCard = document.getElementById('resultCard');
        const titleEl = document.getElementById('title');
        const thumbnailEl = document.getElementById('thumbnail');
        const metaEl = document.getElementById('meta');
        const liveBadge = document.getElementById('liveBadge');
        const downloadMp4Btn = document.getElementById('downloadMp4Btn');
        const downloadMp3Btn = document.getElementById('downloadMp3Btn');
        const errorDiv = document.getElementById('errorMsg');
        const loadingOverlay = document.getElementById('loadingOverlay');
        const loadingText = document.getElementById('loadingText');
        const statusText = document.getElementById('statusText');
        const downloaderPage = document.getElementById('downloaderPage');
        const instructionsPage = document.getElementById('instructionsPage');
        const channelPage = document.getElementById('channelPage');
        const navItems = document.querySelectorAll('.nav-item');
        const progressContainer = document.getElementById('progressContainer');
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        const progressSpeed = document.getElementById('progressSpeed');
        const progressEta = document.getElementById('progressEta');
        const channelInput = document.getElementById('channelInput');
        const channelLookupBtn = document.getElementById('channelLookupBtn');
        const archiveChannelBtn = document.getElementById('archiveChannelBtn');
        const channelResults = document.getElementById('channelResults');
        const archiveStatus = document.getElementById('archiveStatus');
        let currentVideoId = null;
        let progressInterval = null;
        let currentDownloadId = null;

        function switchPage(page) {
            if (page === 'downloader') {
                downloaderPage.style.display = 'block';
                instructionsPage.style.display = 'none';
                channelPage.style.display = 'none';
            } else if (page === 'channel') {
                downloaderPage.style.display = 'none';
                instructionsPage.style.display = 'none';
                channelPage.style.display = 'block';
            } else {
                downloaderPage.style.display = 'none';
                instructionsPage.style.display = 'block';
                channelPage.style.display = 'none';
            }
            navItems.forEach(item => {
                if (item.dataset.page === page) item.classList.add('active');
                else item.classList.remove('active');
            });
        }

        navItems.forEach(item => {
            item.addEventListener('click', () => switchPage(item.dataset.page));
        });

        async function updateStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                if (data.authenticated) {
                    statusText.textContent = 'Authenticated';
                } else {
                    statusText.textContent = 'Ready';
                }
            } catch(e) {}
        }

        async function scanBrowsers() {
            authBtn.disabled = true;
            loadingOverlay.style.display = 'flex';
            loadingText.textContent = 'Scanning browsers...';
            statusText.textContent = 'Scanning...';
            try {
                const res = await fetch('/api/scan', { method: 'POST' });
                const data = await res.json();
                await updateStatus();
                if (data.success) {
                    statusText.textContent = 'Authenticated';
                } else {
                    statusText.textContent = 'No cookies found';
                }
            } catch(e) {
                statusText.textContent = 'Error: ' + e.message;
            } finally {
                authBtn.disabled = false;
                loadingOverlay.style.display = 'none';
            }
        }

        async function clearCookies() {
            clearCookiesBtn.disabled = true;
            loadingOverlay.style.display = 'flex';
            loadingText.textContent = 'Clearing cookies...';
            statusText.textContent = 'Clearing...';
            try {
                const res = await fetch('/api/clear_cookies', { method: 'POST' });
                const data = await res.json();
                await updateStatus();
                if (data.success) {
                    statusText.textContent = 'Cookies cleared';
                    resultCard.style.display = 'none';
                } else {
                    statusText.textContent = 'Failed to clear cookies';
                }
            } catch(e) {} finally {
                clearCookiesBtn.disabled = false;
                loadingOverlay.style.display = 'none';
            }
        }

        authBtn.onclick = scanBrowsers;
        clearCookiesBtn.onclick = clearCookies;
        setInterval(updateStatus, 2000);
        updateStatus();

        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function channelLookup() {
            const query = channelInput.value.trim();
            if (!query) {
                channelResults.innerHTML = '<div class="error-message" style="display:block;">Please enter a channel name, handle, or URL</div>';
                return;
            }
            loadingOverlay.style.display = 'flex';
            loadingText.textContent = 'Searching for channel...';
            channelResults.innerHTML = '';
            archiveStatus.innerHTML = '';
            try {
                const res = await fetch('/api/channel_lookup?q=' + encodeURIComponent(query));
                const data = await res.json();
                if (data.error) throw new Error(data.error);
                if (data.items && data.items.length > 0) {
                    let html = '';
                    for (const item of data.items) {
                        html += `
                            <div class="channel-card">
                                <div class="channel-name">${escapeHtml(item.name) || 'Unknown'}</div>
                                <div class="channel-handle">${escapeHtml(item.handle) || ''}</div>
                                <div class="channel-stats">
                                    <span>Subscribers: ${item.subscribers || 'N/A'}</span>
                                    <span>Videos: ${item.videos || 'N/A'}</span>
                                    <span>Views: ${item.views || 'N/A'}</span>
                                </div>
                                <div class="channel-stats">
                                    <span>Channel ID: ${item.id || 'N/A'}</span>
                                </div>
                                <div style="margin-top: 0.5rem;">
                                    <a href="${item.url || '#'}" target="_blank" style="color: #4a6a8a; text-decoration: none;">Open Channel on YouTube</a>
                                </div>
                            </div>
                        `;
                        if (item.community_posts && item.community_posts.length > 0) {
                            html += `<div style="margin-top: 1rem;"><strong>Recent Community Posts</strong></div>`;
                            for (const post of item.community_posts) {
                                html += `
                                    <div class="community-post">
                                        <div class="post-text">${escapeHtml(post.text || '')}</div>
                                        <div class="post-date">${post.date || ''}</div>
                                        <div class="post-stats">
                                            <span>Likes: ${post.likes || '0'}</span>
                                            <span>Comments: ${post.comments || '0'}</span>
                                        </div>
                                    </div>
                                `;
                            }
                        }
                    }
                    channelResults.innerHTML = html;
                } else {
                    channelResults.innerHTML = '<div class="error-message" style="display:block;">No channels found. Try a different search term.</div>';
                }
            } catch (err) {
                channelResults.innerHTML = '<div class="error-message" style="display:block;">Error: ' + err.message + '</div>';
            } finally {
                loadingOverlay.style.display = 'none';
            }
        }

        async function archiveChannel() {
            const query = channelInput.value.trim();
            if (!query) {
                archiveStatus.innerHTML = '<span style="color: #ff4444;">Please enter a channel URL first</span>';
                return;
            }
            loadingOverlay.style.display = 'flex';
            loadingText.textContent = 'Archiving channel data...';
            archiveStatus.innerHTML = '';
            try {
                const res = await fetch('/api/archive_channel?url=' + encodeURIComponent(query));
                const data = await res.json();
                if (data.error) throw new Error(data.error);
                archiveStatus.innerHTML = '<span style="color: #10b981;">Archive saved: ' + data.filename + '</span>';
            } catch (err) {
                archiveStatus.innerHTML = '<span style="color: #ff4444;">Error: ' + err.message + '</span>';
            } finally {
                loadingOverlay.style.display = 'none';
            }
        }

        channelLookupBtn.onclick = channelLookup;
        archiveChannelBtn.onclick = archiveChannel;
        channelInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') channelLookup();
        });

        function extractVideoId(url) {
            const patterns = [
                /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
                /youtube\.com\/live\/([a-zA-Z0-9_-]{11})/,
                /youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})/
            ];
            for (let p of patterns) {
                const m = url.match(p);
                if (m) return m[1];
            }
            return null;
        }

        function showError(msg) {
            errorDiv.textContent = msg;
            errorDiv.style.display = 'block';
            setTimeout(() => errorDiv.style.display = 'none', 5000);
        }

        function startProgressMonitoring(downloadId) {
            if (progressInterval) clearInterval(progressInterval);
            progressContainer.style.display = 'block';
            progressInterval = setInterval(async () => {
                try {
                    const res = await fetch('/api/progress/' + downloadId);
                    const data = await res.json();
                    if (data.percent !== undefined) {
                        progressFill.style.width = data.percent + '%';
                        progressText.textContent = Math.round(data.percent) + '%';
                        if (data.speed) progressSpeed.textContent = 'Speed: ' + data.speed;
                        if (data.eta) progressEta.textContent = 'ETA: ' + data.eta;
                    }
                    if (data.completed) {
                        clearInterval(progressInterval);
                        setTimeout(async () => {
                            progressContainer.style.display = 'none';
                            progressFill.style.width = '0%';
                            progressSpeed.textContent = '';
                            progressEta.textContent = '';
                            const fileRes = await fetch('/api/get_file/' + downloadId);
                            if (fileRes.ok) {
                                const blob = await fileRes.blob();
                                const a = document.createElement('a');
                                const url = URL.createObjectURL(blob);
                                a.href = url;
                                a.download = 'YTIMP4_' + currentVideoId + '.' + (currentDownloadType === 'mp3' ? 'mp3' : 'mp4');
                                document.body.appendChild(a);
                                a.click();
                                document.body.removeChild(a);
                                URL.revokeObjectURL(url);
                            } else {
                                showError('Failed to retrieve downloaded file');
                            }
                        }, 500);
                    }
                } catch(e) {}
            }, 250);
        }

        let currentDownloadType = 'mp4';

        fetchBtn.onclick = async () => {
            const url = urlInput.value.trim();
            if (!url) {
                showError('Enter a YouTube URL');
                return;
            }
            currentVideoId = extractVideoId(url);
            if (!currentVideoId) {
                showError('Invalid YouTube URL');
                return;
            }
            loadingOverlay.style.display = 'flex';
            loadingText.textContent = 'Fetching video...';
            resultCard.style.display = 'none';
            statusText.textContent = 'Fetching...';
            try {
                const res = await fetch('/api/info?url=' + encodeURIComponent(url));
                const data = await res.json();
                if (data.error) throw new Error(data.error);
                thumbnailEl.src = data.thumbnail;
                titleEl.textContent = data.title;
                liveBadge.style.display = data.isLive ? 'block' : 'none';
                metaEl.textContent = (data.isLive ? 'LIVE | ' : '') + data.uploader;
                resultCard.style.display = 'block';
                statusText.textContent = 'Ready';
            } catch (err) {
                showError(err.message);
            } finally {
                loadingOverlay.style.display = 'none';
            }
        };

        downloadMp4Btn.onclick = () => {
            if (!currentVideoId) {
                showError('Fetch a video first');
                return;
            }
            currentDownloadId = Date.now().toString();
            currentDownloadType = 'mp4';
            startProgressMonitoring(currentDownloadId);
            fetch('/api/download?video_id=' + currentVideoId + '&type=mp4&download_id=' + currentDownloadId).catch(e => showError(e.message));
        };

        downloadMp3Btn.onclick = () => {
            if (!currentVideoId) {
                showError('Fetch a video first');
                return;
            }
            currentDownloadId = Date.now().toString();
            currentDownloadType = 'mp3';
            startProgressMonitoring(currentDownloadId);
            fetch('/api/download?video_id=' + currentVideoId + '&type=mp3&download_id=' + currentDownloadId).catch(e => showError(e.message));
        };

        urlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') fetchBtn.click();
        });
    </script>
</body>
</html>"""

@app.route('/')
def index():
    html = HTML
    html = html.replace('%DOWNLOADER_ICON%', ICON_DOWNLOADER)
    html = html.replace('%INSTRUCTIONS_ICON%', ICON_INSTRUCTIONS)
    html = html.replace('%REFRESH_ICON%', ICON_REFRESH)
    html = html.replace('%TRASH_ICON%', ICON_TRASH)
    html = html.replace('%CHANNEL_ICON%', ICON_CHANNEL)
    html = html.replace('%ARCHIVE_ICON%', ICON_ARCHIVE)
    return render_template_string(html)

@app.route('/api/channel_lookup')
def channel_lookup():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'No query provided'})

    try:
        if query.startswith('http'):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            connector = aiohttp.TCPConnector(limit=1)
            async def fetch_single():
                async with aiohttp.ClientSession(connector=connector) as session:
                    html_content = await fetch_channel_html_async(session, query)
                    if html_content:
                        channel_info = extract_channel_info(html_content)
                        if channel_info.get('name'):
                            community_posts = extract_community_posts(html_content)
                            channel_info['community_posts'] = community_posts[:5]
                            channel_info['url'] = query
                            return [channel_info]
                    return []
            items = loop.run_until_complete(fetch_single())
            loop.close()
            return jsonify({'items': items})
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(search_channels_async(query))
            loop.close()
            return jsonify({'items': results})
    except Exception as e:
        logger.error(f"Channel lookup error: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/archive_channel')
def archive_channel():
    channel_url = request.args.get('url', '')
    if not channel_url:
        return jsonify({'error': 'No URL provided'})

    try:
        if not channel_url.startswith('http'):
            channel_url = f"https://www.youtube.com/{channel_url}"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        connector = aiohttp.TCPConnector(limit=1)

        async def fetch_and_archive():
            async with aiohttp.ClientSession(connector=connector) as session:
                html_content = await fetch_channel_html_async(session, channel_url)
                if not html_content:
                    return None

                channel_info = extract_channel_info(html_content)
                channel_name = channel_info.get('name', 'unknown')
                safe_name = re.sub(r'[^a-zA-Z0-9]', '_', channel_name)
                timestamp = time.strftime('%Y%m%d_%H%M%S')
                filename = f"{safe_name}_{timestamp}.html"
                filepath = os.path.join(ARCHIVE_FOLDER, filename)

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"<!-- Archived from: {channel_url} -->\n")
                    f.write(f"<!-- Archived on: {time.ctime()} -->\n")
                    f.write(f"<!-- Channel Info: {json.dumps(channel_info, indent=2)} -->\n\n")
                    f.write(html_content)

                posts_file = os.path.join(ARCHIVE_FOLDER, f"{safe_name}_posts_{timestamp}.json")
                community_posts = extract_community_posts(html_content)
                with open(posts_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'channel_url': channel_url,
                        'channel_info': channel_info,
                        'community_posts': community_posts,
                        'archived_at': time.ctime()
                    }, f, indent=2)

                return filename

        filename = loop.run_until_complete(fetch_and_archive())
        loop.close()

        if filename:
            return jsonify({'success': True, 'filename': filename})
        return jsonify({'error': 'Failed to fetch channel'})
    except Exception as e:
        logger.error(f"Archive error: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/progress/<download_id>')
def progress(download_id):
    if download_id in download_progress:
        return download_progress[download_id]
    return {'percent': 0, 'completed': False}

@app.route('/api/get_file/<download_id>')
def get_file(download_id):
    if download_id in download_files and os.path.exists(download_files[download_id]):
        return send_file(download_files[download_id], as_attachment=True)
    return 'File not found', 404

@app.route('/api/scan', methods=['POST'])
def scan():
    browsers = get_browser_cookies()
    for browser_name, cookies in browsers:
        if cookies:
            save_cookies(cookies)
            return {'success': True, 'browser': browser_name}
    return {'success': False}

@app.route('/api/clear_cookies', methods=['POST'])
def clear_cookies_route():
    success = clear_cookies()
    return {'success': success}

@app.route('/api/status')
def status():
    if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 0:
        with open(COOKIE_FILE, 'r') as f:
            if 'LOGIN_INFO' in f.read():
                return {'authenticated': True}
    return {'authenticated': False}

@app.route('/api/info')
def info():
    url = request.args.get('url', '')
    video_id = extract_video_id(url)
    if not video_id:
        return {'error': 'Invalid URL'}

    if not os.path.exists(COOKIE_FILE):
        return {'error': 'No cookies. Scan browsers first.'}

    deno = check_deno()
    cmd = [sys.executable, "-m", "yt_dlp", "--cookies", COOKIE_FILE, "--no-playlist", "--dump-json", f"https://www.youtube.com/watch?v={video_id}"]
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

@app.route('/api/download')
def download():
    video_id = request.args.get('video_id', '')
    dtype = request.args.get('type', 'mp4')
    download_id = request.args.get('download_id', '')

    if not video_id or not download_id:
        return 'Missing parameters', 400

    if not os.path.exists(COOKIE_FILE):
        return 'Not authenticated', 500

    deno = check_deno()
    ffmpeg = check_ffmpeg()
    output = os.path.join(DOWNLOAD_FOLDER, f'{video_id}_{download_id}.{dtype}')

    if dtype == 'mp3':
        cmd = [sys.executable, "-m", "yt_dlp", "--cookies", COOKIE_FILE, "--no-playlist", "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0", "--embed-thumbnail", "--add-metadata", "--concurrent-fragments", str(cpu_count), "-N", str(cpu_count), "--newline", "--progress", "-o", output, f"https://www.youtube.com/watch?v={video_id}"]
    else:
        cmd = [sys.executable, "-m", "yt_dlp", "--cookies", COOKIE_FILE, "--no-playlist", "--live-from-start", "--format", "bestvideo+bestaudio", "--merge-output-format", "mp4", "--remux-video", "mp4", "--embed-thumbnail", "--add-metadata", "--concurrent-fragments", str(cpu_count), "-N", str(cpu_count), "--newline", "--progress", "-o", output, f"https://www.youtube.com/watch?v={video_id}"]

    if deno:
        cmd.extend(["--js-runtimes", "deno", "--remote-components", "ejs:npm"])
    if ffmpeg:
        cmd.extend(["--ffmpeg-location", "ffmpeg.exe"])

    thread = threading.Thread(target=run_ytdlp_download, args=(cmd, download_id, output))
    thread.daemon = True
    thread.start()

    return '', 202

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--debug', action='store_true', default=False)
    args = parser.parse_args()
    
    app = YTIMP4App()
    app.run(port=args.port, debug=args.debug)
