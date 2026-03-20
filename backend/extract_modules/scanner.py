import logging
logger = logging.getLogger(__name__)
import os
import glob
import re
import datetime
import ariblib
from ariblib.descriptors import ShortEventDescriptor
from ariblib.sections import EventInformationSection

try:
    from ..database import SessionLocal, Program, Topic
    from .subtitle import extract_subtitles_srt, get_transcript_text
    from .processor import process_topic_batch
    from .video import is_file_closed
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from database import SessionLocal, Program, Topic
    from extract_modules.subtitle import extract_subtitles_srt, get_transcript_text
    from extract_modules.processor import process_topic_batch
    from extract_modules.video import is_file_closed

# Target Directory (Default for tests)
TS_DIR = r"C:\\Users\\rujas\\Videos\\topictest"

def parse_filename(filepath):
    basename = os.path.basename(filepath)
    match = re.search(r"_(\d{12})-(\d{12})", os.path.splitext(basename)[0])
    if match:
        start_str = match.group(1)
        end_str = match.group(2)
        prefix = basename[:match.start()]
        
        if "_" in prefix:
            parts = prefix.split("_", 1)
            station = parts[0]
            program = parts[1]
        else:
            station = "Unknown"
            program = prefix
            
        return {
            'station': station,
            'program': program,
            'start': datetime.datetime.strptime(start_str, "%Y%m%d%H%M"),
            'end': datetime.datetime.strptime(end_str, "%Y%m%d%H%M")
        }
    
    stats = os.stat(filepath)
    return {
        'station': "Unknown",
        'program': os.path.splitext(basename)[0],
        'start': datetime.datetime.fromtimestamp(stats.st_mtime),
        'end': datetime.datetime.fromtimestamp(stats.st_mtime)
    }

def get_program_info(filepath, target_start_time):
    try:
        with ariblib.tsopen(filepath) as ts:
            count = 0
            for eit in ts.sections(EventInformationSection):
                count += 1
                if count > 5000: break
                
                if not hasattr(eit, 'events'): continue

                for event in eit.events:
                    try:
                        st = event.start_time
                        dt = datetime.datetime(st.year, st.month, st.day, st.hour, st.minute, st.second)
                        
                        diff = abs((dt - target_start_time).total_seconds())
                        if diff < 120:
                            title = ""
                            desc = ""
                            for descriptor in event.descriptors:
                                if getattr(descriptor, 'descriptor_tag', 0) == 0x4D:
                                    title = getattr(descriptor, 'event_name_char', "")
                                    desc = getattr(descriptor, 'text_char', "")
                                    break
                            
                            return {
                                "title": title,
                                "description": desc,
                                "start_time": dt,
                                "end_time": dt + datetime.timedelta(seconds=int(event.duration.total_seconds()))
                            }
                    except Exception as e:
                        continue
            return None
    except Exception as e:
        logger.error(f"Error parsing {filepath}: {e}")
        return None

scan_progress = {
    "scanning": False,
    "total": 0,
    "processed": 0,
    "current": "",
    "status": "idle"
}

