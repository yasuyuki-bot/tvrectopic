import asyncio
import sys
import logging

# ==============================================================================
# Python Windows asyncio Policy & Warning Filters (MUST BE AT THE TOP)
# ==============================================================================
import warnings
# Silence DeprecationWarnings (especially for Python 3.14) to keep logs clean.
warnings.filterwarnings("ignore", category=DeprecationWarning)

if sys.platform == 'win32':
    # Force ProactorEventLoopPolicy as the most stable for Windows.
    # We must do this as early as possible before any loops are created.
    import asyncio.windows_events
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ==============================================================================

import unicodedata
from fastapi import FastAPI, HTTPException, Query, Depends, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Union
from sqlalchemy import text
import os
from datetime import datetime, timedelta
import shutil
import glob
import subprocess
import pathlib
import tempfile
import urllib.parse
import json
import threading
import time
from .logger_config import get_logger

BILINGUAL_MARKERS = ["【二】", "[二]", "(二)", "二か国語", "二ヵ国語", "二カ国語", "Bilingual", "multilingual", "主・副", "主+副", "副音声", "Dual Mono"]

# Setup Logging
logger = get_logger(__name__, "app.log", level=logging.DEBUG, backup_count=2)

from .database import get_db, Program, Topic, EPGProgram, ScheduledRecording, AutoReservation, init_db, SessionLocal, Channel
from .extract import scan_and_update
from .recorder import recorder
from .auto_reserve_logic import run_all_auto_reservations, search_programs as search_auto_res_programs, match_program


app = FastAPI()

# 移行したルーターの登録
from .routers.settings import router as settings_router, channels_router
from .routers.recordings import auto_res_router, record_router, reservations_router, recorded_router
from .routers.epg import epg_router, search_router, genres_router
from .routers.player import player_router
from .routers.library import library_router
from .routers.logs import router as logs_router

app.include_router(settings_router)
app.include_router(channels_router)
app.include_router(auto_res_router)
app.include_router(record_router)
app.include_router(reservations_router)
app.include_router(recorded_router)
app.include_router(epg_router)
app.include_router(search_router)
app.include_router(genres_router)
app.include_router(player_router)
app.include_router(library_router)
app.include_router(logs_router)


# Mount Videos directory for efficient streaming (reduce Python overhead)
# This assumes videos are stored under the user's "Videos" directory.
# If files are elsewhere, they will fallback to the slower FileResponse.
video_root = os.path.expanduser("~\\Videos")
if os.path.exists(video_root):
    app.mount("/videos_static", StaticFiles(directory=video_root), name="videos")

# Configure CORS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Add specific IP origins if not internal
try:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    local_ip = s.getsockname()[0]
    origins.append(f"http://{local_ip}:5173")
    origins.append(f"http://{local_ip}:8000")
    s.close()
except:
    pass

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log video requests ONLY at debug level if needed (currently disabled)
    # if "/api/video" in request.url.path:
    #     logger.debug(f"VIDEO_REQUEST: {request.method} {request.url.path} from {request.client.host}")
    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global cache for local IP to reduce log noise
_cached_local_ip = None

def get_local_ip():
    global _cached_local_ip
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        # 8.8.8.8 used to detect the interface that has internet access
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
        s.close()
        
        if ip != _cached_local_ip:
            logger.info(f"Detected local IP for external access: {ip}")
            _cached_local_ip = ip
        return ip
    except Exception:
        return _cached_local_ip or "127.0.0.1"

@app.get("/api/server-ip")
def get_server_ip():
    return {"ip": get_local_ip()}

