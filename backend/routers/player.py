import os
import sys
import json
import subprocess
import shutil
import asyncio
import pathlib
import time
from datetime import datetime, timedelta
from typing import Optional, List, Union
from fastapi import APIRouter, HTTPException, Depends, Request, Response, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging

from ..database import get_db, Program, Topic, EPGProgram, ScheduledRecording, AutoReservation, Channel, SessionLocal
from ..live_stream import live_manager
from ..logger_config import get_logger
from ..utils import parse_time, is_bilingual_program, is_terrestrial_station, BILINGUAL_MARKERS
from ..settings_manager import load_settings, split_ffmpeg_options
import threading
from ..playback_session import playback_session_manager

logger = get_logger(__name__, "app.log")

# --- Robust Cleanup Helper ---
def cleanup_ff_robust(proc, name="FFmpeg"):
    """
    Standardized process cleanup helper using polling to avoid wait() hangs.
    Works for both subprocess.Popen and asyncio.subprocess.Process objects.
    """
    if not proc: return
    
    # Detect if it's asyncio process
    is_async = not hasattr(proc, 'poll')
    
    def wait_and_kill():
        try:
            pid = proc.pid
            logger.info(f"Cleanup Thread: Started for {name} (PID {pid}, async={is_async})")
            
            # 1. Send terminate signal
            try: proc.terminate()
            except: pass
            
            # 2. Wait and Poll
            start_wait = time.time()
            grace_period = 4.0
            terminated = False
            
            while time.time() - start_wait < grace_period:
                # asyncio process uses returncode attribute directly
                ret = proc.returncode if is_async else proc.poll()
                if ret is not None:
                    logger.info(f"Cleanup Thread: {name} (PID {pid}) terminated gracefully")
                    terminated = True
                    break
                time.sleep(0.5)
            
            # 3. Force Kill if still alive
            if not terminated:
                logger.warning(f"Cleanup Thread: {name} (PID {pid}) did not terminate, killing...")
                try: proc.kill()
                except: pass
                # Short final wait
                start_kill_wait = time.time()
                while time.time() - start_kill_wait < 2.0:
                    ret = proc.returncode if is_async else proc.poll()
                    if ret is not None: break
                    time.sleep(0.2)
                logger.info(f"Cleanup Thread: {name} (PID {pid}) force killed/waited")
            
            # 4. Close pipes AFTER process is dead
            for p_name in ['stdin', 'stdout', 'stderr']:
                p = getattr(proc, p_name, None)
                if p:
                    try: p.close()
                    except: pass
            logger.debug(f"Cleanup Thread: pipes closed for {name} (PID {pid})")
        except Exception as e:
            logger.error(f"Cleanup Thread Error for {name}: {e}")
            
    threading.Thread(target=wait_and_kill, daemon=True).start()

player_router = APIRouter(prefix="/api", tags=["video"])

# Global map to store buffer status per session: {session_id: {"ahead": float, "last_update": float}}
buffer_status_map = {}

VIDEO_PATH_CACHE = {}

@player_router.post("/video/status/{session_id}")
async def report_buffer_status(session_id: str, data: dict):
    """
    Receives buffer status from the client.
    data format: {"ahead": seconds_ahead}
    """
    ahead = data.get("ahead", 0)
    # logger.debug(f"DEBUG_BUFFER: session={session_id}, ahead={ahead}")
    buffer_status_map[session_id] = {
        "ahead": float(ahead),
        "last_update": time.time()
    }
    # Cleanup old sessions
    if len(buffer_status_map) > 200:
        now = time.time()
        expired = [sid for sid, info in buffer_status_map.items() if now - info["last_update"] > 600]
        for sid in expired:
            del buffer_status_map[sid]
            
    return {"status": "ok"}

@player_router.delete("/video/status/{session_id}")
async def stop_video_session(session_id: str):
    """
    Forcefully stops a video session by removing it from the buffer map.
    The background manage_playback thread will detect this and kill the process.
    """
    if session_id in buffer_status_map:
        del buffer_status_map[session_id]
    return {"status": "ok"}

