from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

try:
    from ..database import AutoReservation, ScheduledRecording
except ImportError:
    from database import AutoReservation, ScheduledRecording

logger = logging.getLogger(__name__)

def get_auto_reservations(db: Session):
    return [r.to_dict() for r in db.query(AutoReservation).all()]

def create_auto_reservation(db: Session, req_data: dict):
    new_rule = AutoReservation(**req_data)
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return new_rule

def update_auto_reservation(db: Session, id: int, req_data: dict):
    rule = db.query(AutoReservation).filter(AutoReservation.id == id).first()
    if not rule:
        return None
    
    for key, value in req_data.items():
        setattr(rule, key, value)
    
    db.commit()
    return rule

def delete_auto_reservation(db: Session, id: int):
    rule = db.query(AutoReservation).filter(AutoReservation.id == id).first()
    if not rule:
        return False
        
    db.query(ScheduledRecording).filter(
        ScheduledRecording.auto_reservation_id == id,
        ScheduledRecording.status.in_(['scheduled', 'skipped'])
    ).delete(synchronize_session=False)

    db.delete(rule)
    db.commit()
    return True

def get_auto_reservation_items(db: Session, id: int):
    recs = db.query(ScheduledRecording).filter(
        ScheduledRecording.auto_reservation_id == id
    ).order_by(ScheduledRecording.start_time).all()
    return [r.to_dict() for r in recs]

def get_all_reservations(db: Session):
    res = db.query(ScheduledRecording).filter(
        ScheduledRecording.status.in_(["scheduled", "recording", "failed"])
    ).order_by(ScheduledRecording.start_time).all()
    return [r.to_dict() for r in res]

def get_reservation(db: Session, id: int):
    return db.query(ScheduledRecording).filter(ScheduledRecording.id == id).first()

def create_scheduled_recording(db: Session, req_data: dict):
    new_rec = ScheduledRecording(**req_data)
    db.add(new_rec)
    db.commit()
    db.refresh(new_rec)
    return new_rec

def delete_scheduled_recording(db: Session, id: int):
    rec = get_reservation(db, id)
    if not rec:
        return False
    
    if rec.auto_reservation_id:
        rec.status = "skipped"
        rec.skip_reason = "manual_delete"
        logger.info(f"Auto-reservation {id} marked as manual_delete by user.")
    else:
        db.delete(rec)
        
    db.commit()
    return True

def find_existing_recording(db: Session, service_id: int, event_id: Optional[int], start_dt: datetime):
    existing = None
    if event_id:
        existing = db.query(ScheduledRecording).filter(
            ScheduledRecording.service_id == service_id,
            ScheduledRecording.event_id == event_id
        ).first()
    
    if not existing:
         existing = db.query(ScheduledRecording).filter(
            ScheduledRecording.service_id == service_id,
            ScheduledRecording.start_time == start_dt
        ).first()
    return existing
