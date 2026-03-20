import os
from typing import List
from sqlalchemy.orm import Session
import logging

try:
    from ..database import Program, ScheduledRecording, Channel, Topic
except ImportError:
    from database import Program, ScheduledRecording, Channel, Topic

logger = logging.getLogger(__name__)

def get_recorded_list(db: Session):
    progs = db.query(Program).order_by(Program.start_time.desc()).all()
    results = [p.to_dict() for p in progs]
    
    path_meta_map = {}
    try:
        recs_meta = db.query(
            ScheduledRecording.result_path, 
            ScheduledRecording.service_id, 
            ScheduledRecording.event_id
        ).filter(
            ScheduledRecording.result_path.isnot(None), 
            ScheduledRecording.status.in_(["completed", "stopped", "recording"])
        ).all()
        
        for rm in recs_meta:
            if rm.result_path:
                path_meta_map[rm.result_path] = (rm.service_id, rm.event_id)
    except Exception as e:
        logger.error(f"Error fetching recording metadata map: {e}")

    final_results = []
    need_commit = False
    for r in results:
        fpath = r.get("filepath")
        if fpath and not os.path.exists(fpath):
            logger.info(f"File missing for Program {r['id']}, cleaning up DB...")
            prog_to_del = db.query(Program).filter(Program.id == r['id']).first()
            if prog_to_del:
                db.delete(prog_to_del)
                need_commit = True
            continue 
            
        if fpath and fpath in path_meta_map:
            sid, eid = path_meta_map[fpath]
            r["service_id"] = sid
            r["event_id"] = eid
        final_results.append(r)
    
    if need_commit:
        db.commit()
    
    results = final_results
    
    def resolve_name(ch_str):
        if not ch_str: return ch_str
        c = db.query(Channel).filter(Channel.channel_id == ch_str).first()
        if c: return c.service_name
        return ch_str
    
    for r in results:
        if not r.get("service_name"):
             r["service_name"] = resolve_name(r.get("channel"))
    
    scanned_paths = {p.filepath for p in progs if p.filepath}
    
    recent_recs = db.query(ScheduledRecording).filter(
        ScheduledRecording.status.in_(["completed", "stopped", "recording"])
    ).order_by(ScheduledRecording.start_time.desc()).limit(50).all()
    
    for r in recent_recs:
        if r.result_path and r.result_path not in scanned_paths:
            if os.path.exists(r.result_path):
                results.append({
                    "id": f"rec_{r.id}",
                    "title": r.title,
                    "start_time": r.start_time.isoformat(),
                    "end_time": r.end_time.isoformat(),
                    "channel": r.channel,
                    "service_name": r.service_name or resolve_name(r.channel),
                    "description": r.description,
                    "filepath": r.result_path,
                    "service_id": r.service_id, 
                    "event_id": r.event_id,
                    "status": r.status,
                    "topics": []
                })
            else:
                logger.info(f"File missing for ScheduledRecording {r.id}, cleaning up DB...")
                db.delete(r)
                db.commit()
            
    results.sort(key=lambda x: x['start_time'], reverse=True)
    return results

def get_program_by_id(db: Session, program_id: int):
    return db.query(Program).filter(Program.id == program_id).first()

def delete_program_and_topics(db: Session, program_id: int):
    prog = get_program_by_id(db, program_id)
    if not prog:
        return False, None
    
    file_to_delete = prog.filepath
    db.query(Topic).filter(Topic.program_id == program_id).delete()
    db.delete(prog)
    
    if file_to_delete:
        linked_rec = db.query(ScheduledRecording).filter(ScheduledRecording.result_path == file_to_delete).first()
        if linked_rec:
            db.delete(linked_rec)
            
    db.commit()
    return True, file_to_delete

def delete_scheduled_recording_only(db: Session, rec_id: int):
    rec = db.query(ScheduledRecording).filter(ScheduledRecording.id == rec_id).first()
    if not rec:
        return False, None, None
        
    status = rec.status
    file_to_delete = rec.result_path
    
    # Also cleanup from Program table if exists
    if file_to_delete:
        prog = db.query(Program).filter(Program.filepath == file_to_delete).first()
        if prog:
            db.query(Topic).filter(Topic.program_id == prog.id).delete()
            db.delete(prog)

    db.delete(rec)
    db.commit()
    return True, file_to_delete, status
