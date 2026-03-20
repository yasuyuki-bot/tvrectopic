import threading
import logging

try:
    from ..database import SessionLocal, ScheduledRecording
except ImportError:
    from database import SessionLocal, ScheduledRecording

logger = logging.getLogger(__name__)

SCAN_LOCK = threading.Lock()
ACTIVE_SCANS = {
    "GR": 0,
    "BS": 0,
    "CS": 0
}

def get_active_recording_counts():
    db = SessionLocal()
    try:
        active_recs = db.query(ScheduledRecording).filter(ScheduledRecording.status == "recording").all()
        count_gr = 0
        count_bs = 0 
        
        for r in active_recs:
            if "BS" in r.channel or "CS" in r.channel:
                count_bs += 1
            else:
                count_gr += 1
        return count_gr, count_bs
    except Exception as e:
         logger.error(f"DB Error checking counts: {e}")
         return 0, 0 
    finally:
        db.close()

def allocate_tuner(channel_type, settings):
    limit_gr = settings.get("tuner_count_gr", 2)
    limit_bs = settings.get("tuner_count_bs_cs", 2)
    limit_shared = settings.get("tuner_count_shared", 0)
    
    with SCAN_LOCK:
        db_gr, db_bs = get_active_recording_counts()
        
        scan_gr = ACTIVE_SCANS["GR"]
        scan_bs_cs = ACTIVE_SCANS["BS"] + ACTIVE_SCANS["CS"]
        
        total_gr = db_gr + scan_gr
        total_bs = db_bs + scan_bs_cs
        
        can_allocate = False
        
        if channel_type == 'GR':
             if total_gr < limit_gr:
                 can_allocate = True
             else:
                 shared_usage = max(0, total_gr - limit_gr) + max(0, total_bs - limit_bs)
                 if shared_usage < limit_shared:
                     can_allocate = True
        else: 
             if total_bs < limit_bs:
                 can_allocate = True
             else:
                 shared_usage = max(0, total_gr - limit_gr) + max(0, total_bs - limit_bs)
                 if shared_usage < limit_shared:
                     can_allocate = True
        
        if can_allocate:
            ACTIVE_SCANS[channel_type] += 1
            return True
            
        return False

def release_tuner(channel_type):
    with SCAN_LOCK:
        if ACTIVE_SCANS[channel_type] > 0:
            ACTIVE_SCANS[channel_type] -= 1
