import os
import json
import time
import subprocess
import tempfile
import logging
from datetime import datetime, timedelta

from backend.database import SessionLocal, ScheduledRecording, Channel, EPGProgram
from backend.recorder import recorder
from backend.tuner_command import build_epg_command
from backend.epg_modules.db_saver import save_programs

logger = logging.getLogger(__name__)

def parse_sdt(ts_path):
    """
    Extract raw SDT to get exact Service ID inside the TS, useful for identifying the service network.
    (Optional, similar to update_epg.py if needed, but here we expect we know the service_id)
    """
    return []

def check_and_update_realtime_epg(reservation_id: int):
    """
    Attempts to grab EPG data for the channel of a specific reservation right before it starts.
    If the schedule has changed (e.g., baseball extension), updates the reservation times.
    """
    db = SessionLocal()
    try:
        rec = db.query(ScheduledRecording).filter(ScheduledRecording.id == reservation_id).first()
        if not rec or rec.status != "scheduled":
            return False

        # Tuner Conflict Check: We only want to use the tuner if it's free.
        # Check if doing a 15-second EPG grab now would conflict with anything.
        now = datetime.now()
        check_end_dt = now + timedelta(seconds=20)
        
        # Check standard recording conflicts
        conflict_status, _ = recorder.check_tuner_conflict(db, now, check_end_dt, rec.channel, service_id=rec.service_id, exclude_id=rec.id)
        if conflict_status == "full_conflict":
             logger.info(f"Realtime EPG Skipped (Busy): Tuner busy for reservation {reservation_id} ({rec.title})")
             return True

        # Determine type
        ch_type = "GR"
        if rec.service_id:
             info = recorder.get_channel_info(rec.service_id)
             if info and info.get('type'):
                 ch_type = info.get('type')
        if rec.channel:
            if "BS" in rec.channel: ch_type = "BS"
            if "CS" in rec.channel: ch_type = "CS"

        # Try to reserve tuner
        settings = recorder.load_settings()
        
        # Retry loop for tuner acquisition (Wait for up to 5s instead of 60s since scheduler cycles fast)
        max_wait = 5
        start_wait = time.time()
        identifier = f"epg_check_{reservation_id}"
        tuner_reserved = False
        
        while time.time() - start_wait < max_wait:
            if recorder.reserve_tuner(ch_type, identifier):
                tuner_reserved = True
                break
            time.sleep(1)
            
        if not tuner_reserved:
             logger.info(f"Realtime EPG Skipped (Busy): Could not reserve tuner for reservation {reservation_id}")
             return True

        try:
            logger.info(f"Realtime EPG: Grabbing EPG for channel {rec.channel} (SID: {rec.service_id})")
            
            # Determine execution mode
            ssh_host = settings.get("ssh_host")
            use_ssh = bool(ssh_host and ssh_host not in ['localhost', '127.0.0.1'])
            recdvb_path = settings.get("recdvb_path", "/usr/local/bin/recdvb")
            epgdump_path = settings.get("epgdump_path", "/usr/local/bin/epgdump")
            
            # Record for 15 seconds to ensure we get EIT (Event Information Table)
            duration = 15
            json_str = ""
            import paramiko
            import shlex

            if use_ssh:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh_user = settings.get("ssh_user")
                ssh_pass = settings.get("ssh_pass")
                
                client.connect(ssh_host, username=ssh_user, password=ssh_pass, timeout=10)
                
                # [NEW] Set Keepalive
                transport = client.get_transport()
                if transport:
                    transport.set_keepalive(5)
                
                remote_ts = f"/tmp/realtime_epg_{rec.id}_{int(time.time())}.ts"
                cmd_list = build_epg_command(settings, rec.channel, ch_type, duration, remote_ts, 
                                            service_id=rec.service_id, network_id=rec.network_id)
                rec_cmd = shlex.join(cmd_list)
                
                cmd = f"{rec_cmd} && {epgdump_path} json {remote_ts} -"
                logger.debug(f"Realtime EPG: Exec (SSH): {cmd}")
                
                stdin, stdout, stderr = client.exec_command(cmd)
                stdout.channel.settimeout(float(duration) + 30.0)
                json_str = stdout.read().decode('utf-8', errors='ignore')
                
                # Cleanup remote file
                try: client.exec_command(f"rm {remote_ts}")
                except: pass
                client.close()
            else:
                # Local Execution
                fd, local_ts = tempfile.mkstemp(suffix=f"_realtime_epg_{rec.id}.ts")
                os.close(fd)
                
                cmd_list = build_epg_command(settings, rec.channel, ch_type, duration, local_ts,
                                            service_id=rec.service_id, network_id=rec.network_id)
                logger.debug(f"Realtime EPG: Exec (Local): {' '.join(cmd_list)}")
                proc = subprocess.run(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                
                if proc.returncode == 0:
                    cmd_dump = f"{epgdump_path} json {local_ts} -"
                    proc_dump = subprocess.run(cmd_dump.split(), capture_output=True, text=True)
                    json_str = proc_dump.stdout
                else:
                    logger.error(f"Realtime EPG: Local recording failed: {proc.stderr.decode('utf-8', errors='ignore')}")
                
                if os.path.exists(local_ts): os.remove(local_ts)

            if json_str.strip():
                 epg_data = json.loads(json_str)
                 
                 # Look for our specific service and event
                 service_programs = []
                 for service in epg_data:
                     if str(service.get("service_id")) == str(rec.service_id):
                         programs = service.get("programs", [])
                         service_programs.extend(programs)
                 
                 target_prog = None
                 # Try matching by Event ID
                 if rec.event_id:
                     target_prog = next((p for p in service_programs if str(p.get("event_id")) == str(rec.event_id)), None)
                     
                 # Fallback: Match by time range
                 if not target_prog:
                     for p in service_programs:
                         p_start = p.get('start')
                         p_end = p.get('end')
                         if p_start and p_end:
                             p_start_dt = datetime.fromtimestamp(p_start / 1000.0)
                             if (p_start_dt - timedelta(minutes=60)) <= rec.start_time <= (p_start_dt + timedelta(minutes=60)):
                                 if rec.title and p.get('title') and (rec.title[:10] in p.get('title') or p.get('title')[:10] in rec.title):
                                     target_prog = p
                                     break
                 
                 if target_prog:
                     new_start = datetime.fromtimestamp(target_prog.get("start") / 1000.0)
                     new_end = datetime.fromtimestamp(target_prog.get("end") / 1000.0)
                     new_event_id = target_prog.get("event_id")
                     
                     changed = False
                     if new_start != rec.start_time or new_end != rec.end_time:
                          logger.info(f"Realtime EPG: Update Time for '{rec.title}' -> {new_start} to {new_end}")
                          rec.start_time = new_start
                          rec.end_time = new_end
                          changed = True
                          
                     if str(new_event_id) != str(rec.event_id):
                          logger.info(f"Realtime EPG: Update Event ID for '{rec.title}' -> {new_event_id}")
                          rec.event_id = new_event_id
                          changed = True
                          
                     if changed:
                         db.commit()
                         # Update EPG Program Table as well
                         update_epg_from_data(db, epg_data, rec.channel, rec.service_id, rec.network_id, ch_type)
                     else:
                         logger.info(f"Realtime EPG: No changes detected for '{rec.title}'")
                         # Still update EPG Table to keep it fresh
                         update_epg_from_data(db, epg_data, rec.channel, rec.service_id, rec.network_id, ch_type)
                     return True
                 else:
                     logger.warning(f"Realtime EPG: Target program (Event ID {rec.event_id}) not found in live EIT stream.")
                     return True # Even if not found, we tried and finished.
            else:
                logger.warning(f"Realtime EPG: No EPG data retrieved for {rec.title}")
                return True # Finished attempted check.
                     
        except Exception as e:
            logger.error(f"Realtime EPG check error: {e}")
            return False
        finally:
            recorder.release_tuner(identifier)

    except Exception as e:
        logger.error(f"Realtime EPG DB Error: {e}")
        return False
    finally:
        db.close()
        
    return False

def update_epg_from_data(db, epg_data, channel_id, service_id, network_id, ch_type):
    """
    Helper to update EPGProgram table and handle reservation updates via save_programs.
    """
    try:
        ch_info = {
            'channel': channel_id,
            'sid': service_id,
            'onid': network_id,
            'network_id': network_id,
            'type': ch_type
        }
        # save_programs internally handles matching and updating EPGProgram table.
        # It also updates ScheduledRecording if event_id matches.
        added = save_programs(db, epg_data, ch_info)
        db.commit()
        logger.info(f"Realtime EPG: Updated EPG table. Added/Updated {added} items.")
        return True
    except Exception as e:
        logger.error(f"Error updating EPG table from realtime data: {e}")
        db.rollback()
        return False

def check_and_update_running_recording_epg(reservation_id: int):
    """
    Extracts EPG from a currently recording TS file and updates schedules.
    """
    db = SessionLocal()
    try:
        rec = db.query(ScheduledRecording).filter(ScheduledRecording.id == reservation_id).first()
        if not rec or rec.status != "recording":
            return False

        # Get local path from recorder
        with recorder.lock:
            rec_info = recorder.active_recordings.get(reservation_id)
            if not rec_info:
                return False
            local_path = rec_info.get("local_path")
            ch_type = rec_info.get("type", "GR")
        
        if not local_path or local_path == "RESERVING":
            return False

        settings = recorder.load_settings()
        ssh_host = settings.get("ssh_host")
        use_ssh = bool(ssh_host and ssh_host not in ['localhost', '127.0.0.1'])
        epgdump_path = settings.get("epgdump_path", "/usr/local/bin/epgdump")

        json_str = ""
        import paramiko
        
        logger.info(f"Realtime EPG: Checking running recording '{rec.title}' (Path: {local_path})")

        if use_ssh:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_user = settings.get("ssh_user")
            ssh_pass = settings.get("ssh_pass")
            client.connect(ssh_host, username=ssh_user, password=ssh_pass, timeout=10)
            
            # epgdump can read from a growing file
            cmd = f"{epgdump_path} json {local_path} -"
            stdin, stdout, stderr = client.exec_command(cmd)
            json_str = stdout.read().decode('utf-8', errors='ignore')
            client.close()
        else:
            # Local Execution
            if not os.path.exists(local_path):
                logger.warning(f"Realtime EPG: Recording file {local_path} not found locally.")
                return False
            
            cmd_dump = [epgdump_path, "json", local_path, "-"]
            proc_dump = subprocess.run(cmd_dump, capture_output=True, text=True)
            json_str = proc_dump.stdout

        if json_str.strip():
            epg_data = json.loads(json_str)
            
            # Update EPG table first
            update_epg_from_data(db, epg_data, rec.channel, rec.service_id, rec.network_id, ch_type)
            
            # After save_programs, the reservation might already be updated if event_id matched.
            # We re-fetch to see if changed, or apply manual matching if needed.
            db.refresh(rec)
            
            # Manual matching fallback (similar to check_and_update_realtime_epg) if event_id didn't match
            service_programs = []
            for service in epg_data:
                if str(service.get("service_id")) == str(rec.service_id):
                    service_programs.extend(service.get("programs", []))
            
            target_prog = None
            if rec.event_id:
                target_prog = next((p for p in service_programs if str(p.get("event_id")) == str(rec.event_id)), None)
            
            if not target_prog:
                # Fallback matching...
                for p in service_programs:
                    p_start_dt = datetime.fromtimestamp(p.get('start') / 1000.0)
                    if (p_start_dt - timedelta(minutes=60)) <= rec.start_time <= (p_start_dt + timedelta(minutes=60)):
                        if rec.title and p.get('title') and (rec.title[:10] in p.get('title') or p.get('title')[:10] in rec.title):
                            target_prog = p; break
            
            if target_prog:
                new_end = datetime.fromtimestamp(target_prog.get("end") / 1000.0)
                if new_end != rec.end_time:
                    logger.info(f"Realtime EPG: Extension found for running program '{rec.title}' -> {rec.end_time} to {new_end}")
                    rec.end_time = new_end
                    db.commit()
            
            # [PROACTIVE] Broadcast Update: Update all future programs in the DB from this service
            # This ensures subsequent reservations for this channel are updated BEFORE they start.
            logger.debug(f"Realtime EPG: Proactively updating all programs for {rec.channel} from running TS.")
            update_epg_from_data(db, epg_data, rec.channel, rec.service_id, rec.network_id, ch_type)
            
            return True

    except Exception as e:
        logger.error(f"Error in check_and_update_running_recording_epg: {e}")
    finally:
        db.close()
    return False
