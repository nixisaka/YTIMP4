# YTIMP4

[![GitHub License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)

YTIMP4 is a Python application for downloading YouTube videos, audio, live streams, playlists, channels, and subtitles. It uses `yt-dlp` as its download backend and provides a simple interface for managing downloads.

---

## Installation

Clone the repository and install the required packages:

```bash
git clone https://github.com/nixisaka/YTIMP4.git
cd YTIMP4
pip install -r requirements.txt
```

---

## Running

### Windows

Run:

```bash
python bootstrap.py
```

or start the application using `start.bat`.

### Linux / macOS

Run:

```bash
python3 ytimp4.py
```

---

## Features

- Download videos in MP4 format
- Extract audio as MP3
- Download subtitles in SRT format
- Download live streams and archived streams
- Download playlists and channels
- Queue multiple downloads
- Automatic subtitle retrieval
- Browser cookie detection
- Download history
- Light and dark themes

---

## Dependencies

YTIMP4 requires the following Python packages:

- Flask
- yt-dlp
- requests
- beautifulsoup4
- aiohttp
- colorama
- google-api-python-client

Install or update them with:

```bash
pip install -r requirements.txt
```

On Windows, `start.bat` can automatically create a virtual environment, install missing dependencies, and start the application.

---

## Additional Information

- YTIMP4 uses `yt-dlp` for downloading media from YouTube.
- Some videos may require browser cookies or authentication.
- Download quality depends on the formats provided by YouTube.
- Updating `yt-dlp` regularly is recommended to maintain compatibility with YouTube.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

Copyright © 2026 nixisaka

### Contributors

- FILipKOS
