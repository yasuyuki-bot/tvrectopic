from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime
import unicodedata
import os

try:
    from ..database import EPGProgram, Channel, Program, ScheduledRecording, Topic
except ImportError:
    from database import EPGProgram, Channel, Program, ScheduledRecording, Topic

def search_programs(db: Session, query: str):
    norm_q = unicodedata.normalize('NFKC', query).lower()
    
    # Search in Scanned Programs
    results = db.query(Program).filter(
        (func.lower(Program.title).contains(norm_q)) | (func.lower(Program.description).contains(norm_q))
    ).all()
    data = [p.to_dict() for p in results]
    
    # Search in Unscanned Recordings
    unscanned = db.query(ScheduledRecording).filter(
        (ScheduledRecording.status.in_(["completed", "stopped", "recording"])) &
        ((func.lower(ScheduledRecording.title).contains(norm_q)) | (func.lower(ScheduledRecording.description).contains(norm_q)))
    ).order_by(ScheduledRecording.start_time.desc()).all()
    
    scanned_paths = {p.filepath for p in results if p.filepath}
    
    # Filesystem check optimization: collect unique directories to list once
    target_dirs = set()
    for r in unscanned:
        if r.result_path:
            target_dirs.add(os.path.dirname(r.result_path))
    
    dir_cache = {}
    for d in target_dirs:
        if os.path.exists(d):
            try:
                dir_cache[d] = set(os.listdir(d))
            except:
                dir_cache[d] = set()

    for r in unscanned:
        path_to_check = r.result_path
        if not path_to_check: continue
        
        dirname = os.path.dirname(path_to_check)
        basename = os.path.basename(path_to_check)
        
        # Check cache instead of disk if dir is cached
        if dirname in dir_cache:
            if basename not in dir_cache[dirname]:
                continue # File doesn't exist
            
            # Check for mp4 variant in cache
            if basename.endswith(".ts"):
                mp4_basename = basename[:-3] + ".mp4"
                if mp4_basename in dir_cache[dirname]:
                    path_to_check = os.path.join(dirname, mp4_basename)
        else:
            # Fallback to os.path.exists if not in cached dirs (unlikely)
            if not os.path.exists(path_to_check):
                continue

        if path_to_check not in scanned_paths:
             data.append({
                "id": f"rec_{r.id}", 
                "title": r.title,
                "start_time": r.start_time.isoformat(),
                "end_time": r.end_time.isoformat(),
                "channel": r.channel,
                "service_name": r.service_name,
                "service_id": r.service_id,
                "event_id": r.event_id,
                "description": r.description,
                "filepath": r.result_path,
                "status": r.status,
                "topics": [] 
             })
             
    # Collect all unique channel strings to resolve names in one go
    channel_ids = {d.get("channel") for d in data if d.get("channel") and not d.get("service_name")}
    channel_map = {}
    if channel_ids:
        chans = db.query(Channel).filter(Channel.channel_id.in_(channel_ids)).all()
        channel_map = {c.channel_id: c.service_name for c in chans}

    for d in data:
         if not d.get("service_name"):
             ch_id = d.get("channel")
             d["service_name"] = channel_map.get(ch_id, ch_id)
             
    data.sort(key=lambda x: x['start_time'], reverse=True)
    return data

def search_topics(db: Session, query: str):
    norm_q = unicodedata.normalize('NFKC', query).lower()
    results = db.query(Topic).join(Program).filter(func.lower(Topic.title).contains(norm_q)).all()
    
    # Pre-fetch channel names to avoid N+1 queries
    channel_ids = {t.program.channel for t in results if t.program and t.program.channel}
    channel_map = {}
    if channel_ids:
        chans = db.query(Channel).filter(Channel.channel_id.in_(channel_ids)).all()
        channel_map = {c.channel_id: c.service_name for c in chans}

    data = []
    for t in results:
        td = t.to_dict()
        if t.program:
            td['program_id'] = t.program.id
            td['program_title'] = t.program.title
            td['channel'] = t.program.channel
            td['service_name'] = channel_map.get(t.program.channel, t.program.channel)
            td['program_date'] = t.program.start_time.strftime("%Y-%m-%d") if t.program.start_time else ""
            td['filepath'] = t.program.filepath
        data.append(td)
    return data

def get_genres(db: Session):
    results = db.query(EPGProgram.genre_major).distinct().filter(EPGProgram.genre_major != None).all()
    return [r[0] for r in results if r[0]]

def get_epg(db: Session, start: int, end: int, channel_type: Optional[str] = None):
    start_dt = datetime.fromtimestamp(start)
    end_dt = datetime.fromtimestamp(end)
    
    query = db.query(EPGProgram).join(Channel, EPGProgram.channel == Channel.channel_id).filter(
        EPGProgram.end_time > start_dt,
        EPGProgram.start_time < end_dt
    ).with_entities(
        EPGProgram.id, EPGProgram.channel, EPGProgram.title, EPGProgram.description,
        EPGProgram.start_time, EPGProgram.end_time, Channel.sid, EPGProgram.event_id,
        Channel.network_id, EPGProgram.genre_major, EPGProgram.genre_minor, Channel.service_name,
        Channel.tsid
    )

    query = query.filter(Channel.visible == True)
    if channel_type:
        query = query.filter(Channel.type == channel_type)

    programs_raw = query.all()
    
    result = []
    for row in programs_raw:
        s_time = row[4]
        e_time = row[5]
        duration = 0
        if s_time and e_time:
             duration = int((e_time - s_time).total_seconds())

        result.append({
            "id": row[0],
            "channel": row[1],
            "title": row[2] or "",
            "description": row[3] or "",
            "start_time": s_time.isoformat() if s_time else None,
            "end_time": e_time.isoformat() if e_time else None,
            "duration": duration,
            "service_id": row[6] or 0,
            "event_id": row[7],
            "network_id": row[8] or 0,
            "genre_major": row[9],
            "genre_minor": row[10],
            "service_name": row[11],
            "tsid": row[12] or 0
        })

    return result

def get_epg_range(db: Session):
    min_start = db.query(func.min(EPGProgram.start_time)).scalar()
    max_end = db.query(func.max(EPGProgram.end_time)).scalar()
    return {
        "min": min_start.isoformat() if min_start else None,
        "max": max_end.isoformat() if max_end else None
    }
