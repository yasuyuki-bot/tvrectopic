import os
import threading
from datetime import datetime
from typing import Optional, List, Union
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging

from ..database import get_db, SessionLocal, AutoReservation, ScheduledRecording, Program
from ..recorder import recorder
from ..auto_reserve_logic import run_all_auto_reservations, search_programs as search_auto_res_programs
from ..crud import recording as crud_recording
from ..crud import program as crud_program

logger = logging.getLogger(__name__)

auto_res_router = APIRouter(prefix="/api/auto_reservations", tags=["auto_reservations"])
record_router = APIRouter(prefix="/api/record", tags=["record"])
reservations_router = APIRouter(prefix="/api/reservations", tags=["reservations"])
recorded_router = APIRouter(prefix="/api/recorded", tags=["recorded"])

# --- Auto Reservation API ---

class AutoReservationCreate(BaseModel):
    name: str
    keyword: Optional[str] = None
    days_of_week: str = "0,1,2,3,4,5,6"
    genres: Optional[str] = None
    types: str = "GR,BS,CS"
    channels: Optional[str] = None
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    recording_folder: Optional[str] = None
    search_target: str = "title"
    active: bool = True
    allow_duplicates: bool = True
    priority: int = 5

class AutoReservationUpdate(AutoReservationCreate):
    pass

@auto_res_router.get("")
def get_auto_reservations(db: Session = Depends(get_db)):
    return crud_recording.get_auto_reservations(db)

@auto_res_router.post("")
def create_auto_reservation(req: AutoReservationCreate, db: Session = Depends(get_db)):
    new_rule = crud_recording.create_auto_reservation(db, req.dict())
    
    from ..auto_reserve_logic import run_all_auto_reservations
    run_all_auto_reservations(db)
    
    return {"rule": new_rule.to_dict()}

@auto_res_router.put("/{id}")
def update_auto_reservation(id: int, req: AutoReservationUpdate, db: Session = Depends(get_db)):
    rule = crud_recording.update_auto_reservation(db, id, req.dict())
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    from ..auto_reserve_logic import run_all_auto_reservations
    run_all_auto_reservations(db)
    return {"rule": rule.to_dict()}

