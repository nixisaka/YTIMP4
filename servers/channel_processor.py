# cython: language_level=3
# distutils: language=c++

import concurrent.futures
import requests
import json
import os
import time
import csv
import subprocess
import sys
import re

class ConcurrentChannelProcessor:
    def __init__(self, max_workers=10):
        self.max_workers = max_workers
        self.results = []
        self.api_key = self._get_api_key()
    
    def _get_api_key(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config.json')
        
        if not os.path.exists(config_path):
            config_path = os.path.join(script_dir, '..', 'config.json')
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('youtube_api_key', '')
            except Exception:
                return ""
        return ""
    
    def fetch_with_ytdlp(self, channel_id):
        try:
            cmd = [sys.executable, "-m", "yt_dlp", "--skip-download", "--dump-json", f"https://www.youtube.com/channel/{channel_id}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                channel_url = data.get('channel_url', '')
                channel_id_match = re.search(r'channel/([^/]+)', channel_url)
                actual_channel_id = channel_id_match.group(1) if channel_id_match else channel_id
                
                uploader = data.get('uploader', 'Unknown')
                channel_handle = data.get('channel', '')
                
                return {
                    'channel_id': actual_channel_id,
                    'name': uploader,
                    'handle': f"@{channel_handle}" if channel_handle else '',
                    'avatar_url': data.get('thumbnails', [{}])[-1].get('url', '') if data.get('thumbnails') else '',
                    'subscribers': data.get('channel_follower_count', 'N/A'),
                    'videos': data.get('channel_video_count', 'N/A'),
                    'views': 'N/A',
                    'country': 'N/A',
                    'custom_url': '',
                    'description': data.get('description', '')[:200]
                }
            return None
        except Exception as e:
            return None
    
    def fetch_with_api(self, channel_ids):
        results = []
        
        if not channel_ids or not self.api_key:
            return results
        
        ids = ','.join(channel_ids[:50])
        url = f"https://www.googleapis.com/youtube/v3/channels?id={ids}&part=statistics,snippet&key={self.api_key}"
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                return results
            
            data = response.json()
            
            if 'error' in data:
                return results
            
            for item in data.get('items', []):
                stats = item.get('statistics', {})
                snippet = item.get('snippet', {})
                thumbnails = snippet.get('thumbnails', {})
                avatar_url = thumbnails.get('high', {}).get('url', '')
                if not avatar_url:
                    avatar_url = thumbnails.get('medium', {}).get('url', '')
                if not avatar_url:
                    avatar_url = thumbnails.get('default', {}).get('url', '')
                
                results.append({
                    'channel_id': item.get('id', ''),
                    'name': snippet.get('title', 'Unknown'),
                    'handle': f"@{snippet.get('customUrl', '').lower()}" if snippet.get('customUrl') else '',
                    'avatar_url': avatar_url,
                    'subscribers': int(stats.get('subscriberCount', 0)),
                    'videos': int(stats.get('videoCount', 0)),
                    'views': int(stats.get('viewCount', 0)),
                    'country': snippet.get('country', 'N/A'),
                    'custom_url': snippet.get('customUrl', ''),
                    'description': snippet.get('description', '')[:200]
                })
            return results
        except Exception:
            return results
    
    def process_channels(self, channel_ids, max_channels=1000):
        all_results = []
        
        if not channel_ids:
            return all_results
        
        if len(channel_ids) > max_channels:
            print(f"Limiting from {len(channel_ids)} to {max_channels} channels")
            channel_ids = channel_ids[:max_channels]
        
        use_api = bool(self.api_key)
        
        if use_api:
            print(f"Using YouTube API to process {len(channel_ids)} channels...")
            
            batches = [channel_ids[i:i+50] for i in range(0, len(channel_ids), 50)]
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(self.fetch_with_api, batch) for batch in batches]
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        results = future.result()
                        all_results.extend(results)
                        print(f"API batch completed: {len(all_results)}/{len(channel_ids)} channels")
                    except Exception:
                        pass
            
            if len(all_results) < len(channel_ids):
                print(f"API only returned {len(all_results)}/{len(channel_ids)} channels, falling back to yt-dlp...")
                failed_ids = [cid for cid in channel_ids if not any(r['channel_id'] == cid for r in all_results)]
                
                for channel_id in failed_ids:
                    print(f"Fetching {channel_id} with yt-dlp...")
                    result = self.fetch_with_ytdlp(channel_id)
                    if result:
                        all_results.append(result)
                    time.sleep(1)
        else:
            print(f"No API key found, using yt-dlp for {len(channel_ids)} channels...")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self.fetch_with_ytdlp, channel_id): channel_id for channel_id in channel_ids}
                
                for future in concurrent.futures.as_completed(futures):
                    channel_id = futures[future]
                    try:
                        result = future.result()
                        if result:
                            all_results.append(result)
                            print(f"yt-dlp fetched: {result['name']} ({len(all_results)}/{len(channel_ids)})")
                        else:
                            print(f"Failed to fetch {channel_id}")
                    except Exception:
                        pass
                    time.sleep(0.5)
        
        self.results = all_results
        print(f"Completed: {len(self.results)}/{len(channel_ids)} channels processed")
        return self.results
    
    def process_single_channel(self, channel_id):
        result = None
        
        if self.api_key:
            api_result = self.fetch_with_api([channel_id])
            if api_result:
                result = api_result[0]
        
        if not result:
            result = self.fetch_with_ytdlp(channel_id)
        
        return result if result else None
    
    def save_to_csv(self, filename):
        if not self.results:
            return
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['channel_id', 'name', 'handle', 'subscribers', 'videos', 'views', 'country', 'avatar_url', 'description'])
            writer.writeheader()
            writer.writerows(self.results)
        print(f"Saved {len(self.results)} channels to {filename}")
    
    def save_to_json(self, filename):
        if not self.results:
            return
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(self.results)} channels to {filename}")
    
    def get_results(self):
        return self.results

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python channel_processor.py <channel_ids_file>")
        print("Or: python channel_processor.py --single <channel_id>")
        print("Or: python channel_processor.py --url <channel_url>")
        sys.exit(1)
    
    if sys.argv[1] == '--single' and len(sys.argv) >= 3:
        processor = ConcurrentChannelProcessor(max_workers=1)
        result = processor.process_single_channel(sys.argv[2])
        if result:
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps({'error': 'Channel not found'}))
        sys.exit(0)
    
    if sys.argv[1] == '--url' and len(sys.argv) >= 3:
        processor = ConcurrentChannelProcessor(max_workers=1)
        channel_url = sys.argv[2]
        channel_id_match = re.search(r'channel/([^/]+)', channel_url)
        if channel_id_match:
            channel_id = channel_id_match.group(1)
            result = processor.process_single_channel(channel_id)
            if result:
                print(json.dumps(result, indent=2))
            else:
                print(json.dumps({'error': 'Channel not found'}))
        else:
            print(json.dumps({'error': 'Invalid channel URL'}))
        sys.exit(0)
    
    try:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            channel_ids = [line.strip() for line in f if line.strip()]
        
        if not channel_ids:
            print("No channel IDs found in file")
            sys.exit(1)
        
        print(f"Loaded {len(channel_ids)} channel IDs from {sys.argv[1]}")
        
    except FileNotFoundError:
        print(f"File not found: {sys.argv[1]}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
    
    max_channels = 1000
    if len(sys.argv) >= 3 and sys.argv[2].isdigit():
        max_channels = int(sys.argv[2])
    
    processor = ConcurrentChannelProcessor(max_workers=10)
    results = processor.process_channels(channel_ids, max_channels)
    
    if results:
        output_dir = os.path.dirname(sys.argv[1]) or '.'
        output_file = os.path.join(output_dir, 'channels_output.csv')
        processor.save_to_csv(output_file)
        
        json_file = os.path.join(output_dir, 'channels_output.json')
        processor.save_to_json(json_file)
        
        print(json.dumps({'total': len(results), 'csv_file': output_file, 'json_file': json_file}))
    else:
        print(json.dumps({'error': 'No results returned', 'total': 0}))
        sys.exit(1)

if __name__ == "__main__":
    main()