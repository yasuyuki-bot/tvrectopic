from ..logger_config import get_logger
logger = get_logger(__name__, "app.log")
import os
import sys
import json
import subprocess
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..crud import channel as crud_channel

router = APIRouter(prefix="/api/settings", tags=["settings"])
channels_router = APIRouter(prefix="/api/channels", tags=["channels"])

# Find the absolute path to the directory containing the 'backend' package
PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# BASE_DIR is the 'backend' directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
SCAN_STATUS_FILE = os.path.join(BASE_DIR, "scan_status.json")

def load_settings():
    from ..settings_manager import load_settings as ls
    return ls()

def save_settings(data):
    from ..settings_manager import save_settings as ss
    return ss(data)

@router.post("/scan-channels")
def start_scan_channels(background_tasks: BackgroundTasks):
    def run_scan():
        try:
            # Use -m to run as a module for robust imports, from the package root
            cmd = [sys.executable, "-m", "backend.scan_terrestrial"]
            subprocess.run(cmd, cwd=PACKAGE_ROOT)
        except Exception as e:
            logger.error(f"Scan Error: {e}")

    # Reset status
    with open(SCAN_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump({"scanning": True, "progress": 0, "current_channel": "Start", "results": []}, f)

    background_tasks.add_task(run_scan)
    return {"message": "Scan started"}

@router.get("/scan-status")
def get_scan_status():
    if os.path.exists(SCAN_STATUS_FILE):
        try:
            with open(SCAN_STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # If file is locked or corrupted, return 503 so frontend keeps polling
            raise HTTPException(status_code=503, detail="Status file temporarily unavailable")
    
    # Only return default stopped if file truly doesn't exist (e.g. before first scan)
    return {"scanning": False, "progress": 0, "current_channel": "", "results": []}

@router.get("/defaults")
def get_default_settings():
    from ..settings_manager import get_default_settings as gds
    return gds()

@router.get("/ffmpeg-presets")
def get_ffmpeg_presets():
    from ..settings_manager import FFMPEG_PRESETS
    return FFMPEG_PRESETS

@router.get("")
def get_settings():
    return load_settings()

@router.post("")
def update_settings(settings: dict):
    # Retrieve current to merge if needed, or just overwrite
    current = load_settings()
    current.update(settings)
    save_settings(current)
    return current

@channels_router.get("")
def get_channels(db: Session = Depends(get_db)):
    try:
        from ..database import Channel
        channels = db.query(Channel).all()
        
        results = []
        for c in channels:
            results.append({
                "id": c.id,
                "type": c.type,
                "channel": c.channel_id,
                "TP": c.TP,
                "slot": c.slot,
                "service_id": c.sid,
                "network_id": c.network_id,
                "name": c.service_name,
                "visible": c.visible,
                "is_dynamic": True
            })
            
        type_order = {"GR": 1, "BS": 2, "CS": 3}
        def get_ch_num(ch_v):
            if not ch_v: return (999, "")
            try: return (0, int(ch_v))
            except: return (1, str(ch_v))

        results.sort(key=lambda x: (
            type_order.get(x['type'], 99), 
            get_ch_num(x.get('channel')) if x['type'] == 'GR' else (0, 0),
            x.get('service_id') or 0
        ))
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@channels_router.delete("/{channel_id}")
def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    try:
        from ..database import Channel
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        db.delete(channel)
        db.commit()
        return {"status": "deleted", "id": channel_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@channels_router.post("/config")
def update_channel_config(config: List[dict], db: Session = Depends(get_db)):
    try:
        updated_count = crud_channel.update_channel_config(db, config)
        return {
            "status": "Updated", 
            "debug": [
                f"Processed {len(config)} items",
                f"Updated {updated_count} items in database"
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