def _check_running_recordings_epg(db: Session, now: datetime, checked_set: set):
    """EPG periodic check during recording (10m and 5m before end)"""
    try:
        running_recs = db.query(ScheduledRecording).filter(ScheduledRecording.status == "recording").all()
        for rec in running_recs:
            for mark_mins in [10, 5]:
                # Unique key including end_time to re-trigger if extended
                check_key = f"{rec.id}_{mark_mins}_{int(rec.end_time.timestamp())}"
                if check_key in checked_set:
                    continue
                
                trigger_time = rec.end_time - timedelta(minutes=mark_mins)
                if now >= trigger_time:
                    logger.info(f"Scheduler: Triggering Running EPG Check for {rec.title} (Mark: {mark_mins}m before end)")
                    checked_set.add(check_key)
                    
                    def run_check(res_id):
                        try:
                            from .realtime_epg import check_and_update_running_recording_epg
                            check_and_update_running_recording_epg(res_id)
                        except Exception as err:
                            logger.error(f"Error in background running EPG check: {err}")
                    
                    threading.Thread(target=run_check, args=(rec.id,), daemon=True).start()

        # Cleanup old cache entries
        if len(checked_set) > 100:
            running_ids = {r.id for r in running_recs}
            stale = {k for k in checked_set if int(k.split('_')[0]) not in running_ids}
            for k in stale: checked_set.remove(k)
    except Exception as e:
        logger.error(f"Running EPG monitor error: {e}")

def _check_upcoming_recordings_epg(db: Session, now: datetime, checked_set: set, checking_set: set):
    """EPG check before recording starts (13m rule)"""
    try:
        # Look ahead 2 hours for scheduling congestion
        upcoming = db.query(ScheduledRecording).filter(
            ScheduledRecording.status == "scheduled",
            ScheduledRecording.start_time <= now + timedelta(minutes=120),
            ScheduledRecording.start_time > now + timedelta(seconds=180)
        ).all()

        for item in upcoming:
            state_key = f"{item.id}_{item.start_time.timestamp()}"
            if state_key in checked_set or state_key in checking_set:
                continue
            
            item_type = "BS_CS" if (item.channel and ("BS" in item.channel or "CS" in item.channel)) else "GR"

            target_trigger = item.start_time - timedelta(minutes=13)

            # Optimization: Skip if another recording is already running/scheduled on the same channel at the 13m check mark
            prev_prog = db.query(ScheduledRecording).filter(
                ScheduledRecording.channel == item.channel,
                ScheduledRecording.service_id == item.service_id,
                ScheduledRecording.id != item.id,
                ScheduledRecording.status.in_(["scheduled", "recording"]),
                ScheduledRecording.start_time <= target_trigger,
                ScheduledRecording.end_time >= target_trigger
            ).first()

            if prev_prog:
                logger.info(f"Scheduler: Skipping 13m EPG check for '{item.title}' (Tuner expected busy with '{prev_prog.title}' at trigger time)")
                checked_set.add(state_key)
                continue

            should_trigger = False
            
            if now >= target_trigger:
                should_trigger = True
            else:
                # Proactive early trigger if tuners are expected to be busy at the 13m mark
                if recorder.is_tuner_busy_at(db, target_trigger, item_type, exclude_res_id=item.id):
                    if not recorder.is_tuner_busy_at(db, now, item_type, exclude_res_id=item.id):
                        logger.info(f"Scheduler: Proactive EPG Check for '{item.title}' (Tuner predicted busy, checking early)")
                        should_trigger = True

            if should_trigger:
                checking_set.add(state_key)
                logger.info(f"Scheduler: Triggering Real-time EPG Check for {item.title}")
                
                def run_check(res_id, s_key):
                    try:
                        from .realtime_epg import check_and_update_realtime_epg
                        if check_and_update_realtime_epg(res_id) is True:
                            checked_set.add(s_key)
                    finally:
                        if s_key in checking_set: checking_set.remove(s_key)

                threading.Thread(target=run_check, args=(item.id, state_key), daemon=True).start()
        
        # Periodic cleanup of checked set
        cutoff = now - timedelta(hours=1)
        stale = {k for k in checked_set if float(k.split('_')[1]) <= cutoff.timestamp()}
        for k in stale: checked_set.remove(k)
    except Exception as e:
        logger.error(f"Real-time EPG hook logic error: {e}")

