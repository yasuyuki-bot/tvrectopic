import os
import shutil
import asyncio
import uuid
import time
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..logger_config import get_logger
from ..settings_manager import load_settings
from .player import _resolve_video_path, get_video_info, build_ffmpeg_args, _get_video_context

logger = get_logger(__name__, "app.log")
hls_router = APIRouter(prefix="/api/hls", tags=["hls"])

TEMP_HLS_DIR = os.path.join(os.getcwd(), "temp_hls")
# os.makedirs(TEMP_HLS_DIR, exist_ok=True) # Commented out to prevent automatic folder creation

class HLSSessionManager:
    def __init__(self):
        self.sessions = {} # session_id -> { proc, dir, last_access }

    async def start_session(self, video_path, start_time, audio_idx, db, duration=None):
        if not os.path.exists(TEMP_HLS_DIR):
            os.makedirs(TEMP_HLS_DIR, exist_ok=True)
            
        session_id = str(uuid.uuid4())
        session_dir = os.path.join(TEMP_HLS_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)

        m3u8_path = os.path.join(session_dir, "index.m3u8")
        master_path = os.path.join(session_dir, "master.m3u8")
        
        info = get_video_info(video_path)
        settings = load_settings()
        is_rec, is_dual = _get_video_context("", video_path, db) # program_id_str not strictly needed for context if path is provided

        cmd_base, output_args, out_fmt, movflags, v_idx, a_idx, af = build_ffmpeg_args(
            video_path, info, start_time, None, "hls", audio_idx, "stereo", is_dual, True, settings, is_hls=True
        )

        cmd = cmd_base
        cmd.extend(["-i", video_path])
        
        # HLS Specific
        cmd.extend(["-g", "30", "-sc_threshold", "0"])
        cmd.extend(["-map", f"0:{v_idx}", "-map", f"0:{a_idx}?" if not isinstance(a_idx, int) else f"0:{a_idx}"])
        
        if af: cmd.extend(["-af", ",".join(af)])
        
        cmd.extend(output_args)
        
        # HLS specific flags
        cmd.extend([
            "-f", "hls",
            "-hls_time", "2",
            "-hls_flags", "independent_segments",
            "-hls_list_size", "0",
            "-master_pl_name", "master.m3u8",
            m3u8_path
        ])

        try:
            log_file_path = os.path.join(session_dir, "ffmpeg.log")
            log_file = open(log_file_path, "w")
            
            try:
                proc = await asyncio.create_subprocess_exec(
                    *[str(c) for c in cmd],
                    stdout=log_file,
                    stderr=log_file
                )
            except NotImplementedError:
                # Fallback for Windows where ProactorEventLoop might not be the default
                import subprocess
                proc = subprocess.Popen(
                    [str(c) for c in cmd],
                    stdout=log_file,
                    stderr=log_file,
                    stdin=subprocess.DEVNULL
                )
            
            self.sessions[session_id] = {
                "proc": proc,
                "dir": session_dir,
                "last_access": time.time()
            }
            
            # Wait for master m3u8 to be generated
            for _ in range(50):
                if os.path.exists(master_path):
                    break
                await asyncio.sleep(0.1)
                
            if not os.path.exists(master_path):
                logger.error(f"HLS master m3u8 generation timeout! Check {log_file_path}")
                try:
                    with open(log_file_path, "r") as f:
                        logger.error(f"FFmpeg Log: {f.read()[-1000:]}")
                except Exception:
                    pass
                raise Exception("HLS m3u8 generation failed or timed out.")
                
            return session_id
        except Exception as e:
            logger.error(f"HLS FFmpeg start failed: {e}")
            raise e

    async def stop_session(self, session_id):
        if session_id in self.sessions:
            sess = self.sessions[session_id]
            proc = sess["proc"]
            try: proc.terminate()
            except: pass
            
            try:
                shutil.rmtree(sess["dir"], ignore_errors=True)
            except: pass
            
            del self.sessions[session_id]

    async def cleanup_loop(self):
        while True:
            await asyncio.sleep(60)
            now = time.time()
            expired = []
            for sid, sess in self.sessions.items():
                if now - sess["last_access"] > 300: # 5 minutes threshold
                    expired.append(sid)
            for sid in expired:
                await self.stop_session(sid)

hls_manager = HLSSessionManager()

@hls_router.on_event("startup")
async def on_startup():
    shutil.rmtree(TEMP_HLS_DIR, ignore_errors=True)
    # os.makedirs(TEMP_HLS_DIR, exist_ok=True) # Prevent startup folder creation
    asyncio.create_task(hls_manager.cleanup_loop())

@hls_router.on_event("shutdown")
async def on_shutdown():
    for sid in list(hls_manager.sessions.keys()):
        await hls_manager.stop_session(sid)

@hls_router.post("/start/{program_id_str}")
async def start_hls(program_id_str: str, request: Request, start: float = 0, audio: int = 0, db: Session = Depends(get_db)):
    video_path = _resolve_video_path(program_id_str, db)
    if not video_path:
        raise HTTPException(status_code=404, detail="File not found")
        
    session_id = await hls_manager.start_session(video_path, start_time=start, audio_idx=audio, db=db)
    
    # Use real IP rather than request host, since localhost/127.0.0.1 won't work on the Cast receiver
    from ..main import get_local_ip
    server_ip = get_local_ip()
    scheme = request.url.scheme
    m3u8_url = f"{scheme}://{server_ip}:8000/api/hls/{session_id}/master.m3u8"
    
    return JSONResponse({"session_id": session_id, "m3u8_url": m3u8_url})

@hls_router.post("/stop/{session_id}")
async def stop_hls(session_id: str):
    await hls_manager.stop_session(session_id)
    return {"status": "ok"}

@hls_router.get("/{session_id}/{filename}")
async def get_hls_file(session_id: str, filename: str):
    if session_id not in hls_manager.sessions:
        raise HTTPException(status_code=404, detail="HLS session not found")
        
    sess = hls_manager.sessions[session_id]
    sess["last_access"] = time.time()
    
    file_path = os.path.join(sess["dir"], filename)
    if not os.path.exists(file_path):
        for _ in range(150): # Wait up to 15 seconds for the segment to finish
            await asyncio.sleep(0.1)
            if os.path.exists(file_path):
                break
        if not os.path.exists(file_path):
            logger.error(f"HLS file Not Found after wait: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")
            
    media_type = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/MP2T"
    return FileResponse(file_path, media_type=media_type)
