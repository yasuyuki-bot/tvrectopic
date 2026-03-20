
import os
import time
import threading
import subprocess
import paramiko
import json
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
try:
    from .database import ScheduledRecording, Program, SessionLocal, Channel
    from .tuner_command import build_recording_command
    from .utils import get_program_type, parse_time
except (ImportError, ValueError):
    try:
        from database import ScheduledRecording, Program, SessionLocal, Channel
        from tuner_command import build_recording_command
        from utils import get_program_type, parse_time
    except ImportError:
        from backend.database import ScheduledRecording, Program, SessionLocal, Channel
        from backend.tuner_command import build_recording_command
        from backend.utils import get_program_type, parse_time

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

try:
    from .logger_config import get_logger
except (ImportError, ValueError):
    from logger_config import get_logger

logger = get_logger(__name__, "app.log")


class RecordManager:
    def __init__(self):
        # active_recordings: program_id -> { 'client': ssh_client, 'type': 'GR'|'BS'|'CS', 'start_time': ts }
        self.active_recordings = {} 
        self.lock = threading.Lock()
        self.on_preempt_live = None # Callback to preempt live streams
        
        self.HOST = None
        self.USER = None
        self.PASS = None
        
        # Caching layer
        self._settings_cache = None
        self._settings_expiry = 0
        self._channels_cache = {} # (sid, network_id) -> info
        self._channels_expiry = 0
        
        self.load_connection_settings()

    def load_settings(self, force=False):
        now = time.time()
        if not force and self._settings_cache and now < self._settings_expiry:
            return self._settings_cache
            
        try:
            from .settings_manager import load_settings
        except (ImportError, ValueError):
            from settings_manager import load_settings
        
        self._settings_cache = load_settings()
        self._settings_expiry = now + 5 # Cache for 5s
        return self._settings_cache

    def load_connection_settings(self):
        settings = self.load_settings(force=True)
        self.HOST = settings.get("ssh_host")
        self.USER = settings.get("ssh_user")
        self.PASS = settings.get("ssh_pass")

    def _ensure_channels_cache(self):
        now = time.time()
        if self._channels_cache and now < self._channels_expiry:
            return
            
        with SessionLocal() as db:
            chans = db.query(Channel).all()
            new_cache = {}
            for c in chans:
                info = {
                    'channel': c.channel_id,
                    'type': c.type,
                    'sid': c.sid,
                    'network_id': c.network_id,
                    'service_name': c.service_name
                }
                # Index by (sid, network_id) and also just sid as fallback
                new_cache[(c.sid, c.network_id)] = info
                if c.sid not in new_cache:
                    new_cache[c.sid] = info
            self._channels_cache = new_cache
        self._channels_expiry = now + 30 # Cache for 30s

    def get_channel_info(self, service_id, network_id=None):
        self._ensure_channels_cache()
        if network_id is not None:
            return self._channels_cache.get((service_id, network_id))
        return self._channels_cache.get(service_id)

    def reserve_tuner(self, type_str, identifier, can_preempt=False):
        """
        Atomically checks availability and reserves a tuner slot if available.
        Returns True if reserved, False otherwise.
        """
        settings = self.load_settings()
        limit_gr = settings.get("tuner_count_gr")
        limit_bs = settings.get("tuner_count_bs_cs")
        limit_shared = settings.get("tuner_count_shared")
        
        def check_available():
            active_gr = 0
            active_bs = 0
            for pid, rec in self.active_recordings.items():
                if rec['type'] == 'GR': active_gr += 1
                else: active_bs += 1
                    
            if type_str == 'GR':
                if active_gr < limit_gr: return True
                current_shared_usage = max(0, active_gr - limit_gr) + max(0, active_bs - limit_bs)
                if current_shared_usage < limit_shared: return True
            else:
                if active_bs < limit_bs: return True
                current_shared_usage = max(0, active_gr - limit_gr) + max(0, active_bs - limit_bs)
                if current_shared_usage < limit_shared: return True
            return False

        with self.lock:
            if check_available():
                # Reserve immediately
                self.active_recordings[identifier] = {
                    "client": None, "type": type_str, "local_path": "RESERVING", "start_time": time.time()
                }
                return True
            
            if can_preempt and self.on_preempt_live:
                # Look for live streams to kill
                # IMPORTANT: BS and CS share the same pool!
                status_type = type_str if type_str in ['BS', 'CS'] else 'GR'
                
                live_pids = []
                for pid, rec in self.active_recordings.items():
                    if isinstance(pid, str) and pid.startswith("live_"):
                        target_status_type = rec['type'] if rec['type'] in ['BS', 'CS'] else 'GR'
                        if target_status_type == status_type:
                            live_pids.append(pid)
                
                if live_pids:
                    target_pid = live_pids[0]
                    logger.info(f"Preempting live stream {target_pid} for new {type_str} recording {identifier}")
                    
                    self.lock.release()
                    try:
                        # Pass the full PID to the callback
                        self.on_preempt_live(target_pid)
                    except Exception as e:
                        logger.error(f"Failed to preempt live stream {target_pid}: {e}")
                    finally:
                        self.lock.acquire()
                    
                    if check_available():
                        self.active_recordings[identifier] = {
                            "client": None, "type": type_str, "local_path": "RESERVING", "start_time": time.time()
                        }
                        return True

            return False

    def check_tuner_conflict(self, db: Session, start_dt: datetime, end_dt: datetime, channel: str, service_id: int = None, network_id: int = None, tsid: int = None, is_manual: bool = True, exclude_id: int = None):
        """
        Checks if adding a reservation at the given time would exceed tuner limits.
        Uses a sweep-line algorithm for O(N log N) performance.
        Returns: (status, message)
        """
        settings = self.load_settings()
        limit_gr = settings.get("tuner_count_gr")
        limit_bs_cs = settings.get("tuner_count_bs_cs")
        limit_shared = settings.get("tuner_count_shared")

        # Get new reservation type (using cache/common_utils)
        new_type = "GR"
        if service_id:
            info = self.get_channel_info(service_id, network_id=network_id)
            if info:
                new_type = get_program_type(info.get('network_id'), info.get('channel'), info.get('service_name'))
        elif channel:
            new_type = get_program_type(None, channel, None)

        # 連続録画時の数秒の重なりを許容するため、マージンを設定から読み込む
        start_margin = int(settings.get("recording_start_margin"))
        margin_end = int(settings.get("recording_margin_end"))

        # Check the window with start margin for the new reservation
        effective_start = start_dt - timedelta(seconds=start_margin)

        # Fetch only necessary columns to reduce memory/DB load
        query = db.query(ScheduledRecording.id, ScheduledRecording.start_time, ScheduledRecording.end_time, ScheduledRecording.channel, ScheduledRecording.auto_reservation_id).filter(
            ScheduledRecording.start_time < end_dt,
            ScheduledRecording.end_time > effective_start,
            ScheduledRecording.status.in_(["scheduled", "recording"])
        )
        if exclude_id:
            query = query.filter(ScheduledRecording.id != exclude_id)
        overlaps = query.all()

        # Build events for sweep-line
        events = []
        # Current new reservation
        events.append((effective_start, 1, new_type, is_manual))
        events.append((end_dt, -1, new_type, is_manual))
        
        for o in overlaps:
            if o.channel:
                o_type = get_program_type(None, o.channel, None)
            
            is_o_manual = (o.auto_reservation_id is None)
            
            # Clip overlap times and apply margin_end to existing reservations
            # If the existing reservation will be shortened by margin_end, 
            # we should consider it ending earlier for conflict check.
            adj_o_end = o.end_time - timedelta(seconds=margin_end)
            
            # If adjusted end is still before or at our effective start, it's not a real conflict
            if adj_o_end <= effective_start:
                continue

            ev_start = max(effective_start, o.start_time)
            ev_end = min(end_dt, adj_o_end)
            
            if ev_start < ev_end:
                events.append((ev_start, 1, o_type, is_o_manual))
                events.append((ev_end, -1, o_type, is_o_manual))

        # Sort events by time, and then by delta (end before start for same time)
        # However, for conflict we usually want to know the peak.
        events.sort()

        cur_m_gr, cur_a_gr = 0, 0
        cur_m_bs, cur_a_bs = 0, 0
        status = "ok"

        for _, delta, t_type, t_manual in events:
            if t_type == "GR":
                if t_manual: cur_m_gr += delta
                else: cur_a_gr += delta
            else: # BS/CS
                if t_manual: cur_m_bs += delta
                else: cur_a_bs += delta

            # Check validity at this point
            def check_limit(m_gr, a_gr, m_bs, a_bs):
                t_gr = m_gr + a_gr
                t_bs = m_bs + a_bs
                shared_needed = max(0, t_gr - limit_gr) + max(0, t_bs - limit_bs_cs)
                return shared_needed <= limit_shared

            # 1. Manual-only conflict (Always bad)
            if not check_limit(cur_m_gr, 0, cur_m_bs, 0):
                return "full_conflict", "チューナー数が上限に達しています（すべて手動予約で埋まっています）"
            
            # 2. Total conflict (Manual + Auto)
            if not check_limit(cur_m_gr, cur_a_gr, cur_m_bs, cur_a_bs):
                status = "auto_conflict"

        if status == "auto_conflict":
            if is_manual:
                return "auto_conflict", "チューナー数が上限に達していますが、自動予約より手動予約を優先して追加しますか？"
            else:
                return "auto_conflict", "チューナー数が上限に達しています（自動予約による競合）"

        return "ok", ""

    def is_tuner_busy_at(self, db: Session, target_dt: datetime, ch_type: str, exclude_res_id: int = None):
        """Helper to predict if tuners will be full for a specific wave type at target_dt."""
        settings = self.load_settings()
        limit_shared = settings.get("tuner_count_shared")
        
        # 連続録画時のマージンを考慮
        start_margin = int(settings.get("recording_start_margin"))
        margin_end = int(settings.get("recording_margin_end"))
        
        # 判定対象の実質的な開始時間
        effective_target = target_dt - timedelta(seconds=start_margin)
        
        # Find scheduled/recording items that overlap effective_target
        # We consider a recording busy from its start until (end - margin_end)
        recs = db.query(ScheduledRecording).filter(
            ScheduledRecording.status.in_(["scheduled", "recording"]),
            ScheduledRecording.start_time <= effective_target
        ).all()
        
        count_gr = 0
        count_bs_cs = 0
        
        for rec in recs:
            if exclude_res_id and rec.id == exclude_res_id:
                continue
                
            # 実質的な終了時間（マージンを引く）
            adj_end = rec.end_time - timedelta(seconds=margin_end)
            if adj_end <= effective_target:
                continue
            
            rec_type = get_program_type(None, rec.channel, None)
            
            if rec_type == "GR": count_gr += 1
            else: count_bs_cs += 1
        
        # Shared tuner logic
        def is_full(t_gr, t_bs):
            shared_needed = max(0, t_gr - settings.get("tuner_count_gr")) + \
                            max(0, t_bs - settings.get("tuner_count_bs_cs"))
            return shared_needed > limit_shared

        # Check if adding one more of 'ch_type' would exceed limits
        if ch_type == "GR":
            return is_full(count_gr + 1, count_bs_cs)
        else:
            return is_full(count_gr, count_bs_cs + 1)

    def release_tuner(self, identifier):
        """
        Releases a tuner slot reserved via reserve_tuner.
        """
        with self.lock:
            if identifier in self.active_recordings:
                logger.debug(f"Releasing tuner for identifier: {identifier}")
                del self.active_recordings[identifier]

    def start_recording(self, program_id: int, channel_type: str, channel: str, duration: int, db: Session, recording_folder: str = None, network_id: int = None):
        logger.debug(f"start_recording called. ID={program_id}, Type={channel_type}, Ch={channel}, Dur={duration}")
        logger.info(f"Starting recording for {program_id} ({channel_type}).")
        
        # Retry loop for tuner allocation (Wait for up to 120s)
        max_wait = 120
        start_wait = time.time()
        
        while True:
            # Atomic reservation with preemption
            if self.reserve_tuner(channel_type, program_id, can_preempt=True):
                logger.debug(f"Tuner reserved for ID={program_id}")
                break
            
            if time.time() - start_wait > max_wait:
                logger.info(f"No Tuner Available after waiting {max_wait}s. Active: {list(self.active_recordings.keys())}")
                return False, "No Tuner"
            
            if int(time.time() - start_wait) % 10 == 0:
                logger.info(f"Tuners busy for {program_id}, waiting... ({int(time.time() - start_wait)}s). Active: {list(self.active_recordings.keys())}")
            time.sleep(1)
        
        settings = self.load_settings()
        save_dir = recording_folder if recording_folder else settings["recording_folder"]

        if not os.path.exists(save_dir):
             try: os.makedirs(save_dir, exist_ok=True)
             except: return False, "Invalid Dir"

        # Resolve DB Info
        local_db = SessionLocal()
        prog = local_db.query(ScheduledRecording).filter(ScheduledRecording.id == program_id).first()
        title = prog.title if prog else "Unknown"
        service_id = prog.service_id if prog else 0
        # Use network_id from prog if available, otherwise use passed arguments
        effective_network_id = prog.network_id if prog and prog.network_id is not None else network_id


        # Adjust duration if start time was delayed
        if prog and prog.end_time:
            current_now = datetime.now()
            remaining = (prog.end_time - current_now).total_seconds()
            
            if remaining < duration:
                logger.info(f"Adjusting duration for {program_id} due to delay: {duration}s -> {int(remaining)}s")
                duration = max(5, int(remaining)) # Ensure at least 5s

        
        # Command building is deferred to record_thread via tuner_command

        if prog: 
            prog.status = "recording"
            local_db.commit()

        # Filename
        now = datetime.now()
        now = datetime.now()
        if prog:
            if prog.start_time:
                logger.info(f"DEBUG: Using DB StartTime for filename: {prog.start_time} (ID: {program_id})")
                start_for_fn = prog.start_time
            else:
                logger.info(f"DEBUG: DB Prog found but start_time is None. Using NOW: {now} (ID: {program_id})")
                start_for_fn = now
        else:
            logger.info(f"DEBUG: DB Prog NOT FOUND. Using NOW: {now} (ID: {program_id})")
            start_for_fn = now
        
        def sanitize_filename(name):
            if not name: return "Unknown"
            # Replace characters that are generally problematic on Windows/Linux filesystems
            # \ / : * ? " < > | and null byte
            invalid_chars = r'\/:*?"<>|'
            safe_name = "".join(c for c in name if c not in invalid_chars and ord(c) > 31)
            return safe_name.strip()

        safe_title = sanitize_filename(title)
        
        # Get Service Name and Sanitize
        s_name = prog.service_name if prog and prog.service_name else "UnknownService"
        safe_s_name = sanitize_filename(s_name)
        
        # Determine End Time Variables
        end_dt = prog.end_time if prog and prog.end_time else now
        end_date_str = end_dt.strftime("%Y%m%d")
        end_time_str = end_dt.strftime("%H%M")

        filename = settings["filename_format"].format(
            Title=safe_title, Date=start_for_fn.strftime("%Y%m%d"), Time=start_for_fn.strftime("%H%M"), 
            EndDate=end_date_str, EndTime=end_time_str,
            Channel=channel, SID=service_id, ServiceName=safe_s_name
        )
        if not filename.endswith(".ts"): filename += ".ts"
        local_path = os.path.join(save_dir, filename)

        # Close DB session AFTER gathering all needed data for filename
        local_db.close()

        # Registration is now done in reserve_tuner
        # Update placeholder with actual file path
        with self.lock:
            if program_id in self.active_recordings:
                self.active_recordings[program_id]["local_path"] = local_path
            else:
                # This should not happen if reserve_tuner worked
                logger.warning(f"Warning: program_id {program_id} missing from active_recordings after reservation")
                self.active_recordings[program_id] = {
                    "client": None, "type": channel_type, "local_path": local_path, "start_time": time.time()
                }

        def record_thread(tgt_path):
            nonlocal end_dt
            logger.debug(f"record_thread started for {program_id}. Path={tgt_path}")
            # Determine execution mode
            settings = self.load_settings()
            use_ssh = True
            host = getattr(self, 'HOST', None)
            if not host or host in ['localhost', '127.0.0.1']:
                use_ssh = False

            max_retries = 3
            retry_conf = 0
            
            # Start Loop
            total_written_bytes = 0
            while retry_conf < max_retries:
                # [FIX] Re-fetch end_time from DB to handle dynamic extensions
                s_db_check = SessionLocal()
                p_check = s_db_check.query(ScheduledRecording).filter(ScheduledRecording.id == program_id).first()
                if p_check and p_check.end_time:
                    if p_check.end_time != end_dt:
                        logger.info(f"Recording Extension Detected for {program_id}: {end_dt} -> {p_check.end_time}")
                        end_dt = p_check.end_time
                s_db_check.close()

                now_dt = datetime.now()
                remaining = (end_dt - now_dt).total_seconds()
                
                if remaining < 3: # Margin
                    logger.debug(f"Finishing recording for {program_id} as scheduled end is reached.")
                    break

                retry_conf += 1
                current_attempt_duration = int(remaining)
                logger.debug(f"Recording Attempt {retry_conf}/{max_retries} for {program_id} (Remaining: {current_attempt_duration}s)")
                
                attempt_written_bytes = 0  
                client = None
                proc = None
                
                try:
                    if use_ssh:
                        client = paramiko.SSHClient()
                        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        client.connect(self.HOST, username=self.USER, password=self.PASS, timeout=10)
                        
                        # [NEW] Set Keepalive
                        transport = client.get_transport()
                        if transport:
                            transport.set_keepalive(5)
                            
                        with self.lock:
                            if program_id in self.active_recordings:
                                self.active_recordings[program_id]["client"] = client
                            else:
                                client.close()
                                return
                    else:
                        # Local Execution
                        pass # Handled below
    
                    # Command building is deferred to record_thread via tuner_command
                    cmd_list = build_recording_command(settings, service_id, channel_type, current_attempt_duration, "-", channel_num=channel, network_id=effective_network_id)
                    
                    if use_ssh:
                        import shlex
                        full_cmd_ssh = shlex.join(cmd_list) + " 2>/dev/null"
                        logger.info(f"Exec (SSH) Attempt {retry_conf} for Program {program_id}: {full_cmd_ssh}")
                        _, stdout, _ = client.exec_command(full_cmd_ssh, bufsize=1024*1024)
                    else:
                        full_cmd_local = ' '.join(cmd_list)
                        logger.info(f"Exec (Local) Attempt {retry_conf} for Program {program_id}: {full_cmd_local}")
                        proc = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                        with self.lock:
                            if program_id in self.active_recordings:
                                self.active_recordings[program_id]["client"] = proc # Store proc object
                            else:
                                proc.terminate()
                                return
    
                    s_db = SessionLocal()
                    p = s_db.query(ScheduledRecording).filter(ScheduledRecording.id == program_id).first()
                    if p: 
                        p.result_path = tgt_path
                        s_db.commit()
                    s_db.close()
    
                    # [MOD] Open in Append mode ("ab")
                    with open(tgt_path, "ab") as f:
                        start_ts = time.time()
                        while True:
                            if program_id not in self.active_recordings: break
                            
                            data = None
                            if use_ssh:
                                try:
                                    data = stdout.read(65536)
                                except:
                                    break
                            else:
                                data = proc.stdout.read(65536)
                                
                            if not data: 
                                if use_ssh:
                                    # Connection might be closed
                                    if attempt_written_bytes == 0 and (time.time() - start_ts) > 20:
                                        logger.info(f"Recording Timeout (No data) for {program_id}")
                                        break
                                    break
                                else:
                                    # Subprocess ended
                                    if proc.poll() is not None:
                                        break
                                    break
                            
                            f.write(data)
                            attempt_written_bytes += len(data)
                            total_written_bytes += len(data)
    
                    with self.lock:
                        is_active = (program_id in self.active_recordings)
                    
                    if is_active:
                         # Still active but loop exited (EOF/Error) -> Retry
                         logger.info(f"Recording Interrupted ({attempt_written_bytes} bytes in this attempt) for {program_id}. Retrying...")
                         # Loop will continue if retries left
                    else:
                         # Manual stop or success
                         break
    
                except Exception as e:
                    logger.info(f"Err in record_thread {program_id} (Attempt {retry_conf}): {e}")
                finally:
                    # Cleanup Current Attempt
                    if client:
                        try: client.close()
                        except: pass
                    if proc:
                        try: 
                            proc.terminate()
                            proc.wait(timeout=1)
                        except: pass
                
                # Check cancellation
                with self.lock:
                    if program_id not in self.active_recordings:
                        break

                # [MOD] Retry if still active
                if retry_conf < max_retries:
                    retry_interval = int(settings.get("recording_retry_interval"))
                    logger.info(f"Waiting {retry_interval}s before retry {retry_conf+1}...")
                    time.sleep(retry_interval)
                    continue
                else:
                    break
            
            # Final Cleanup Logic (Outside Loop)
            with self.lock:
                if program_id in self.active_recordings:
                    del self.active_recordings[program_id]
                
                try:
                    s_db = SessionLocal()
                    p = s_db.query(ScheduledRecording).filter(ScheduledRecording.id == program_id).first()
                    if p and p.status == "recording": 
                        # written_bytes is from the last iteration
                        if total_written_bytes == 0: p.status = "failed"
                        else: p.status = "completed"
                        s_db.commit()
                    s_db.close()
                except Exception as e:
                    logger.info(f"Final status update error: {e}")

        t = threading.Thread(target=record_thread, args=(local_path,))
        t.start()
        return True, "Started"

    def stop_recording(self, program_id: int):
        with self.lock:
            if program_id in self.active_recordings:
                rec = self.active_recordings[program_id]
                # Update DB status to completed since user stopped it manually
                try:
                    s_db = SessionLocal()
                    p = s_db.query(ScheduledRecording).filter(ScheduledRecording.id == program_id).first()
                    if p:
                        # Only update if it is currently recording or scheduled
                        if p.status == "recording":
                            p.status = "completed"
                        elif p.status == "scheduled":
                            p.status = "cancelled" # If stopped before starting?
                        s_db.commit()
                    s_db.close()
                except: pass

                try:
                    logger.info(f"Stopping recording {program_id}...")
                    client = rec['client']
                    if hasattr(client, 'terminate'): # Subprocess
                        client.terminate()
                        try: client.wait(timeout=1)
                        except: client.kill()
                    else: # SSH Client
                        client.close()
                except Exception as e:
                    logger.error(f"Error stopping recording: {e}")
                
                del self.active_recordings[program_id]
                return True
        return False

recorder = RecordManager()