# Recording Scheduler
def recording_schedule_loop():
    logger.info("Recording Scheduler started")
    
    REALTIME_EPG_CHECKED = set()
    REALTIME_EPG_CHECKING = set()
    RUNNING_EPG_CHECKED = set()

    while True:
        try:
            now = datetime.now()
            settings = recorder.load_settings()
            db = SessionLocal()
            
            # --- EPG Stability Checks ---
            _check_running_recordings_epg(db, now, RUNNING_EPG_CHECKED)
            _check_upcoming_recordings_epg(db, now, REALTIME_EPG_CHECKED, REALTIME_EPG_CHECKING)
            
            # Find scheduled items starting soon
            start_margin = int(settings.get("recording_start_margin", 5))
            upcoming = db.query(ScheduledRecording).filter(
                ScheduledRecording.status == "scheduled",
                ScheduledRecording.start_time <= now + timedelta(seconds=start_margin),
                ScheduledRecording.end_time > now # Still valid
            ).all()
            
            for item in upcoming:
                logger.info(f"Scheduler: Starting Recording {item.title}")
                duration = (item.end_time - now).total_seconds()
                if duration < 0: duration = 10
                
                ch_str = item.channel
                ch_type = "GR"
                if item.service_id:
                     info = recorder.get_channel_info(item.service_id, network_id=item.network_id)
                     if info and info.get('type'):
                         ch_type = info.get('type')
                
                if ch_type == "GR" and ch_str:
                    if ch_str.startswith("BS"): ch_type = "BS"
                    elif ch_str.startswith("CS"): ch_type = "CS"
                
                # Consecutive recording margin
                try:
                    margin = int(settings.get("recording_margin_end"))
                    if margin > 0:
                        margin_window_start = item.end_time - timedelta(seconds=1)
                        margin_window_end = item.end_time + timedelta(seconds=1)
                        
                        conflict_next = db.query(ScheduledRecording).filter(
                             ScheduledRecording.status == "scheduled",
                             ScheduledRecording.start_time >= margin_window_start,
                             ScheduledRecording.start_time <= margin_window_end,
                             ScheduledRecording.id != item.id
                        ).first()
                        
                        if conflict_next:
                             logger.info(f"Scheduler: Consecutive recording detected! Applying margin -{margin}s to {item.title}")
                             duration -= margin
                             if duration < 5: duration = 5
                except Exception as ex:
                    logger.error(f"Margin Check Error: {ex}")
                
                success, msg = recorder.start_recording(
                    program_id=item.id,
                    channel_type=ch_type,
                    channel=ch_str,
                    duration=int(duration),
                    db=db,
                    recording_folder=item.recording_folder,
                    network_id=item.network_id
                )
                if not success:
                    logger.error(f"[Scheduler] Failed to start recording {item.id}: {msg}")
                    item.status = "failed"
                else:
                    db.commit()
            
            db.close()
            time.sleep(1)
            
        except Exception as e:
             logger.error(f"Recording Scheduler Error: {e}")
             try: db.close()
             except: pass
             time.sleep(5)

