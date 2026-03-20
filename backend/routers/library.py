import os
import threading
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging
from datetime import datetime, timedelta

from ..database import get_db, Topic, Program, SessionLocal, Channel, EPGProgram, ScheduledRecording

logger = logging.getLogger(__name__)

library_router = APIRouter(prefix="/api", tags=["library"])

def load_settings():
    try:
        from ..settings_manager import load_settings as ls
    except (ImportError, ValueError):
        from settings_manager import load_settings as ls
    return ls()

try:
    from .player import get_video_info, BILINGUAL_MARKERS
except (ImportError, ValueError):
    try:
        from player import get_video_info, BILINGUAL_MARKERS
    except (ImportError, ValueError):
        from backend.routers.player import get_video_info, BILINGUAL_MARKERS

class FolderRequest(BaseModel):
    path: Optional[str] = None
    model_name: Optional[str] = None
    batch_size: Optional[int] = None
    api_key: Optional[str] = None

class PlaybackRequest(BaseModel):
    filepath: str
    start_time: str = "0"
    start_index: int = 0

@library_router.get("/scan/progress")
def get_scan_progress():
    try:
        from ..extract import scan_progress
    except:
        from extract import scan_progress
    return scan_progress


# Refactored Scan Logic
def run_scan_thread(scan_targets, batch_size, model_name, api_key, skip_topics=False):
    t_db = SessionLocal()
    try:
        try:
            from ..extract import scan_and_update
        except:
            from extract import scan_and_update
        scan_and_update(scan_targets, t_db, batch_size=batch_size, model_name=model_name, api_key=api_key, skip_topics=skip_topics)
    finally:
        t_db.close()

@library_router.post("/scan")
def scan_endpoint(req: Optional[FolderRequest] = None, db: Session = Depends(get_db)):
    try:
        from ..extract import scan_progress
    except:
        from extract import scan_progress
    if scan_progress.get("scanning", False):
        return {"message": "Scan already in progress", "status": "running"}

    settings = load_settings()
    scan_targets = []
    if req and req.path:
         scan_targets = [{"path": req.path, "recursive": False}]
    else:
         scan_targets = settings.get("topic_scan_folders", [])
         # If no topic folders, maybe fallback to recording folder?
         if not scan_targets and settings.get("recording_folder"):
             scan_targets = [{"path": settings["recording_folder"], "recursive": False}]

    if not scan_targets:
         raise HTTPException(status_code=400, detail="No scan targets configured")

    api_key_to_use = req.api_key if req and req.api_key else settings.get("gemini_api_key")
    if not api_key_to_use:
         raise HTTPException(status_code=400, detail="Gemini API Key is not configured")
    
    model_to_use = req.model_name if req and req.model_name else settings.get("gemini_model_name", "gemini-2.5-flash")
    batch_size_to_use = req.batch_size if req and req.batch_size else settings.get("topic_batch_size", 4)

    t = threading.Thread(target=run_scan_thread, args=(scan_targets, batch_size_to_use, model_to_use, api_key_to_use, False))
    t.start()
             
    return {"message": "Scan started in background", "status": "started"}

@library_router.post("/library/scan")
def library_scan_endpoint(db: Session = Depends(get_db)):
    try:
        from ..extract import scan_progress
    except:
        from extract import scan_progress
    if scan_progress.get("scanning", False):
        return {"message": "Scan already in progress", "status": "running"}

    settings = load_settings()
    scan_targets = settings.get("topic_scan_folders", [])
    if not scan_targets and settings.get("recording_folder"):
         scan_targets = [{"path": settings["recording_folder"], "recursive": False}]

    if not scan_targets:
         raise HTTPException(status_code=400, detail="No scan targets configured")

    # No API Key needed for library scan
    t = threading.Thread(target=run_scan_thread, args=(scan_targets, 4, None, None, True))
    t.start()
    
    return {"message": "Library scan started", "status": "started"}

@library_router.get("/schedule")
def get_schedule(date: str, db: Session = Depends(get_db)):
    from datetime import datetime, timedelta
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        next_day = dt + timedelta(days=1)
        results = db.query(Program).filter(
            Program.start_time >= dt,
            Program.start_time < next_day
        ).order_by(Program.start_time).all()
        return [p.to_dict() for p in results]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

@library_router.get("/folders")
def get_folders():
    drives = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
    return drives

@library_router.get("/files")
def get_files(path: str = Query(...)):
    if not os.path.exists(path):
        return []
    try:
        entries = os.scandir(path)
        result = []
        for e in entries:
            result.append({
                "name": e.name,
                "path": e.path,
                "is_dir": e.is_dir()
            })
        return sorted(result, key=lambda x: (not x['is_dir'], x['name']))
    except:
        return []

@library_router.get("/programs")
def get_programs(db: Session = Depends(get_db)):
    return [p.to_dict() for p in db.query(Program).order_by(Program.start_time.desc()).all()]

try:
    from ..live_stream import live_manager
except:
    from live_stream import live_manager