def scan_and_update(scan_targets=None, db_session=None, batch_size=4, model_name=None, api_key=None, skip_topics=False):
    global scan_progress
    scan_progress["scanning"] = True
    scan_progress["processed"] = 0
    scan_progress["total"] = 0
    scan_progress["status"] = "Scanning directories..."
    scan_progress["current"] = ""

    if not scan_targets:
        scan_targets = [{"path": TS_DIR, "recursive": False}]

    try:
        from ..settings_manager import load_settings
    except (ImportError, ValueError):
        from settings_manager import load_settings
    settings = load_settings()
    custom_prompt = settings.get("topic_prompt")
    api_key = api_key if api_key else settings.get("gemini_api_key")
    
    close_session = False
    if db_session:
        session = db_session
    else:
        session = SessionLocal()
        close_session = True
        
    all_ts_files = []
    
    for target in scan_targets:
        scan_dir = target.get("path")
        is_recursive = target.get("recursive", False)
        
        if not scan_dir or not os.path.exists(scan_dir):
            continue

        if is_recursive:
            found = glob.glob(os.path.join(scan_dir, "**", "*.ts"), recursive=True)
        else:
            found = glob.glob(os.path.join(scan_dir, "*.ts"), recursive=False)
            
        all_ts_files.extend(found)

    scan_progress["status"] = "Cleaning up missing files..."
    db_programs = session.query(Program).all()
    deleted_count = 0
    for p in db_programs:
        if not os.path.exists(p.filepath):
            session.delete(p)
            deleted_count += 1
    
    if deleted_count > 0:
        session.commit()

    ts_files = sorted(list(set(all_ts_files)))
    scan_progress["total"] = len(ts_files)
    scan_progress["status"] = f"Found {len(ts_files)} files. Starting processing..."

    pending_topics = {} 

    for filepath in ts_files:
        filename = os.path.basename(filepath)
        scan_progress["current"] = filename
        
        if not is_file_closed(filepath):
            scan_progress["processed"] += 1
            continue

        base_dir = os.path.dirname(filepath)
        filename_no_ext = os.path.splitext(os.path.basename(filepath))[0]
        srt_path = os.path.join(base_dir, "srt", f"{filename_no_ext}.srt")
        srt_exists = os.path.exists(srt_path)

        existing = session.query(Program).filter(Program.filepath == filepath).first()
        
        if existing:
            # Sync subtitle_status if SRT exists or Topics exist
            has_topics = session.query(Topic).filter(Topic.program_id == existing.id).count() > 0
            if srt_exists or has_topics:
                if existing.subtitle_status != 1:
                    existing.subtitle_status = 1
                    session.commit()
            
            # Skip if explicitly marked as No Subtitles (status 2) and SRT still missing
            if existing.subtitle_status == 2 and not srt_exists:
                scan_progress["processed"] += 1
                continue

            # If SRT exists and Topics already exist, we are fully done with this file
            if srt_exists and has_topics:
                scan_progress["processed"] += 1
                continue
            
            prog = existing
        else:
            scan_progress["status"] = f"Processing EIT: {filename}"
            meta = parse_filename(filepath)
            if meta:
                info = get_program_info(filepath, meta['start'])
                
                title = info['title'] if info and info['title'] else meta['program']
                desc = info['description'] if info else ""
                start_dt = info['start_time'] if info else meta['start']
                end_dt = info['end_time'] if info else meta['end']
                
                prog = Program(
                    title=title,
                    description=desc,
                    start_time=start_dt,
                    end_time=end_dt,
                    channel=meta['station'],
                    filepath=filepath,
                    subtitle_status=1 if srt_exists else 0
                )
                session.add(prog)
                session.commit()
            else:
                scan_progress["processed"] += 1
                continue

        if skip_topics:
             scan_progress["processed"] += 1
             continue

        if not srt_exists:
            scan_progress["status"] = f"Extracting Subtitles: {filename}"
            logger.info(f"Extracting subtitles: {filepath}")
            extracted_srt = extract_subtitles_srt(filepath)
            if extracted_srt:
                srt_path = extracted_srt
                prog.subtitle_status = 1
                session.commit()
            else:
                # Mark as No Subtitles to avoid future retries
                prog.subtitle_status = 2
                session.commit()
                scan_progress["processed"] += 1
                continue

        scan_progress["status"] = f"Parsing Transcript: {filename}"
        transcript_text = get_transcript_text(srt_path)
        if transcript_text:
            pending_topics[filepath] = transcript_text
            
            if len(pending_topics) >= batch_size:
                scan_progress["status"] = f"Generating Topics (Batch of {batch_size})..."
                process_topic_batch(pending_topics, custom_prompt, model_name, api_key=api_key)
                pending_topics = {}

        scan_progress["processed"] += 1

    if pending_topics and not skip_topics:
        scan_progress["status"] = f"Generating Topics (Final Batch of {len(pending_topics)})..."
        process_topic_batch(pending_topics, custom_prompt, model_name, api_key=api_key)

    scan_progress["scanning"] = False
    scan_progress["status"] = "Completed"
    scan_progress["current"] = ""

    if close_session:
        session.close()

def get_scan_progress():
    global scan_progress
    return scan_progress
