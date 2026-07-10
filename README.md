# YTIMP4

[![GitHub License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)

**YouTube Downloader** — download YouTube videos, audio, live streams, and subtitles.

---

## Installation

```bash
git clone https://github.com/nixisaka/YTIMP4.git
cd YTIMP4
pip install -r requirements.txt
```

Alternatively, download the latest release from the GitHub Releases page.

---

## Running

### Windows

Double-click `start.bat` or run:

```bash
python bootstrap.py
```

### Linux / macOS

```bash
python3 ytimp4.py
```

---

## Features

- MP4 video downloads (1080p+ where available)
- MP3 audio extraction with embedded thumbnails
- SRT subtitle downloads
- Live stream and archive downloads
- Channel downloads
- Batch downloads with queue support
- Automatic subtitle retrieval
- Browser cookie detection
- Download history
- Light and dark themes

---

## Dependencies

YTIMP4 depends on the following Python packages:

- Flask
- yt-dlp
- requests
- beautifulsoup4
- aiohttp
- colorama
- google-api-python-client

Install them with:

```bash
pip install -r requirements.txt
```

If dependency installation fails on Windows, run `start.bat`. It will attempt to create a virtual environment, install the required packages, and start the application automatically.

---

## License

MIT License

Copyright © 2026 nixisaka

### Contributors

- FILipKOS
