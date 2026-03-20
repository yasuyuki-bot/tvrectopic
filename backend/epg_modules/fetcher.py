import time
import os
import tempfile
import json
import logging
import paramiko

try:
    from .tuner import allocate_tuner, release_tuner
    from ..tuner_command import build_epg_command
    from ..utils.text import normalize_text
except (ImportError, ValueError):
    # Standalone script fallback
    import sys
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from tuner import allocate_tuner, release_tuner
    from tuner_command import build_epg_command
    from utils.text import normalize_text

logger = logging.getLogger(__name__)

def fetch_epg_for_channel(channel_info, settings):
    ch_type = channel_info.get('type', 'GR')
    chid = channel_info.get('channel')
    tuning_ch = channel_info.get('TP') or chid
    duration = settings.get("epg_duration", {}).get(ch_type, 60)
    
    allocated = False
    while not allocated:
        if allocate_tuner(ch_type, settings):
            allocated = True
        else:
            time.sleep(2)

    max_retries = 3
    retry_delay = 5

    try:
        for attempt in range(max_retries):
            try:
                logger.info(f"[{channel_info.get('service_name')} (Ch:{tuning_ch})] Tuning... (Attempt {attempt+1}/{max_retries})")
                
                ssh_host = settings.get("ssh_host")
                use_ssh = bool(ssh_host and ssh_host not in ['localhost', '127.0.0.1'])
                
                epgdump_path = settings.get("epgdump_path", "/usr/local/bin/epgdump")

                json_str = ""
                client = None
                
                if use_ssh:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh_user = settings.get("ssh_user")
                    ssh_pass = settings.get("ssh_pass")
                    try:
                        client.connect(ssh_host, username=ssh_user, password=ssh_pass, timeout=10)
                    except Exception as e:
                        logger.info(f"[{channel_info.get('service_name')}] SSH Connect Error: {e}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        else:
                            return None, []
                    
                    remote_ts = f"/tmp/epg_{tuning_ch}_{int(time.time())}.ts" 
                    cmd_list = build_epg_command(settings, tuning_ch, ch_type, duration, remote_ts, service_id=channel_info.get('sid'), network_id=channel_info.get('network_id'))
                    import shlex
                    rec_cmd = shlex.join(cmd_list)
                    cmd = f"{rec_cmd} 2>/dev/null && {epgdump_path} json {remote_ts} -"
                    
                    stdin, stdout, stderr = client.exec_command(cmd)
                    stdout.channel.settimeout(float(duration) + 30.0)
                    json_str = stdout.read().decode('utf-8', errors='ignore')
                else:
                    import subprocess
                    fd, local_ts = tempfile.mkstemp(suffix=f"_epg_{tuning_ch}.ts")
                    os.close(fd)
                    
                    cmd_list = build_epg_command(settings, tuning_ch, ch_type, duration, local_ts, service_id=channel_info.get('sid'), network_id=channel_info.get('network_id'))
                    logger.info(f"Exec (Local rec tuner): {' '.join(cmd_list)}")
                    proc = subprocess.run(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=float(duration) + 30.0)
                    
                    if proc.returncode == 0:
                        cmd_dump = [epgdump_path, "json", local_ts, "-"]
                        logger.info(f"Exec (Local epgdump): {' '.join(cmd_dump)}")
                        proc_dump = subprocess.run(cmd_dump, capture_output=True, text=True, timeout=60.0)
                        json_str = proc_dump.stdout
                    else:
                        logger.error(f"Local tuner failed: {proc.stderr.decode('utf-8', errors='ignore')}")
                    
                    remote_ts = local_ts

                if not json_str.strip():
                     if use_ssh:
                        err_msg = stderr.read().decode('utf-8', errors='ignore').strip()
                        logger.info(f"[{channel_info.get('service_name')}] No JSON output. Stderr: {err_msg}")
                        try: client.exec_command(f"rm {remote_ts}")
                        except: pass
                        client.close()
                     else:
                        logger.info(f"[{channel_info.get('service_name')}] No JSON output from local epgdump.")
                        if os.path.exists(local_ts): os.remove(local_ts)

                     if attempt < max_retries - 1:
                         logger.info(f"[{channel_info.get('service_name')}] Retrying in {retry_delay}s...")
                         time.sleep(retry_delay)
                         continue
                     else:
                         return None, []
                     
                try:
                    epg_data = json.loads(json_str)
                except:
                     if use_ssh:
                        try: client.exec_command(f"rm {remote_ts}")
                        except: pass
                        client.close()
                     else:
                        if os.path.exists(local_ts): os.remove(local_ts)
                     if attempt < max_retries - 1:
                         time.sleep(retry_delay)
                         continue
                     return None, []

                robust_services = []
                if epg_data:
                    seen_sids = set()
                    for service in epg_data:
                        onid = service.get("original_network_id")
                        tsid = service.get("transport_stream_id")
                        sid = service.get("service_id")
                        if not sid or sid in seen_sids: continue
                        seen_sids.add(sid)

                        s_name = normalize_text(service.get("name", "Unknown"))
                        sinfo = service.get("satelliteinfo", {})
                        tp_str = sinfo.get("TP")
                        slot_val = sinfo.get("SLOT")
                        
                        formatted_tp = None
                        if tp_str:
                            formatted_tp = str(tp_str).split('_')[0]

                        robust_services.append({
                            "onid": onid,
                            "tsid": tsid,
                            "sid": sid,
                            "name": s_name,
                            "channel": formatted_tp,
                            "slot": slot_val
                        })
                
                if use_ssh:
                    try: client.exec_command(f"rm {remote_ts}")
                    except: pass
                    client.close()
                else:
                    if os.path.exists(local_ts): os.remove(local_ts)
                return epg_data, robust_services
                
            except Exception as e:
                logger.error(f"Error {tuning_ch} (Attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None, []
        
        return None, []
    finally:
        release_tuner(ch_type)
