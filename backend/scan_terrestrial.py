try:
    from .logger_config import get_logger
except (ImportError, ValueError):
    # Standalone script fallback
    import sys
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from logger_config import get_logger

logger = get_logger(__name__, "scan.log")
import paramiko
import subprocess
import json
import time
import shlex
import os
import tempfile
import concurrent.futures
import threading
import unicodedata
from ariblib.aribstr import AribString
try:
    from .utils import normalize_text
except (ImportError, ValueError):
    from utils import normalize_text

# Configuration
STATUS_FILE = os.path.join(os.path.dirname(__file__), "scan_status.json")

# Physical Channels to Scan (UHF 13-62)
TARGET_CHANNELS = [str(i) for i in range(13, 63)]
# Adapters are determined dynamically from settings
# Actually we don't know how many adapters. `recorder.py` mentions exclude_tuners=[] but we don't know limit.
# User asked "recdvb should be parallel".
# Let's try 4 workers.

# Shared state for status updates
scan_state = {
    "scanning": True,
    "progress": 0,
    "current_channel": "",
    "results": [],
    "total": len(TARGET_CHANNELS),
    "processed": 0
}
state_lock = threading.Lock()


def update_status_file():
    with state_lock:
        s = scan_state
        # Calculate progress
        pct = 0
        if s["total"] > 0:
            pct = int((s["processed"] / s["total"]) * 100)
            

        out = {
            "scanning": s["scanning"],
            "progress": pct,
            "current_channel": s["current_channel"],
            "results": sorted(s["results"], key=lambda x: int(x['channel']))
        }
        
        # Atomic write INSIDE the lock to avoid race conditions between workers
        tmp_file = STATUS_FILE + ".tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False)
            
            # On Windows, os.replace might fail if the file is being read by the API
            # Retry a few times
            max_retries = 5
            for i in range(max_retries):
                try:
                    # In Python 3.3+, os.replace is atomic and works on Windows
                    # but can still fail with WinError 32 if another handle is open
                    if os.path.exists(STATUS_FILE):
                        os.remove(STATUS_FILE)
                    os.rename(tmp_file, STATUS_FILE)
                    break
                except Exception as ex:
                    if i == max_retries - 1:
                        raise ex
                    time.sleep(0.1)
        except Exception as e:
            logger.info(f"Status Write Error: {e}")
            try: 
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
            except: pass


