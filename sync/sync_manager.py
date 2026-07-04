import os
import json
import hashlib
import time
from pathlib import Path
from datetime import datetime

class SyncManager:
    def __init__(self, sync_folder=None):
        if sync_folder is None:
            sync_folder = Path(__file__).parent
        self.sync_folder = Path(sync_folder)
        self.sync_file = self.sync_folder / "sync.json"
        self.project_root = self.find_project_root()
        self.manifest = self.load_sync()
    
    def find_project_root(self):
        current = self.sync_folder.parent
        while current != current.parent:
            if (current / "ytimp4.py").exists():
                return current
            current = current.parent
        return self.sync_folder.parent
    
    def load_sync(self):
        if self.sync_file.exists():
            with open(self.sync_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data["project_root"] = str(self.project_root)
                return data
        return {
            "version": "1.0.0",
            "last_scan": datetime.now().isoformat(),
            "project_root": str(self.project_root),
            "structure": {
                "root_files": [],
                "folders": {}
            },
            "files": {},
            "folders": {}
        }
    
    def save_sync(self):
        self.manifest["last_scan"] = datetime.now().isoformat()
        self.manifest["project_root"] = str(self.project_root)
        with open(self.sync_file, 'w', encoding='utf-8') as f:
            json.dump(self.manifest, f, indent=2)
    
    def get_file_hash(self, file_path):
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()
    
    def scan_files(self):
        self.manifest["files"] = {}
        
        for root, dirs, files in os.walk(self.project_root):
            if '__pycache__' in root or '.venv' in root or '.git' in root:
                continue
            for file in files:
                if file.endswith('.pyc'):
                    continue
                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(self.project_root))
                stat = file_path.stat()
                self.manifest["files"][rel_path] = {
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "hash": self.get_file_hash(file_path)
                }
        
        self.save_sync()
    
    def get_modified_files(self):
        modified = []
        for rel_path, info in self.manifest["files"].items():
            file_path = self.project_root / rel_path
            if file_path.exists():
                current_hash = self.get_file_hash(file_path)
                if current_hash != info["hash"]:
                    modified.append(rel_path)
        return modified
    
    def get_sync_status(self):
        return {
            "total_files": len(self.manifest["files"]),
            "last_scan": self.manifest["last_scan"],
            "version": self.manifest["version"],
            "project_root": str(self.project_root)
        }