import logging
logger = logging.getLogger(__name__)
import paramiko
import os
import json
import sys
import time


def fetch_epg(channel, duration=15):
    # Load settings from adjacent settings.json
    settings = {}
    settings_file = os.path.join(os.path.dirname(__file__), "settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except: pass

    ssh_host = settings.get("ssh_host")
    use_ssh = bool(ssh_host and ssh_host not in ['localhost', '127.0.0.1'])
    
    recdvb_path = settings.get("recdvb_path", "/usr/local/bin/recdvb")
    epgdump_path = settings.get("epgdump_path", "/usr/local/bin/epgdump")

    client = None
    try:
        if use_ssh:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_user = settings.get("ssh_user")
            ssh_pass = settings.get("ssh_pass")
            client.connect(ssh_host, username=ssh_user, password=ssh_pass, timeout=10)
            
            cmd = f"{recdvb_path} --b25 --strip {channel} {duration} - | {epgdump_path} json - -"
            logger.info(f"Executing remote command: {cmd}")
            stdin, stdout, stderr = client.exec_command(cmd)
            
            json_str = stdout.read().decode('utf-8', errors='ignore')
            err_str = stderr.read().decode('utf-8', errors='ignore')
        else:
            # Local Execution
            import subprocess
            cmd = f"{recdvb_path} --b25 --strip {channel} {duration} -"
            cmd_dump = f"{epgdump_path} json - -"
            logger.info(f"Executing local command: {cmd} | {cmd_dump}")
            
            p1 = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p2 = subprocess.Popen(cmd_dump.split(), stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p1.stdout.close()
            
            stdout_data, stderr_data = p2.communicate()
            json_str = stdout_data.decode('utf-8', errors='ignore')
            err_str = stderr_data.decode('utf-8', errors='ignore')
        
        if err_str:
            logger.info(f"STDERR: {err_str}")
        
        if not json_str.strip():
            logger.info("No output from epgdump.")
            return None
            
        try:
            data = json.loads(json_str)
            return data
        except json.JSONDecodeError as e:
            logger.info(f"JSON Decode Error: {e}")
            logger.info(f"Raw Output (head): {json_str[:500]}")
            return None

    except Exception as e:
        logger.info(f"Execution Error: {e}")
        return None
    finally:
        if client:
            client.close()

if __name__ == "__main__":
    target_ch = sys.argv[1] if len(sys.argv) > 1 else "27"
    logger.info(f"Starting EPG fetch for Channel {target_ch}...")
    
    start_time = time.time()
    epg_data = fetch_epg(target_ch)
    end_time = time.time()
    
    logger.info(f"Finished in {end_time - start_time:.2f} seconds.")
    
    if epg_data:
        # Check structure (epgdump json usually creates a list of programs or channels)
        # Assuming structure details, but just dumping for now.
        prog_count = 0
        if isinstance(epg_data, list):
            prog_count = len(epg_data) # epgdump often returns array of channels, or programs
            # epgdump json format: usually [ { "name": "...", "programs": [...] } ]
            if len(epg_data) > 0 and 'programs' in epg_data[0]:
                 prog_count = len(epg_data[0]['programs'])
            
        logger.info(f"Fetched Data Structure Type: {type(epg_data)}")
        logger.info(f"Estimated Program Count: {prog_count}")
        
        out_file = f"epg_{target_ch}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(epg_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved EPG data to {out_file}")
    else:
        logger.error("Failed to fetch EPG data.")