def scan_worker(channel, adapter):
    with state_lock:
        scan_state["current_channel"] = channel
    
    # Adapter index is only used for unique filename, not passed to recdvb as per user request
    logger.info(f"[{channel}] Scanning (Worker {adapter})...")
    
    settings = load_settings()
    host = settings.get("ssh_host")
    user = settings.get("ssh_user")
    password = settings.get("ssh_pass")
    
    use_ssh = True
    if not host or host in ['localhost', '127.0.0.1']:
        use_ssh = False

    try:
        client = None
        if use_ssh:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, username=user, password=password, timeout=10)
        
        # Unique TS for thread safety
        # If local, use tempfile directly
        if use_ssh:
             remote_ts = f"/tmp/scan_gr_{channel}_{adapter}.ts"
        else:
             fd, local_ts_path = tempfile.mkstemp(suffix=f"_scan_{channel}_{adapter}.ts")
             os.close(fd)
             remote_ts = local_ts_path # concept of 'remote' is same as target path

        # recdvb with 5s. Removed --dev as requested.
        recdvb_path = settings.get("recdvb_path", "/usr/local/bin/recdvb")
        cmd = [recdvb_path]
        if settings.get("recdvb_voltage", False):
            cmd.extend(["--lnb", "15"])
        cmd.extend(["--b25", "--strip", channel, "5", remote_ts])
        
        if use_ssh:
            ssh_cmd = shlex.join(cmd)
            stdin, stdout, stderr = client.exec_command(ssh_cmd)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                err = stderr.read().decode('utf-8', errors='ignore')
                logger.info(f"[{channel}] recdvb failed (Status {exit_status}): {err}")
        else:
             # Local Execution
             logger.info(f"Exec (Local): {' '.join(cmd)}")
             proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
             if proc.returncode != 0:
                 logger.info(f"[{channel}] recdvb failed (Status {proc.returncode}): {proc.stderr.decode('utf-8', errors='ignore')}")

        found = []
        # Use epgdump json to extract channel info
        epgdump_path = settings.get("epgdump_path", "epgdump")
        json_output = ""
        
        if use_ssh:
            # Re-read remote_ts using epgdump
            dump_cmd = f"{epgdump_path} json {remote_ts} -"
            logger.debug(f"Exec (SSH Dump): {dump_cmd}")
            stdin_d, stdout_d, stderr_d = client.exec_command(dump_cmd)
            json_output = stdout_d.read().decode('utf-8', errors='ignore')
            # cleanup remote ts
            client.exec_command(f"rm {remote_ts}")
            client.close()
        else:
             # Local Execution
            if os.path.exists(local_ts_path):
                dump_cmd = [epgdump_path, "json", local_ts_path, "-"]
                proc_dump = subprocess.run(dump_cmd, capture_output=True, text=True)
                json_output = proc_dump.stdout
                os.remove(local_ts_path)

        if json_output.strip():
            try:
                epg_data = json.loads(json_output)
                for service in epg_data:
                    # Extract fields
                    onid = service.get("original_network_id")
                    tsid = service.get("transport_stream_id")
                    sid = service.get("service_id")
                    s_name = normalize_text(service.get("name", "Unknown"))
                    
                    sinfo = service.get("satelliteinfo", {})
                    tp_val = sinfo.get("TP")
                    slot_val = sinfo.get("SLOT")
                    
                    # Manual Override for channel_id format
                    c_id = f"GR{channel}_{sid}"
                    
                    found.append({
                        "channel_id": c_id,
                        "onid": onid,
                        "tsid": tsid,
                        "sid": sid,
                        "service_name": s_name,
                        "TP": tp_val if tp_val else channel,
                        "slot": str(slot_val) if slot_val is not None else "",
                        "type": c_id[:2] if c_id else "GR",
                        "channel": channel # Physical channel for sorting
                    })
            except Exception as e:
                logger.info(f"[{channel}] JSON Parse Error: {e}")
            
        with state_lock:
            if found:
                scan_state["results"].extend(found)
            scan_state["processed"] += 1
            
        update_status_file()
        logger.info(f"[{channel}] Found {len(found)}")
        return found
        
    except Exception as e:
        logger.info(f"[{channel}] Error: {e}")
        with state_lock:
            scan_state["processed"] += 1
        update_status_file()
        return []

# ...
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except: pass
    return {}

def main():
    logger.info("Starting Terrestrial Scan (Parallel)...")
    
    settings = load_settings()
    # Default to 2 if not set, as per user's comment "Ground wave is max 2"
    tuner_count = int(settings.get("tuner_count_gr", 2))
    
    # Cap at reasonable limit if setting is weird, but user said max 2.
    if tuner_count < 1: tuner_count = 1
    
    logger.info(f"Using {tuner_count} tuners for scanning.")

    # Database operations
    try:
        from .database import SessionLocal, Channel
    except (ImportError, ValueError):
        from database import SessionLocal, Channel
    db = SessionLocal()
    try:
        # Load existing channels from DB
        existing = db.query(Channel).all()
        
        # Identify non-GR channels to keep (as models)
        non_gr = [c for c in existing if c.type != 'GR']
        
        # Parallel Execution
        workers = tuner_count
        
        future_to_ch = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for i, ch in enumerate(TARGET_CHANNELS):
                # Adapters: 0 to N-1
                adp = i % tuner_count 
                future = executor.submit(scan_worker, ch, adp)
                future_to_ch[future] = ch
                
            for future in concurrent.futures.as_completed(future_to_ch):
                future.result()
                
        # Get results
        with state_lock:
            new_gr_results = scan_state["results"]
            
        new_gr_results.sort(key=lambda x: int(x['channel']))
        
        # Remove ALL existing GR channels from DB before inserting new ones
        db.query(Channel).filter(Channel.type == 'GR').delete()
        
        # Add new GR channels
        for res in new_gr_results:
            new_c = Channel(
                type=res['type'],
                channel_id=res['channel_id'],
                tsid=res['tsid'],
                network_id=res['onid'],
                sid=res['sid'],
                service_name=res['service_name'],
                TP=res['TP'],
                slot=res['slot'],
                visible=True
            )
            db.add(new_c)
            
        db.commit()
    except Exception as e:
        logger.info(f"Database Error: {e}")
        db.rollback()
    finally:
        db.close()

    with state_lock:
        scan_state["scanning"] = False
        scan_state["progress"] = 100
        
    update_status_file()
    logger.info("Scan Completed.")

if __name__ == "__main__":
    main()
