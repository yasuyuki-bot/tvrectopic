import os
import sys
import json
import subprocess
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
import logging

from ..database import get_db
from ..crud import epg as crud_epg
from ..logger_config import get_logger

logger = get_logger(__name__, "app.log")

# Find the absolute path to the directory containing the 'backend' package
PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# BASE_DIR is the 'backend' directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Global to track the running EPG update process
active_epg_process = None

epg_router = APIRouter(prefix="/api/epg", tags=["epg"])
search_router = APIRouter(prefix="/api/search", tags=["search"])
genres_router = APIRouter(prefix="/api/genres", tags=["genres"])

@search_router.get("/programs")
def search_programs(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    return crud_epg.search_programs(db, q)

@search_router.get("/topics")
def search_topics(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    return crud_epg.search_topics(db, q)

@genres_router.get("")
def get_genres(db: Session = Depends(get_db)):
    return crud_epg.get_genres(db)

# --- EPG API ---

@epg_router.get("")
def get_epg(start: int = 0, end: int = 0, type: Optional[str] = None, db: Session = Depends(get_db)):
    now_ts = int(datetime.now().timestamp())
    if start == 0: start = now_ts
    if end == 0: end = now_ts + 86400
    return crud_epg.get_epg(db, start, end, type)

@epg_router.get("/status")
def get_epg_status():
    status_file = os.path.join(BASE_DIR, "epg_status.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"running": False, "progress": 0, "current_channel": "", "completed": 0, "total": 0}

@epg_router.get("/range")
def get_epg_range(db: Session = Depends(get_db)):
    return crud_epg.get_epg_range(db)

@epg_router.post("/update")
def update_epg_endpoint(background_tasks: BackgroundTasks, type: Optional[str] = None):
    def run_update():
        global active_epg_process
        try:
            # Use -m to run as a module for robust imports
            cmd = [sys.executable, "-m", "backend.update_epg"]
            if type:
                cmd.append(type)
            
            log_path = os.path.join(os.path.dirname(__file__), "epg_update.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n--- EPG Update Started at {datetime.now()} (Manual) ---\n")
                f.write(f"Command: {cmd}\n")
                f.flush()
                
                # Start as process group on Linux to kill children (rec tuner commands)
                kwargs = {}
                if os.name != 'nt':
                    kwargs['preexec_fn'] = os.setsid
                
                active_epg_process = subprocess.Popen(
                    cmd, cwd=PACKAGE_ROOT, stdout=f, stderr=f, **kwargs
                )
                active_epg_process.wait()
                f.write(f"\n--- EPG Update Finished/Terminated at {datetime.now()} ---\n")

            logger.info("EPG Update script finished (checked epg_update.log).")
        except Exception as e:
            logger.error(f"EPG Update Error: {e}")
        finally:
            active_epg_process = None
            # Ensure status is reset to False in case of crash or termination
            status_file = os.path.join(BASE_DIR, "epg_status.json")
            try:
                with open(status_file, "w", encoding="utf-8") as f:
                    json.dump({"running": False, "progress": 0, "current_channel": "停止 (中断)", "completed": 0, "total": 0}, f, ensure_ascii=False)
            except: pass

    background_tasks.add_task(run_update)
    return {"status": "Update started", "type": type}

@epg_router.post("/cancel")
def cancel_epg_update():
    global active_epg_process
    if active_epg_process and active_epg_process.poll() is None:
        logger.info(f"Cancelling EPG Update process (PID: {active_epg_process.pid})...")
        try:
            if os.name == 'nt':
                active_epg_process.terminate()
            else:
                import signal
                # Kill the entire process group (including child recdvb etc.)
                os.killpg(active_epg_process.pid, signal.SIGTERM)
            return {"status": "Cancellation successful"}
        except Exception as e:
            logger.error(f"Failed to cancel EPG process: {e}")
            return {"status": "Error", "detail": str(e)}
    return {"status": "No process running"}