@auto_res_router.delete("/{id}")
def delete_auto_reservation(id: int, db: Session = Depends(get_db)):
    success = crud_recording.delete_auto_reservation(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    from ..auto_reserve_logic import recover_skipped_reservations
    recover_skipped_reservations(db)
    
    return {"status": "Deleted"}

@auto_res_router.post("/preview")
def preview_auto_reservation(req: AutoReservationCreate, db: Session = Depends(get_db)):
    from ..database import AutoReservation
    temp_rule = AutoReservation(
        keyword=req.keyword,
        days_of_week=req.days_of_week,
        genres=req.genres,
        types=req.types,
        channels=req.channels,
        time_range_start=req.time_range_start,
        time_range_end=req.time_range_end,
        search_target=req.search_target
    )
    matches = search_auto_res_programs(db, temp_rule)
    return [p.to_dict() for p in matches]

@auto_res_router.get("/{id}/reservations")
def get_auto_reservation_items(id: int, db: Session = Depends(get_db)):
    return crud_recording.get_auto_reservation_items(db, id)

# --- Recording APIs ---

class ScheduleRequest(BaseModel):
    event_id: Optional[int] = None
    service_id: int
    program_id: Optional[int] = None 
    title: str
    description: str
    start_time: str 
    end_time: str 
    channel: Optional[str] = None
    service_name: str
    network_id: Optional[int] = None
    tsid: Optional[int] = None
    recording_folder: Optional[str] = None
    force: Optional[bool] = False

@record_router.post("/schedule")
def schedule_recording(req: ScheduleRequest, db: Session = Depends(get_db)):
    try:
        start_dt = datetime.fromisoformat(req.start_time)
        end_dt = datetime.fromisoformat(req.end_time)
        
        existing = crud_recording.find_existing_recording(db, req.service_id, req.event_id, start_dt)
        if existing and existing.status != "skipped":
            return {"status": "Already scheduled", "id": existing.id}
            
        conflict_status, msg = recorder.check_tuner_conflict(db, start_dt, end_dt, req.channel, service_id=req.service_id, network_id=req.network_id)
        
        if conflict_status == "full_conflict":
             raise HTTPException(status_code=409, detail=msg)
             
        if conflict_status == "auto_conflict":
            if not req.force:
                return {"status": "Conflict", "conflict_type": "auto", "message": msg}

        # req.dict() doesn't convert string dates to datetime, so we do it manually or pass fields
        req_data = {
            "program_id": req.program_id,
            "event_id": req.event_id,
            "service_id": req.service_id,
            "network_id": req.network_id,
            "title": req.title,
            "description": req.description,
            "start_time": start_dt,
            "end_time": end_dt,
            "channel": req.channel,
            "service_name": req.service_name,
            "status": "scheduled",
            "recording_folder": req.recording_folder
        }
        new_rec = crud_recording.create_scheduled_recording(db, req_data)
        
        def update_res():
            with SessionLocal() as local_db:
                try: run_all_auto_reservations(local_db)
                except Exception as e: logger.info(f"Post-schedule update error: {e}")
        threading.Thread(target=update_res).start()
        
        return {"status": "Scheduled", "id": new_rec.id}
    except HTTPException:
        raise
    except Exception as e:
        logger.info(f"Schedule Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@record_router.post("/start")
def start_immediate_recording(req: ScheduleRequest, db: Session = Depends(get_db)):
    try:
        start_dt = datetime.now() 
        orig_end = datetime.fromisoformat(req.end_time)
        if orig_end < start_dt:
            end_dt = start_dt + datetime.timedelta(minutes=60)
        else:
            end_dt = orig_end
        
        conflict_status, msg = recorder.check_tuner_conflict(db, start_dt, end_dt, req.channel, service_id=req.service_id)
        
        if conflict_status == "full_conflict":
            raise HTTPException(status_code=409, detail=msg)
            
        if conflict_status == "auto_conflict":
            if not req.force:
                return {"status": "Conflict", "conflict_type": "auto", "message": msg}

        duration = int((end_dt - start_dt).total_seconds())
        
        req_data = {
            "program_id": req.program_id,
            "event_id": req.event_id,
            "service_id": req.service_id,
            "network_id": req.network_id,
            "title": req.title,
            "description": req.description,
            "start_time": start_dt,
            "end_time": end_dt,
            "channel": req.channel,
            "service_name": req.service_name,
            "status": "scheduled", 
            "recording_folder": req.recording_folder
        }
        rec = crud_recording.create_scheduled_recording(db, req_data)
        
        def update_res_imm():
            with SessionLocal() as local_db:
                try: run_all_auto_reservations(local_db)
                except Exception as e: logger.info(f"Post-immediate-start update error: {e}")
        threading.Thread(target=update_res_imm).start()
        
        ch_type = "GR"
        if req.service_id:
             info = recorder.get_channel_info(req.service_id, network_id=req.network_id)
             if info and info.get('type'):
                 ch_type = info.get('type')
        
        if req.channel:
            if "BS" in req.channel: ch_type = "BS"
            if "CS" in req.channel: ch_type = "CS"
        
        success, msg = recorder.start_recording(rec.id, ch_type, req.channel, duration, db, recording_folder=req.recording_folder)
        if not success:
             rec.status = "failed"
             db.commit()
             raise HTTPException(status_code=500, detail=msg)
             
        return {"status": "Recording Started", "id": rec.id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@record_router.post("/stop")
def stop_recording_endpoint(program_id: int, db: Session = Depends(get_db)):
    try:
        recorder_stopped = recorder.stop_recording(program_id)
        rec = crud_recording.get_reservation(db, program_id)
        if rec and rec.status == "recording":
             from ..auto_reserve_logic import recover_skipped_reservations
             threading.Thread(target=recover_skipped_reservations, args=(SessionLocal(),)).start()
             return {"status": "Stopped (Forced)" if not recorder_stopped else "Stopped"}
        
        return {"status": "Not Active or Already Stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@reservations_router.get("")
def get_reservations(db: Session = Depends(get_db)):
    return crud_recording.get_all_reservations(db)

@reservations_router.delete("/{id}")
def delete_reservation_endpoint(id: int, db: Session = Depends(get_db)):
    rec = crud_recording.get_reservation(db, id)
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    
    if rec.status == "recording":
        recorder.stop_recording(id)
    
    crud_recording.delete_scheduled_recording(db, id)
    
    def update_res_del():
        with SessionLocal() as local_db:
            try: run_all_auto_reservations(local_db)
            except Exception as e: logger.info(f"Post-delete update error: {e}")
    threading.Thread(target=update_res_del).start()
    
    return {"status": "deleted_or_skipped", "id": id}

@recorded_router.get("")
def get_recorded_list(db: Session = Depends(get_db)):
    return crud_program.get_recorded_list(db)

class BulkDeleteRequest(BaseModel):
    ids: List[Union[str, int]]
    delete_file: bool = True

@recorded_router.post("/bulk_delete")
def bulk_delete_recorded_programs(req: BulkDeleteRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    deleted_files = []
    errors = []
    
    for item in req.ids:
        program_id_str = str(item)
        try:
            # We reuse the logic from delete_recorded_program but for efficiency we might want to refactor it,
            # however for safety and code reuse, we'll implement the core deletion here.
            file_to_delete = None
            if program_id_str.startswith("rec_"):
                rec_id = int(program_id_str.replace("rec_", ""))
                rec_status = crud_recording.get_reservation(db, rec_id)
                if rec_status and rec_status.status == "recording":
                    recorder.stop_recording(rec_id)
                success, file_to_delete, _ = crud_program.delete_scheduled_recording_only(db, rec_id)
            elif program_id_str.isdigit():
                pid = int(program_id_str)
                success, file_to_delete = crud_program.delete_program_and_topics(db, pid)
            
            if file_to_delete and req.delete_file:
                # File deletion
                paths_to_clean = [file_to_delete]
                base, ext = os.path.splitext(file_to_delete)
                paths_to_clean.append(f"{base}.mp4")
                paths_to_clean.append(f"{base}.srt")
                parent_dir = os.path.dirname(file_to_delete)
                filename_no_ext = os.path.splitext(os.path.basename(file_to_delete))[0]
                paths_to_clean.append(os.path.join(parent_dir, "srt", f"{filename_no_ext}.srt"))
                
                for p in paths_to_clean:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception as e:
                            logger.warning(f"Bulk delete failed for {p}: {e}")
                
                deleted_files.append(file_to_delete)

        except Exception as e:
            logger.error(f"Error in bulk delete for {program_id_str}: {e}")
            errors.append({"id": program_id_str, "error": str(e)})

    background_tasks.add_task(run_all_auto_reservations, db)
    
    return {"status": "ok", "deleted_count": len(deleted_files), "errors": errors}


@recorded_router.delete("/{program_id_str}")
def delete_recorded_program(program_id_str: str, background_tasks: BackgroundTasks, delete_file: bool = True, db: Session = Depends(get_db)):
    file_to_delete = None
    
    if program_id_str.startswith("rec_"):
        try:
            rec_id = int(program_id_str.replace("rec_", ""))
            rec_status = crud_recording.get_reservation(db, rec_id)
            if rec_status and rec_status.status == "recording":
                recorder.stop_recording(rec_id)
                
            success, file_to_delete, _ = crud_program.delete_scheduled_recording_only(db, rec_id)
            if not success:
                raise HTTPException(status_code=404, detail="Recording not found")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid ID format")

    elif program_id_str.isdigit():
        pid = int(program_id_str)
        success, file_to_delete = crud_program.delete_program_and_topics(db, pid)
        if not success:
             raise HTTPException(status_code=404, detail="Program not found")
    else:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    if file_to_delete and delete_file:
        import time
        # Small delay if we just stopped recording to allow OS/thread to release file
        if program_id_str.startswith("rec_"):
            time.sleep(0.5)

        max_delete_retries = 3
        for attempt in range(max_delete_retries):
            try:
                paths_to_clean = [file_to_delete]
                base, ext = os.path.splitext(file_to_delete)
                paths_to_clean.append(f"{base}.mp4")
                paths_to_clean.append(f"{base}.srt")
                
                parent_dir = os.path.dirname(file_to_delete)
                filename_no_ext = os.path.splitext(os.path.basename(file_to_delete))[0]
                paths_to_clean.append(os.path.join(parent_dir, "srt", f"{filename_no_ext}.srt"))

                all_success = True
                for p in paths_to_clean:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                            logger.info(f"Deleted file: {p}")
                        except Exception as e:
                            logger.warning(f"Delete attempt {attempt+1} failed for {p}: {e}")
                            all_success = False
                
                if all_success:
                    break
                else:
                    time.sleep(1.0) # Wait before retry
            except Exception as e:
                logger.error(f"Error in delete loop: {e}")
                time.sleep(1.0)

    # Trigger immediate re-evaluation of auto-reservations in background
    # This recovers any "duplicate" skips that are no longer duplicates
    background_tasks.add_task(run_all_auto_reservations, db)
    
    return {"status": "ok", "deleted": file_to_delete}

# --- Resume Position API ---

@record_router.get("/resume/{program_id}")
def get_resume_position(program_id: int, db: Session = Depends(get_db)):
    from ..database import ResumePosition
    pos = db.query(ResumePosition).filter(ResumePosition.program_id == program_id).first()
    if pos:
        return {"position": pos.position}
    return {"position": 0}

@record_router.post("/resume/{program_id}")
def save_resume_position(program_id: int, position: int, db: Session = Depends(get_db)):
    from ..database import ResumePosition
    pos = db.query(ResumePosition).filter(ResumePosition.program_id == program_id).first()
    if pos:
        pos.position = position
    else:
        new_pos = ResumePosition(program_id=program_id, position=position)
        db.add(new_pos)
    
    db.commit()
    return {"status": "ok"}

@record_router.delete("/resume/{program_id}")
def delete_resume_position(program_id: int, db: Session = Depends(get_db)):
    from ..database import ResumePosition
    db.query(ResumePosition).filter(ResumePosition.program_id == program_id).delete()
    db.commit()
    return {"status": "ok"}
