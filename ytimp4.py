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
from flask import Flask, render_template, request, send_file, jsonify, url_for
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, 
            static_folder='static',
            static_url_path='/static',
            template_folder='templates')

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

@app.route('/')
def index():
    return render_template('index.html')

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

@app.route('/api/channel_lookup_html')
def channel_lookup_html():
    return '''
    <div class="status-card">
        <div class="status-text">Channel Lookup & Archive Tool</div>
    </div>
    <div class="channel-input-group">
        <input type="text" id="channelInput" class="channel-input" placeholder="Enter YouTube channel name, handle, or URL..." autocomplete="off">
        <button id="channelLookupBtn" class="channel-btn">Lookup Channel</button>
        <button id="archiveChannelBtn" class="action-btn"><span class="nav-icon"><img src="/static/icons/archive.svg" alt="archive" onerror="this.src='/static/fallback.png'"></span>Archive Channel</button>
    </div>
    <div id="channelResults" class="channel-result"></div>
    <div id="archiveStatus" style="margin-top: 0.5rem; font-size: 0.8rem; color: #6b7280;"></div>
    <script>
        document.getElementById('channelLookupBtn').onclick = async function() {
            const query = document.getElementById('channelInput').value.trim();
            if (!query) { alert('Please enter a channel name or URL'); return; }
            document.getElementById('loadingOverlay').style.display = 'flex';
            document.getElementById('loadingText').textContent = 'Searching...';
            try {
                const res = await fetch('/api/channel_lookup?q=' + encodeURIComponent(query));
                const data = await res.json();
                const container = document.getElementById('channelResults');
                if (data.error) { container.innerHTML = '<div class="error-message" style="display:block;">' + data.error + '</div>'; return; }
                if (!data.items || data.items.length === 0) { container.innerHTML = '<div class="loading-suggestion">No channels found</div>'; return; }
                let html = '';
                for (const item of data.items) {
                    html += '<div class="channel-card">';
                    html += '<div class="channel-name">' + (item.name || 'Unknown') + '</div>';
                    html += '<div class="channel-handle">' + (item.handle || '') + '</div>';
                    html += '<div class="channel-stats">';
                    html += '<span>Subscribers: ' + (item.subscribers || 'N/A') + '</span>';
                    html += '<span>Videos: ' + (item.videos || 'N/A') + '</span>';
                    html += '<span>Views: ' + (item.views || 'N/A') + '</span>';
                    html += '</div>';
                    html += '<div style="margin-top:0.5rem;"><a href="' + (item.url || '#') + '" target="_blank" style="color:#4a6a8a;">Open Channel</a></div>';
                    if (item.community_posts && item.community_posts.length > 0) {
                        html += '<div style="margin-top:1rem;"><strong>Recent Community Posts</strong></div>';
                        for (const post of item.community_posts) {
                            html += '<div class="community-post">';
                            html += '<div class="post-text">' + (post.text || '') + '</div>';
                            html += '<div class="post-date">' + (post.date || '') + '</div>';
                            html += '<div class="post-stats"><span>Likes: ' + (post.likes || '0') + '</span><span>Comments: ' + (post.comments || '0') + '</span></div>';
                            html += '</div>';
                        }
                    }
                    html += '</div>';
                }
                container.innerHTML = html;
            } catch(e) {
                document.getElementById('channelResults').innerHTML = '<div class="error-message" style="display:block;">Error: ' + e.message + '</div>';
            }
            document.getElementById('loadingOverlay').style.display = 'none';
        };
        document.getElementById('archiveChannelBtn').onclick = async function() {
            const query = document.getElementById('channelInput').value.trim();
            if (!query) { alert('Please enter a channel URL'); return; }
            document.getElementById('loadingOverlay').style.display = 'flex';
            document.getElementById('loadingText').textContent = 'Archiving...';
            try {
                const res = await fetch('/api/archive_channel?url=' + encodeURIComponent(query));
                const data = await res.json();
                const status = document.getElementById('archiveStatus');
                if (data.error) { status.innerHTML = '<span style="color:#ff4444;">Error: ' + data.error + '</span>'; }
                else { status.innerHTML = '<span style="color:#10b981;">Archive saved: ' + data.filename + '</span>'; }
            } catch(e) {
                document.getElementById('archiveStatus').innerHTML = '<span style="color:#ff4444;">Error: ' + e.message + '</span>';
            }
            document.getElementById('loadingOverlay').style.display = 'none';
        };
    </script>
    '''

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
    quality = request.args.get('quality', 'best')

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

@app.route('/api/subtitles')
def get_subtitles():
    video_id = request.args.get('video_id', '')
    if not video_id:
        return jsonify({'error': 'No video ID'})
    
    if not os.path.exists(COOKIE_FILE):
        return jsonify({'error': 'No cookies'})
    
    try:
        cmd = [sys.executable, "-m", "yt_dlp", "--cookies", COOKIE_FILE, "--write-subs", "--sub-lang", "en", "--skip-download", "-o", f"{video_id}", f"https://www.youtube.com/watch?v={video_id}"]
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        sub_file = f"{video_id}.en.srt"
        if os.path.exists(sub_file):
            with open(sub_file, 'r', encoding='utf-8') as f:
                subs = f.read()
            os.remove(sub_file)
            return jsonify({'subtitles': subs})
        return jsonify({'error': 'No subtitles found'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/queue_status')
def queue_status():
    active = 0
    queued = 0
    for d in download_progress.values():
        if d.get('completed', False) == False:
            active += 1
        elif d.get('queued', False):
            queued += 1
    return jsonify({'active': active, 'queued': queued})

@app.route('/api/system_status')
def system_status():
    try:
        total, used, free = shutil.disk_usage(os.path.dirname(__file__))
        return jsonify({'free_space': f'{free // (1024**3)} GB'})
    except:
        return jsonify({'free_space': 'N/A'})

@app.route('/api/get_settings')
def get_settings():
    settings = {
        'youtube_api_key': os.environ.get('YT_API_KEY', ''),
        'download_folder': DOWNLOAD_FOLDER,
        'max_concurrent_downloads': 3,
        'default_format': 'mp4',
        'default_quality': 'best',
        'max_retries': 3,
        'save_subtitles': False,
        'subtitle_language': 'en'
    }
    return jsonify(settings)

@app.route('/api/save_settings', methods=['POST'])
def save_settings():
    try:
        data = request.json
        with open('settings.json', 'w') as f:
            json.dump(data, f)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    if os.path.exists(COOKIE_FILE):
        os.remove(COOKIE_FILE)
    print(f"\nYTIMP4 - CPU cores: {cpu_count}, Deno: {check_deno()}, FFmpeg: {check_ffmpeg()}")
    print(f"Archive folder: {ARCHIVE_FOLDER}")
    port = 8080
    app.run(host='127.0.0.1', port=port, debug=False, threaded=True)