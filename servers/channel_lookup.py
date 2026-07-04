from flask import jsonify
from .channel_lookup import channel_lookup_bp
from pathlib import Path

def register_blueprints(app):
    app.register_blueprint(channel_lookup_bp, url_prefix='/api')
    
    @app.route('/api/sync_status')
    def sync_status():
        from sync.sync_manager import SyncManager
        sync_mgr = SyncManager(Path(__file__).parent.parent / "sync")
        return jsonify(sync_mgr.get_sync_status())
    
    @app.route('/api/sync_scan', methods=['POST'])
    def sync_scan():
        from sync.sync_manager import SyncManager
        sync_mgr = SyncManager(Path(__file__).parent.parent / "sync")
        sync_mgr.scan_files()
        return jsonify({"success": True, "files": len(sync_mgr.manifest["files"])})
    
    @app.route('/api/sync_modified')
    def sync_modified():
        from sync.sync_manager import SyncManager
        sync_mgr = SyncManager(Path(__file__).parent.parent / "sync")
        return jsonify({"modified": sync_mgr.get_modified_files()})
    
    app.logger.info("Registered channel_lookup blueprint")
    app.logger.info("All blueprints registered successfully")