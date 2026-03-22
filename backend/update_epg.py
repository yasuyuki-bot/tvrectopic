import sys
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from .database import SessionLocal
    from .auto_reserve_logic import run_all_auto_reservations, recover_skipped_reservations
    from .epg_modules.fetcher import fetch_epg_for_channel
    from .epg_modules.db_saver import load_channels, update_channel_map, save_programs, cleanup_old_epg
    from .logger_config import get_logger
except (ImportError, ValueError):
    # Standalone script fallback: ensure backend root is in path
    import sys
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from database import SessionLocal
    from auto_reserve_logic import run_all_auto_reservations, recover_skipped_reservations
    from epg_modules.fetcher import fetch_epg_for_channel
    from epg_modules.db_saver import load_channels, update_channel_map, save_programs, cleanup_old_epg
    from logger_config import get_logger

# Configure the root logger to output to stdout/stderr.
# The parent process (epg.py or scheduler) will handle capturing this output to a file.
logger = get_logger("backend", configure_root=True)
# Also get a specific logger for this module for clear identification in logs
module_logger = logger.getChild("update_epg")

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
STATUS_FILE = os.path.join(os.path.dirname(__file__), "epg_status.json")

def load_settings():
    try:
        from .settings_manager import load_settings as ls
    except (ImportError, ValueError):
        from settings_manager import load_settings as ls
    return ls()

SETTINGS = load_settings()

BS_PHYSICAL = ["BS01_0", "BS03_0", "BS05_0", "BS09_0", "BS13_0", "BS15_0", "BS19_0", "BS21_0", "BS23_0"]
CS_PHYSICAL = ["CS2", "CS4", "CS6", "CS8", "CS10", "CS12", "CS14", "CS16", "CS18", "CS20", "CS22", "CS24"]

def write_status(running, progress, current_ch, completed_cnt, total_cnt):
    try:
        tmp = STATUS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "running": running,
                "progress": progress,
                "current_channel": current_ch,
                "completed": completed_cnt,
                "total": total_cnt
            }, f, ensure_ascii=False)
        os.replace(tmp, STATUS_FILE)
    except: pass

def channel_task(ch_info):
    logger.info(f"Task Started: {ch_info.get('service_name')}")
    data, robust_services = fetch_epg_for_channel(ch_info, SETTINGS)
    if data:
        if ch_info.get('type') != 'GR': 
            update_channel_map(ch_info['channel'], robust_services, ch_info['type'])
        
        db = SessionLocal()
        try:
            added = save_programs(db, data, ch_info)
            db.commit()
            logger.info(f"Task Completed: {ch_info.get('service_name')} - Added {added}")
            return ch_info.get('service_name'), added
        except Exception as e:
            logger.error(f"Error saving {ch_info.get('service_name')}: {e}")
            return ch_info.get('service_name'), 0
        finally: db.close()
    return ch_info.get('service_name'), 0

def main(target_type=None):
    channels = load_channels()
    scan_tasks = {}
    
    if not target_type or target_type == "GR":
        for c in channels:
            if c.get('type') == 'GR':
                if c.get('visible') is False: continue
                tp_val = c.get('TP')
                if tp_val and tp_val not in scan_tasks:
                    scan_tasks[tp_val] = c

    if not target_type or target_type == "BS":
        bs_target = "BS15"
        rep = next((c for c in channels if c.get('TP') == bs_target or c.get('channel') == bs_target), None)
        if not rep:
             rep = {"type": "BS", "TP": bs_target, "channel": bs_target, "service_name": "NHK BS (Global Scan)", "sid": 101}
        scan_tasks[bs_target] = rep

    if not target_type or target_type == "CS":
         for tp in CS_PHYSICAL:
            rep = next((c for c in channels if c.get('type') == 'CS' and c.get('TP') == tp), None)
            if not rep:
                 rep = {"type": "CS", "channel": tp, "TP": tp, "service_name": f"{tp} (Scan)", "sid": 0}
            scan_tasks[tp] = rep

    task_list = list(scan_tasks.values())
    
    gr_tasks = [t for t in task_list if t.get('type') == 'GR']
    bs_tasks = [t for t in task_list if t.get('type') == 'BS']
    cs_tasks = [t for t in task_list if t.get('type') == 'CS']
    
    interleaved_list = []
    max_len = max(len(gr_tasks), len(bs_tasks), len(cs_tasks))
    for i in range(max_len):
        if i < len(gr_tasks): interleaved_list.append(gr_tasks[i])
        if i < len(bs_tasks): interleaved_list.append(bs_tasks[i])
        if i < len(cs_tasks): interleaved_list.append(cs_tasks[i])
    
    task_list = interleaved_list
    
    logger.info(f"Starting EPG Update ({len(task_list)} channels)...")
    
    write_status(True, 0, "開始中...", 0, len(task_list))

    total_tasks = len(task_list)
    completed_count = 0
    
    limit_gr = SETTINGS.get("tuner_count_gr", 2)
    limit_bs = SETTINGS.get("tuner_count_bs_cs", 2)
    limit_shared = SETTINGS.get("tuner_count_shared", 0)
    max_threads = 32
    logger.info(f"Using {max_threads} concurrent threads for task management (Tuner limits: GR:{limit_gr} BS/CS:{limit_bs} Shared:{limit_shared})")

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        future_to_ch = {executor.submit(channel_task, ch): ch for ch in task_list}
        for future in as_completed(future_to_ch):
            ch_data = future_to_ch[future]
            completed_count += 1
            pct = int((completed_count / total_tasks) * 100)
            
            try:
                res_name, added_cnt = future.result()
                write_status(True, pct, f"{res_name} (Added: {added_cnt})", completed_count, total_tasks)
            except Exception as e:
                write_status(True, pct, f"Error: {ch_data.get('service_name')}", completed_count, total_tasks)

    cleanup_old_epg(SETTINGS)

    db = SessionLocal()
    try:
        logger.info("Triggering auto reservations after EPG update...")
        count = run_all_auto_reservations(db)
        logger.info(f"Auto Reservations Completed. New: {count}")

        logger.info("Running recovery pass for skipped reservations...")
        rec_count = recover_skipped_reservations(db)
        if rec_count > 0:
             logger.info(f"Recovered {rec_count} skipped reservations.")
    except Exception as e:
        logger.error(f"Error executing auto reservations: {e}")
    finally:
        db.close()

    write_status(False, 100, "完了", total_tasks, total_tasks)

if __name__ == "__main__":
    target = None
    if len(sys.argv) > 1: target = sys.argv[1]
    try: main(target)
    except KeyboardInterrupt: pass
    except Exception as e: logger.error(e)
    
    try:
        tmp = STATUS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "running": False,
                "progress": 0,
                "current_channel": "停止",
                "completed": 0,
                "total": 0
            }, f, ensure_ascii=False)
        os.replace(tmp, STATUS_FILE)
    except: pass
    
    try:
        sys.exit(0)
    except: pass