@library_router.get("/programs/{program_id_str}")
def get_program_detail(program_id_str: str, db: Session = Depends(get_db)):
    # 0. Live Stream
    if program_id_str.startswith("live_"):
        parts = program_id_str.split("_")
        # Format: live_TYPE_CH_SID
        type_str = parts[1]
        ch_str = parts[2]
        sid_str = parts[3]
        
        # Resolve Name
        # Resolve Channel Name from DB
        try:
            try:
                from ..database import Channel
            except:
                from database import Channel
            with SessionLocal() as db_sess:
                c = db_sess.query(Channel).filter(
                    Channel.sid == sid_str,
                    Channel.type == type_str
                ).first()
                if c:
                    title = f"LIVE: {c.service_name}"
        except: pass

        # Try to find actual program title from EPG
        title = "Live Broadcast"
        audio_tracks = 1
        try:
            db = SessionLocal()
            now = datetime.now()
            # Find program that is currently airing on this service
            prog = db.query(EPGProgram).join(Channel, EPGProgram.channel == Channel.channel_id).filter(
                Channel.sid == int(sid_str),
                EPGProgram.start_time <= now,
                EPGProgram.end_time > now
            ).first()
            if prog:
                title = prog.title
                description = prog.description or ""
                # Heuristic: Check for bilingual markers in title and description
                text_to_scan = f"{title} {description}"
                if any(m in text_to_scan for m in BILINGUAL_MARKERS):
                    audio_tracks = 2
            db.close()

        except: pass

        return {
            "id": program_id_str,
            "title": title,
            "description": "Live Broadcast / 現在放送中",
            "channel": ch_str if type_str=='GR' else sid_str,
            "start_time": datetime.now().isoformat(),
            "end_time": (datetime.now() + timedelta(hours=83)).isoformat(),
            "duration": 300000,
            "filepath": "", 
            "topics": [], 
            "video_format": "ts",
            "audio_tracks": audio_tracks,
            "is_live": True
        }

    # 1. Check for "rec_" prefix (ScheduledRecording)
    if program_id_str.startswith("rec_"):
        try:
            rec_id = int(program_id_str.replace("rec_", ""))
            rec = db.query(ScheduledRecording).filter(ScheduledRecording.id == rec_id).first()
            if rec:
                # Mock a Program object response
                base, ext = os.path.splitext(rec.result_path) if rec.result_path else ("", "")
                formats = []
                video_format = "ts"
                
                # Check for MP4 variant
                if rec.result_path:
                    mp4_path = f"{base}.mp4"
                    if os.path.exists(mp4_path):
                         video_format = "mp4"

                # Get actual info if file exists
                is_recording = (rec.status == "recording")
                scheduled_duration = (rec.end_time - rec.start_time).total_seconds()
                actual_info = {"duration": scheduled_duration, "audio_tracks": 1}

                if rec.result_path and os.path.exists(rec.result_path):
                    # For recording icons, probe current duration but still report scheduled_duration for UI
                    probe_info = get_video_info(rec.result_path)
                    actual_info["audio_tracks"] = probe_info.get("audio_tracks", 1)
                    if not is_recording:
                        actual_info["duration"] = probe_info.get("duration", scheduled_duration)
                    
                    # If only 1 track but title has markers, it's Dual Mono
                    if actual_info["audio_tracks"] == 1:
                        text_to_scan = f"{rec.title} {rec.description or ''}"
                        if any(m in text_to_scan for m in BILINGUAL_MARKERS):
                            actual_info["audio_tracks"] = 2

                return {
                    "id": program_id_str, # Keep the string ID
                    "title": rec.title,
                    "description": rec.description,
                    "channel": rec.channel,
                    "start_time": rec.start_time.isoformat(),
                    "end_time": rec.end_time.isoformat(),
                    "duration": actual_info["duration"],
                    "audio_tracks": actual_info["audio_tracks"],
                    "filepath": rec.result_path or "", # Might be empty
                    "topics": [], # No topics for raw recordings yet
                    "video_format": video_format,
                    "is_recording": (rec.status == "recording")
                }
        except: pass
        
    # 2. Check for numeric ID (Program)
    try:
        if program_id_str.isdigit():
            pid = int(program_id_str)
            prog = db.query(Program).filter(Program.id == pid).first()
            if prog:
                d = prog.to_dict()
                # Check MP4
                if prog.filepath:
                    base, ext = os.path.splitext(prog.filepath)
                    mp4_path = f"{base}.mp4"
                    if os.path.exists(mp4_path):
                        d['video_format'] = "mp4"
                    else:
                        d['video_format'] = "ts"
                    
                    # Add actual duration/audio info
                    actual_info = get_video_info(prog.filepath)
                    d['duration'] = actual_info['duration']
                    d['audio_tracks'] = actual_info['audio_tracks']
                    if d['audio_tracks'] == 1:
                        text_to_scan = f"{prog.title} {prog.description or ''}"
                        if any(m in text_to_scan for m in BILINGUAL_MARKERS):
                            d['audio_tracks'] = 2
                else:
                    d['video_format'] = "ts"
                    d['audio_tracks'] = 1
                return d
    except: pass
    
    raise HTTPException(status_code=404, detail="Program not found")