# Update Config Scheduler
def update_loop():
    logger.info(f"EPG/Topic Update Loop started (PID: {os.getpid()})")
    last_epg_run = {} # Track last EPG run
    last_topic_run = {} # Track last run per schedule index
    
    while True:
        try:
            now = datetime.now()
            now_str = now.strftime("%H:%M")
            weekday = now.weekday()
            today_date = now.strftime("%Y-%m-%d")
            
            try:
                from backend.settings_manager import load_settings
            except ImportError:
                from settings_manager import load_settings
                
            settings = load_settings()
            
            # 1. EPG Updates
            times = settings.get("update_times", [])
            for t_str in times:
                if t_str == now_str:
                    run_key = f"{today_date}_{now_str}"
                    if last_epg_run.get(run_key):
                        continue

                    logger.info(f"Scheduler: Triggering EPG update at {now_str} (PID: {os.getpid()})")
                    last_epg_run[run_key] = True
                    
                    # Use -m to run as a module to fix import errors on Linux
                    # Project root is parent of backend/
                    backend_dir = os.path.dirname(os.path.realpath(__file__))
                    proj_root = os.path.dirname(backend_dir)
                    epg_log_path = os.path.join(backend_dir, "epg_update.log")
                    
                    cmd = [sys.executable, "-m", "backend.update_epg"]
                    with open(epg_log_path, "a", encoding="utf-8") as f:
                        f.write(f"\n--- Scheduled EPG Update Started at {datetime.now()} ---\n")
                        subprocess.run(cmd, cwd=proj_root, stdout=f, stderr=f)
                    time.sleep(60)

            # 2. Topic Updates
            topic_schedules = settings.get("topic_schedules", [])
            for idx, sched in enumerate(topic_schedules):
                if sched.get("time") == now_str:
                    # Guard against double execution in the same minute
                    run_key = f"{idx}_{today_date}_{now_str}"
                    if last_topic_run.get(run_key):
                        continue

                    days = sched.get("days", [])
                    if weekday in days:
                        logger.info(f"Scheduler: Triggering Topic Scan at {now_str} (Key: {run_key}, PID: {os.getpid()})")
                        last_topic_run[run_key] = True
                        batch_size = int(sched.get("batch_size", 4))
                        model_name = sched.get("model", "gemini-2.5-flash")
                        
                        def run_scan():
                             try:
                                 from .settings_manager import load_settings as ls
                                 current_settings = ls()
                                 targets = current_settings.get("topic_scan_folders", [])
                                 if not targets and current_settings.get("recording_folder"):
                                      targets = [{"path": current_settings["recording_folder"], "recursive": False}]
                                 
                                 if targets:
                                     try:
                                         from .extract import scan_and_update
                                     except (ImportError, ValueError):
                                         from extract import scan_and_update
                                     scan_and_update(targets, None, batch_size, model_name)
                             except Exception as e:
                                 logger.error(f"Topic Scan Error: {e}")
                        
                        threading.Thread(target=run_scan, daemon=True).start()
                        time.sleep(60)
                        break
            time.sleep(10)
        except Exception as e:
             logger.error(f"Scheduler Error: {e}")
             time.sleep(60)

# Start Scheduler on Startup
@app.on_event("startup")
def startup_event():
    init_db()
    
    # Migration
    from .database import SessionLocal, ScheduledRecording
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE scheduled_recordings ADD COLUMN recording_folder VARCHAR"))
        db.commit()
    except: pass

    # Cleanup stuck recordings
    try:
        stuck = db.query(ScheduledRecording).filter(ScheduledRecording.status == "recording").all()
        for s in stuck:
            logger.info(f"Cleaning up stuck recording: {s.title}")
            s.status = "failed"
        db.commit()
    except Exception as e:
        logger.error(f"Cleanup Error: {e}")
        db.rollback()
    finally:
        db.close()

    # Reset EPG Status
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        epg_status_path = os.path.join(BASE_DIR, "epg_status.json")
        with open(epg_status_path, "w", encoding="utf-8") as f:
            json.dump({
                "running": False, "progress": 0, "current_channel": "", "completed": 0, "total": 0
            }, f, ensure_ascii=False)
    except: pass

    # For asyncio.create_subprocess_exec on Windows Python 3.14+
    if sys.platform == 'win32':
        loop = asyncio.get_running_loop()
        logger.info(f"STARTUP DIAGNOSTIC: Active Event Loop Type is: {type(loop).__name__}")
        if not isinstance(loop, getattr(asyncio, "ProactorEventLoop", type(None))):
             logger.info("Using SelectorEventLoop with Python 3.14 stability patch.")
        
        try:
            # Set the policy globally just in case threads/reloads need it
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception as e:
            logger.error(f"Failed to set WindowsProactorEventLoopPolicy: {e}")

    threading.Thread(target=update_loop, daemon=True).start()
    threading.Thread(target=recording_schedule_loop, daemon=True).start()

# Serve Frontend Static Files (Production)
frontend_dist = os.path.join(os.path.dirname(__file__), "../frontend/dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
