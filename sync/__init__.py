from flask import jsonify
from pathlib import Path

from .sync_manager import SyncManager

def register_sync_routes(app):
    @app.route('/api/sync_status')
    def sync_status():
        sync_mgr = SyncManager(Path(__file__).parent)
        return jsonify(sync_mgr.get_sync_status())
    
    @app.route('/api/sync_scan', methods=['POST'])
    def sync_scan():
        sync_mgr = SyncManager(Path(__file__).parent)
        sync_mgr.scan_files()
        return jsonify({"success": True, "files": len(sync_mgr.manifest["files"])})
    
    @app.route('/api/sync_modified')
    def sync_modified():
        sync_mgr = SyncManager(Path(__file__).parent)
        return jsonify({"modified": sync_mgr.get_modified_files()})
    
    app.logger.info("Registered sync routes")