def get_video_info(path: str):
    """
    Returns actual duration and detailed stream info (organized by programs) using ffprobe.
    """
    if not os.path.exists(path):
        return {"duration": 0, "audio_tracks": 0, "programs": []}
    
    cache_key = f"info_v2_{path}_{os.path.getmtime(path)}"
    if cache_key in VIDEO_PATH_CACHE:
        return VIDEO_PATH_CACHE[cache_key]

    info = {"duration": 0, "audio_tracks": 0, "programs": [], "best_program_id": None, "best_video_index": 0}
    if not shutil.which("ffprobe"):
        return info

    try:
        # Deep probe for program structure
        cmd = [
            "ffprobe", "-v", "error", 
            "-analyzeduration", "15M", "-probesize", "15M",
            "-show_programs", "-show_format",
            "-of", "json", path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            format_data = data.get("format", {})
            info["duration"] = float(format_data.get("duration", 0))
            
            programs = data.get("programs", [])
            info["programs"] = programs
            
            # Find the "best" program (one with the highest resolution video)
            best_prog = None
            max_width = -1
            
            for prog in programs:
                for s in prog.get("streams", []):
                    if s.get("codec_type") == "video":
                        w = int(s.get("width") or 0)
                        if w > max_width:
                            max_width = w
                            best_prog = prog
            
            if best_prog:
                info["best_program_id"] = best_prog.get("program_id")
                # Find the video stream index within this program
                for s in best_prog.get("streams", []):
                    if s.get("codec_type") == "video":
                        val = s.get("index")
                        if val is not None:
                            info["best_video_index"] = val
                        break
                
                audio_streams = [s for s in best_prog.get("streams", []) if s.get("codec_type") == "audio"]
                info["audio_tracks"] = len(audio_streams)
                info["program_audio_indices"] = [s.get("index") for s in audio_streams]
            else:
                # Fallback to simple counting if no programs found
                all_audio = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
                info["audio_tracks"] = len(all_audio)
                info["program_audio_indices"] = [s.get("index") for s in all_audio]
            
        VIDEO_PATH_CACHE[cache_key] = info
    except Exception as e:
        logger.error(f"get_video_info error: {e}")
        
    return info

def get_player_path():
    possible_paths = [
        # VLC Priority (User Request)
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        # MPV Fallback
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\mpv.net\mpvnet.exe"),
        r"C:\Program Files\mpv.net\mpvnet.exe",
        r"C:\Program Files\mpv.net\mpv.net.exe",
        r"C:\Program Files\mpv\mpv.exe",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    if shutil.which("vlc"): return "vlc"
    if shutil.which("mpvnet"): return "mpvnet"
    if shutil.which("mpv"): return "mpv"
            
    return None

def generate_mpv_edl(items, output_path):
    """
    Generate MPV EDL (Edit Decision List).
    items: list of dict { "path": str, "start": float, "stop": float, "title": str }
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# mpv EDL v0\n")
        
        for item in items:
            path_str = item.get("path", "")
            # Ensure header-less format v0
            # EDL spec: [timestamps] [filename]
            # But standard mpv edl file format is:
            # path,start,length
            # Special chars in path need escaping?  MPV docs say:
            # "There are no escapes." but commas are delimiters.
            # %length% syntax is needed if file path has commas?
            # Let's try to verify if paths have commas.
            # Replace comma with %2C just in case.
            
            # Using absolute path with forward slashes
            # MPV on Windows handles forward slashes well and it avoids escape issues
            abs_path = os.path.abspath(path_str).replace("\\", "/")
            
            start = item.get("start", 0)
            stop = item.get("stop", 0)
            
            length = stop - start
            if length <= 0:
                length = 999999
            
            # Use raw path in EDL instead of URI
            # Check for commas
            if "," in abs_path:
                logger.warning(f"WARNING: Path contains comma, might fail in EDL: {abs_path}")
                # Try to strict percent encode comma only? 
                # Or assume no commas based on logs.
            
            f.write(f"{abs_path},{start},{length}\n")

class PlaybackRequest(BaseModel):
    filepath: str
    start_time: str = "0"
    start_index: int = 0

class PlaylistRequest(BaseModel):
    items: List[dict] # {filepath, start, end, title}
    start_index: int = 0

@player_router.post("/play")
def play_video(req: PlaybackRequest, request: Request, db: Session = Depends(get_db)):
    try:
        logger.debug(f"Play Request for filepath: {req.filepath}")
        
        prog = db.query(Program).filter(Program.filepath == req.filepath).first()
        topics = []
        if prog:
            logger.debug(f"Found Program: {prog.title} (ID: {prog.id})")
            topics = db.query(Topic).filter(Topic.program_id == prog.id).order_by(Topic.start_time).all()
        else:
            logger.debug("Program NOT found in DB!")
            raise HTTPException(status_code=404, detail="Program not found in DB")
        
        # Unified time parser moved to common_utils.py

        items = []
        if not topics:
             logger.debug("No topics found, playing file from start.")
             items.append({
                 "start": 0,
                 "stop": 0,
                 "title": prog.title
             })
        else:
            logger.debug(f"Found {len(topics)} topics.")
            for t in topics:
                start = parse_time(t.start_time)
                end = parse_time(t.end_time)
                
                items.append({
                    "start": start,
                    "stop": end,
                    "title": t.title
                })
            
            # Add Opening if starts later
            if items and items[0]['start'] > 1.0:
                logger.debug("Adding Opening chapter")
                items.insert(0, {
                    "start": 0.0,
                    "stop": items[0]['start'],
                    "title": "Opening / 番組開始"
                })
        
        # --- Adjust Stop Times for Continuous Playback ---
        for i in range(len(items) - 1):
             next_start = items[i+1]['start']
             if next_start > items[i]['start']:
                 items[i]['stop'] = next_start

        # Generate Stream URL
        host = request.headers.get("host")
        scheme = request.url.scheme
        video_url = f"{scheme}://{host}/api/video/{prog.id}"
        
        # Generate M3U content in memory
        lines = ["#EXTM3U"]
        for item in items:
            # Format start time to HH:MM:SS
            m, s = divmod(int(item['start']), 60)
            h, m = divmod(m, 60)
            start_str = f"{h:02d}:{m:02d}:{s:02d}"
            
            display_title = f"[{start_str}] {item['title']}"
            
            # Set duration in EXTINF to -1 for continuous playback without skip
            lines.append(f"#EXTINF:-1,{display_title}")
            
            # URL with server-side cut params
            # No VLC options (start-time) to prevent client seeking
            separator = "&" if "?" in video_url else "?"
            full_url = f"{video_url}{separator}start={item['start']}"
            
            # Removed 'end' param to allow playback to continue past topic end
            # if item['stop'] > item['start']:
            #      full_url += f"&end={item['stop']}"
            
            lines.append(full_url)
        
        content = "\n".join(lines)
        
        filename = f"playlist_{prog.id}.m3u"
        return Response(
            content=content,
            media_type="audio/x-mpegurl",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    except Exception as e:
        logger.error(f"Error creating Playlist: {e}")
        return {"status": "Error", "message": str(e)}


@player_router.post("/stream/stop/{stream_id}")
def stop_live_stream_explicit(stream_id: str):
    # Endpoint to manually stop a live stream
    # Used when frontend explicitly closes the player
    try:
        if stream_id.startswith("live_"):
            logger.debug(f"Explicit Stop Request for: {stream_id}")
            live_manager.stop_stream(stream_id)
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"Stop Error: {e}")
    return {"status": "ignored"}

# split_ffmpeg_options moved to settings_manager.py

def _resolve_video_path(program_id_str: str, db: Session) -> Optional[str]:
    """Resolves a program ID or recording ID to a physical file path."""
    video_path = None
    if program_id_str.startswith("rec_"):
        try:
            rec_id = int(program_id_str.replace("rec_", ""))
            rec = db.query(ScheduledRecording).filter(ScheduledRecording.id == rec_id).first()
            if rec: video_path = rec.result_path
        except: pass
    elif program_id_str.isdigit():
        try:
            pid = int(program_id_str)
            prog = db.query(Program).filter(Program.id == pid).first()
            if prog:
                video_path = prog.filepath
            else:
                rec = db.query(ScheduledRecording).filter(ScheduledRecording.id == pid).first()
                if rec: video_path = rec.result_path
        except: pass
    
    if video_path:
        # Check for MP4 override
        base, ext = os.path.splitext(video_path)
        if os.path.exists(f"{base}.mp4"):
            video_path = f"{base}.mp4"
            
    return video_path

def _get_video_context(program_id_str: str, video_path: str, db: Session):
    """Detects if recording is active and if program is dual-mono (bilingual)."""
    is_recording_active = False
    is_dual_mono = False
    
    try:
        start_time_check = time.time()
        # 1. Recording Activity
        if program_id_str.startswith("rec_"):
            rec_rid = int(program_id_str.replace("rec_", ""))
            r_obj = db.query(ScheduledRecording).filter(ScheduledRecording.id == rec_rid).first()
            if r_obj and r_obj.status == "recording":
                is_recording_active = True
        
        if not is_recording_active and video_path:
            norm_target = os.path.normpath(video_path).lower()
            active = db.query(ScheduledRecording).filter(ScheduledRecording.status == "recording").all()
            for r in active:
                if r.result_path and os.path.normpath(r.result_path).lower() == norm_target:
                    is_recording_active = True
                    break

        # 2. Dual Mono Detection
        context_obj = None
        if program_id_str.startswith("rec_"):
            context_obj = db.query(ScheduledRecording).filter(ScheduledRecording.id == int(program_id_str.replace("rec_", ""))).first()
        elif program_id_str.isdigit():
            context_obj = db.query(Program).filter(Program.id == int(program_id_str)).first()
            
        if context_obj:
            is_dual_mono = is_bilingual_program(context_obj.title, context_obj.description, video_path)
    except Exception as e:
        logger.debug(f"Video context check error: {e}")
    
    elapsed = (time.time() - start_time_check) * 1000
    if elapsed > 100:
        logger.warning(f"Video context check took {elapsed:.1f}ms for {video_path}")
    
    return is_recording_active, is_dual_mono

def build_ffmpeg_args(video_path, info, start, end, req_format, audio_idx, pan_mode, is_dual_mono, is_cast, settings, is_hls=False):
    """Builds a list of FFmpeg arguments based on format and hardware settings."""
    input_args = []
    output_args = []
    
    selected_video_idx = info.get("best_video_index", 0)
    program_audio_indices = info.get("program_audio_indices", [])
    
    # 1. Base Hardware & Quality Settings
    custom_opts = settings.get("ffmpeg_options", "-vf \"yadif,format=nv12\" -c:v h264_qsv -b:v 5000k -preset veryfast -c:a aac")
    input_args, output_args = split_ffmpeg_options(custom_opts)
    
    # 2. Cast (MP4) Specific Overrides
    if req_format == "mp4":
        # Standard Fragmented MP4 for web/cast streaming
        output_format = "mp4"
        movflags = "frag_keyframe+empty_moov+default_base_moof+frag_discont"
        
        # Audio Standardization (AAC 192k)
        if "-c:a" in output_args:
            output_args[output_args.index("-c:a")+1] = "aac"
        else:
            output_args.extend(["-c:a", "aac"])
        output_args.extend(["-b:a", "192k"])
    else:
        output_format = "hls" if is_hls else "mpegts"
        movflags = None

    # 3. Audio Filter / Mapping
    af_filters = ["aresample=async=1"]
    if req_format == "mp4" and is_dual_mono:
        if pan_mode == "left": af_filters.append("pan=stereo|c0=c0|c1=c0")
        elif pan_mode == "right": af_filters.append("pan=stereo|c0=c1|c1=c1")

    # Mapping
    target_audio_idx = program_audio_indices[audio_idx] if audio_idx < len(program_audio_indices) else f"a:{audio_idx}"
    
    # Build Final Command List
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "warning"]
    cmd.extend(["-probesize", "15M", "-analyzeduration", "5M"])
    cmd.extend(["-fflags", "+genpts+igndts+discardcorrupt", "-err_detect", "ignore_err"])
    
    # QSV Device Init
    if any("qsv" in str(a) for a in input_args + output_args):
        if os.name != 'nt':
            # Linux: Direct DRI device access
            qsv_device = settings.get("qsv_device_path") or "/dev/dri/renderD128"
            if not any("-init_hw_device" in str(a) for a in input_args + output_args):
                cmd.extend(["-init_hw_device", f"qsv=qsv:hw_any,child_device={qsv_device}", "-filter_hw_device", "qsv"])
        else:
            # Windows: Standard device init
            if not any("-init_hw_device" in str(a) for a in input_args + output_args):
                cmd.extend(["-init_hw_device", "qsv=qsv:hw_any", "-filter_hw_device", "qsv"])

    # Input Flags (excluding pacing)
    stable_keys = {"-probesize", "-analyzeduration", "-fflags", "-err_detect", "-readrate", "-re", "-thread_queue_size"}
    for i in range(0, len(input_args)-1, 2):
        if input_args[i] not in stable_keys:
            cmd.extend([input_args[i], input_args[i+1]])

    if start > 0: cmd.extend(["-ss", str(float(start))])
    cmd.extend(["-thread_queue_size", "4096"])
    
    # Pacing (Adaptive for browser, 1x for Cast)
    is_adaptive = settings.get("adaptive_streaming_enabled", False) and not is_cast
    # For Cast, -re is often required for stable delivery to the device
    if not is_adaptive: cmd.extend(["-re"])
    
    # Input File

    return cmd, output_args, output_format, movflags, selected_video_idx, target_audio_idx, af_filters

@player_router.get("/video/{program_id_str}")
async def stream_video_file(
    program_id_str: str, 
    request: Request,
    start: Union[float, str] = 0, 
    end: Union[float, str, None] = None, 
    format: Optional[str] = None,
    session: Optional[str] = None,
    db: Session = Depends(get_db),
    session_id: Optional[str] = None
):
    final_session_id = session_id or session or request.query_params.get("session") or request.query_params.get("session_id")
    is_cast = request.query_params.get("cast") == "1"
    if is_cast:
        logger.info(f"CAST_REQUEST (ID: {program_id_str}) from {request.client.host}")
    
    # 0. Live Stream Handling
    if program_id_str.startswith("live_"):
        try:
            parts = program_id_str.split("_")
            type_str, ch_str, sid_str = parts[1], parts[2], parts[3]
            
            audio_idx = int(request.query_params.get("audio", 0))
            is_bilingual = False
            try:
                db_local = SessionLocal()
                # Simple bilingual check for live
                now = datetime.now()
                prog = db_local.query(EPGProgram).join(Channel, EPGProgram.channel == Channel.channel_id).filter(
                    Channel.sid == int(sid_str), EPGProgram.start_time <= now, EPGProgram.end_time > now
                ).first()
                if prog: is_bilingual = is_bilingual_program(prog.title, prog.description)
                db_local.close()
            except: pass

            live_info = live_manager.start_stream(program_id_str, type_str, ch_str, sid_str, audio_idx=audio_idx, is_bilingual=is_bilingual)
            proc = live_info["proc"]
            session_id = live_info["session_id"]
            
            async def iter_live():
                # 接続監視タスク
                async def watch_disconnect():
                    try:
                        while True:
                            if await request.is_disconnected():
                                logger.info(f"Live disconnect detected for session={session_id}")
                                live_manager.stop_stream(live_info["stream_id"], only_session=session_id)
                                break
                            await asyncio.sleep(1)
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.debug(f"iter_live watch_disconnect error: {e}")

                disconnect_task = asyncio.create_task(watch_disconnect())
                try:
                    while True:
                        data = await asyncio.to_thread(proc.stdout.read, 65536)
                        if not data: break
                        yield data
                finally:
                    disconnect_task.cancel()
                    try:
                        await disconnect_task
                    except: pass
                    live_manager.stop_stream(live_info["stream_id"], only_session=session_id)
            
            return StreamingResponse(iter_live(), media_type="video/mp2t")
        except Exception as e:
            logger.error(f"Live Stream Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # 1. Resolve Path & Context
    video_path = _resolve_video_path(program_id_str, db)
    if not video_path: raise HTTPException(status_code=404, detail="File not found")
    
    if video_path.lower().endswith(".mp4") and os.path.exists(video_path):
         return FileResponse(video_path, media_type="video/mp4", filename=os.path.basename(video_path))

    is_recording_active, is_dual_mono = _get_video_context(program_id_str, video_path, db)
    
    # 2. Parameters Preparation
    start_val = parse_time(start)
    end_val = parse_time(end)
    req_format = format or request.query_params.get("format")
    is_cast = request.query_params.get("cast") == "1"
    audio_idx = int(request.query_params.get("audio", 0))
    pan_mode = request.query_params.get("pan", "stereo")
    settings = load_settings()
    
    info = get_video_info(video_path)
    
    cmd_base, output_args, out_fmt, movflags, v_idx, a_idx, af = build_ffmpeg_args(
        video_path, info, start_val, end_val, req_format, audio_idx, pan_mode, is_dual_mono, is_cast, settings
    )
    # 3. Final Command Construction
    ffmpeg_cmd = cmd_base
    ffmpeg_cmd.extend(["-max_interleave_delta", "10M"])
    
    if is_recording_active and video_path.lower().endswith(".ts"):
        ffmpeg_cmd.extend(["-f", "mpegts", "-follow", "1"])
    
    ffmpeg_cmd.extend(["-i", video_path])
    
    if end_val is not None:
        remaining = float(end_val) - max(0, float(start_val))
        if remaining > 0: ffmpeg_cmd.extend(["-t", str(remaining)])
    
    ffmpeg_cmd.extend(["-g", "60", "-avoid_negative_ts", "make_zero", "-muxdelay", "0"])
    ffmpeg_cmd.extend(["-map", f"0:{v_idx}", "-map", f"0:{a_idx}?" if not isinstance(a_idx, int) else f"0:{a_idx}"])
    
    if af: ffmpeg_cmd.extend(["-af", ",".join(af)])
    ffmpeg_cmd.extend(["-ac", "2", "-ar", "48000", "-max_muxing_queue_size", "8192"])
    ffmpeg_cmd.extend(output_args)
    if movflags: ffmpeg_cmd.extend(["-movflags", movflags])
    ffmpeg_cmd.extend(["-f", out_fmt, "-"])

    # 4. Storage & Streaming
    # --- Adaptive Streaming Persistence Logic (for Recorded/Follow) ---
    # We use PlaybackSessionManager to keep FFmpeg running even if browser disconnects briefly.
    # This specifically addresses the issue where adaptive streaming triggers unnecessary FFmpeg restarts.
    USE_SESSION_STREAMING = True 
    
    if USE_SESSION_STREAMING and not is_cast and final_session_id:
        try:
            params = {
                "video_path": video_path,
                "start": start_val,
                "end": end_val,
                "audio_idx": audio_idx,
                "pan_mode": pan_mode,
                "format": req_format,
                "is_recording_active": is_recording_active
            }
            
            # Construct final command
            safe_cmd = [str(arg) for arg in ffmpeg_cmd]
            
            session = await playback_session_manager.get_or_create_session(
                final_session_id, safe_cmd, params
            )
            
            async def paced_session_stream():
                sent = 0
                chunk_size = settings.get("stream_chunk_size", 512 * 1024)
                burst_limit = settings.get("burst_transmission_size", 10 * 1024 * 1024)
                is_adaptive = settings.get("adaptive_streaming_enabled", True) and not is_cast
                
                async for chunk in session.get_stream():
                    yield chunk
                    sent += len(chunk)
                    
                    if is_adaptive:
                        # Adaptive Pacing Logic based on buffer feedback
                        ahead = 0
                        if final_session_id and final_session_id in buffer_status_map:
                            info = buffer_status_map[final_session_id]
                            if time.time() - info["last_update"] < 10:
                                ahead = info["ahead"]
                        
                        # 1. First 20MB is always burst (Initial speed)
                        if sent < burst_limit:
                            continue
                            
                        # 2. Dynamic Throttling based on 'ahead'
                        if ahead > 25:
                            delay = (len(chunk) / (5 * 1024 * 1024 / 8))
                            await asyncio.sleep(delay)
                        elif ahead > 15:
                            delay = (len(chunk) / (20 * 1024 * 1024 / 8))
                            await asyncio.sleep(delay)
                        elif ahead > 3:
                            delay = (len(chunk) / (40 * 1024 * 1024 / 8))
                            await asyncio.sleep(delay)

            headers = {
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
                "X-Playback-Session": final_session_id
            }
            
            return StreamingResponse(paced_session_stream(), media_type=f"video/{out_fmt}", headers=headers)
            
        except Exception as e:
            logger.error(f"Session-based streaming failed, falling back to legacy: {e}")
            # Fallback to legacy iterfile below

    async def iterfile(session_id=None):
        logger.info(f"DEBUG_LOOP: Starting iterfile for session={session_id}")
        try:
            safe_cmd = [str(arg) for arg in ffmpeg_cmd]
            logger.info(f"DEBUG_FFMPEG_CMD: {' '.join(safe_cmd)}")
            
            try:
                proc = await asyncio.create_subprocess_exec(
                    *safe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                is_async = True
            except NotImplementedError:
                import subprocess
                proc = subprocess.Popen(safe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
                is_async = False
            
            async def log_stderr():
                # Common non-critical messages to filter out
                ignore_keywords = [
                    "Could not find codec parameters",
                    "Consider increasing the value",
                    "PES packet size mismatch",
                    "Packet corrupt",
                    "channel element 0.1 is not allocated",
                    "Error submitting packet to decoder",
                    "Invalid data found when processing input",
                    "Invalid frame dimensions 0x0",
                    "Last message repeated",
                    "non-existing PPS 0 referenced",
                    "no frame!",
                    "estimate_timings_from_pts"
                ]
                try:
                    while True:
                        try:
                            line = await (proc.stderr.readline() if is_async else asyncio.to_thread(proc.stderr.readline))
                            if not line: break
                            msg = line.decode('utf-8', errors='replace').strip()
                            if msg:
                                if any(kw in msg for kw in ignore_keywords):
                                    continue
                                logger.info(f"FFMPEG_STDERR (PID {proc.pid}): {msg}")
                        except (OSError, ValueError):
                            break
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

            log_task = asyncio.create_task(log_stderr())
            
            # Pacing Config (Aliged with Settings)
            is_adaptive = settings.get("adaptive_streaming_enabled", True) and not is_cast
            chunk_size = settings.get("stream_chunk_size", 512 * 1024)
            burst_limit = settings.get("burst_transmission_size", 40 * 1024 * 1024)
            
            sent = 0
            start_time = time.time()
            
            # 接続監視タスク
            async def watch_disconnect():
                try:
                    while True:
                        if await request.is_disconnected():
                            logger.info(f"Disconnect detected by watcher for session={session_id}")
                            # Use standardized robust cleanup to avoid hangs
                            cleanup_ff_robust(proc, "FFmpeg (Watcher)")
                            break
                        await asyncio.sleep(1)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.debug(f"watch_disconnect error: {e}")

            disconnect_task = asyncio.create_task(watch_disconnect())
            
            try:
                while True:
                    # Read Data
                    chunk = await (proc.stdout.read(chunk_size) if is_async else asyncio.to_thread(proc.stdout.read, chunk_size))
                    if not chunk: break
                    
                    yield chunk
                    sent += len(chunk)
                    
                    if is_adaptive:
                        # Adaptive Pacing Logic based on buffer feedback
                        if session_id and session_id in buffer_status_map:
                            info = buffer_status_map[session_id]
                            if time.time() - info["last_update"] < 10:
                                ahead = info["ahead"]
                        
                        # 1. First 20MB is always burst (Initial speed)
                        if sent < burst_limit:
                            await asyncio.sleep(0.01) # Small gap to avoid CPU spike
                            continue
                            
                        # 2. Dynamic Throttling based on 'ahead'
                        if ahead > 25:
                            delay = (len(chunk) / (5 * 1024 * 1024 / 8))
                            await asyncio.sleep(delay)
                        elif ahead > 15:
                            delay = (len(chunk) / (20 * 1024 * 1024 / 8))
                            await asyncio.sleep(delay)
                        elif ahead > 3:
                            delay = (len(chunk) / (40 * 1024 * 1024 / 8))
                            await asyncio.sleep(delay)
            finally:
                disconnect_task.cancel()
                try:
                    await disconnect_task
                except: pass
                
                # Ensure logging task is stopped
                log_task.cancel()
                
                # Standardized robust cleanup (Polling-based to avoid wait() hangs)
                cleanup_ff_robust(proc, "FFmpeg (Final)")

                if session_id:
                    logger.info(f"Streaming ended for session={session_id}")
                    if session_id in buffer_status_map:
                        del buffer_status_map[session_id]
        except Exception as e:
            logger.error(f"Iterfile error: {e}")

    headers = {
        "Access-Control-Allow-Origin": "*",
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-cache"
    }
    return StreamingResponse(iterfile(final_session_id), media_type=f"video/{out_fmt}", headers=headers)

class PlaylistRequest(BaseModel):
    items: List[dict] # {filepath, start, end, title}
    start_index: int = 0

@player_router.post("/play_list")
def play_custom_playlist(req: PlaylistRequest, request: Request, db: Session = Depends(get_db)):
    try:
        items = req.items
        if not items:
            return {"status": "Empty Playlist"}
            
        settings = load_settings()
        offset = int(settings.get("topic_offset_sec", 0))
        
        # Apply Offset
        if offset > 0:
            for item in items:
                item['start'] = max(0, item['start'] - offset)

        # --- Adjust Stop Times for Continuous Playback ---
        # Ensure items are sorted by start time
        items.sort(key=lambda x: x['start'])

        for i in range(len(items) - 1):
             # Update current item's stop time to next item's start time
             next_start = items[i+1]['start']
             if next_start > items[i]['start']:
                 items[i]['stop'] = next_start
        
        # Rotate items so the clicked item is first, and previous items go to the end
        if req.start_index > 0 and req.start_index < len(items):
             logger.info(f"DEBUG: Rotating playlist. Start index: {req.start_index}")
             items = items[req.start_index:] + items[:req.start_index]

        # Generate Stream Base URL
        host = request.headers.get("host")
        scheme = request.url.scheme
        
        lines = ["#EXTM3U"]
        for item in items:
            # Find Program ID
            prog = db.query(Program).filter(Program.filepath == item['path']).first()
            
            video_url = ""
            if prog:
                video_url = f"{scheme}://{host}/api/video/{prog.id}"
            else:
                logger.warning(f"WARNING: Program not found for path: {item['path']}")
                video_url = pathlib.Path(item['path']).as_uri()

            # Calculate duration
            duration = max(0, item['stop'] - item['start']) if item['stop'] > item['start'] else 0
            
            # Format start time
            m, s = divmod(int(item['start']), 60)
            h, m = divmod(m, 60)
            start_str = f"{h:02d}:{m:02d}:{s:02d}"
            
            display_title = f"[{start_str}] {item['title']}"
            
            # Set duration in EXTINF to -1
            lines.append(f"#EXTINF:-1,{display_title}")
            
            # URL Param logic (Server-side cut)
            if video_url.startswith("http"):
                separator = "&" if "?" in video_url else "?"
                full_url = f"{video_url}{separator}start={item['start']}"
                
                # Removed 'end' param to allow playback to continue past topic end
                # if item['stop'] > item['start']:
                #      full_url += f"&end={item['stop']}"
                lines.append(full_url)
            else:
                # Fallback for local files (File URI) - Use VLC opts as server can't cut
                lines.append(f"#EXTVLCOPT:start-time={item['start']}")
                lines.append(video_url)
        
        content = "\n".join(lines)
        filename = "playlist_topics.m3u"
        
        return Response(
            content=content,
            media_type="audio/x-mpegurl",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    except Exception as e:
        logger.error(f"Error creating Playlist: {e}")
        return {"status": "Error", "message": str(e)}



