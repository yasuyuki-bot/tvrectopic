import threading
import logging
from datetime import datetime, timedelta

try:
    from ..database import SessionLocal, Channel, EPGProgram, ScheduledRecording
    from ..utils.text import normalize_text
except ImportError:
    from database import SessionLocal, Channel, EPGProgram, ScheduledRecording
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from utils.text import normalize_text

logger = logging.getLogger(__name__)

CHANNELS_LOCK = threading.Lock()

def update_channel_map(scanning_ch_num, discovered_services, scanned_type):
    if not discovered_services: return
    with CHANNELS_LOCK:
        db = SessionLocal()
        try:
            updated = False
            for s in discovered_services:
                c = db.query(Channel).filter(
                    Channel.network_id == s['onid'],
                    Channel.tsid == s['tsid'],
                    Channel.sid == s['sid'],
                    Channel.type == scanned_type
                ).first()

                if c:
                    if s['name'] != "Unknown":
                        c.service_name = s['name']
                    
                    if scanned_type in ['BS', 'CS'] and s.get('channel') is not None:
                        c.TP = s.get('channel')
                    elif scanned_type == 'GR':
                        c.TP = scanning_ch_num

                    if s.get('slot') is not None:
                        c.slot = s.get('slot')
                    updated = True
                else:
                    if scanned_type == 'GR':
                        new_ch_id = f"GR{scanning_ch_num}_{s['sid']}"
                    else:
                        new_ch_id = f"{scanned_type}{s['sid']}"

                    new_c = Channel(
                        type=scanned_type,
                        channel_id=new_ch_id,
                        tsid=s['tsid'],
                        network_id=s['onid'],
                        sid=s['sid'],
                        service_name=s['name'],
                        TP=scanning_ch_num if scanned_type == 'GR' else s.get('channel'),
                        slot=s.get('slot'),
                        visible=True
                    )
                    db.add(new_c)
                    updated = True
                    logger.info(f"  [New Service] {new_c.service_name} (SID: {new_c.sid})")

            if updated:
                db.commit()
        except Exception as e:
            logger.error(f"Error updating channel map: {e}")
            db.rollback()
        finally:
            db.close()

def load_channels():
    db = SessionLocal()
    try:
        channels = db.query(Channel).all()
        return [
            {
                "id": c.id, "type": c.type, "channel": c.channel_id,
                "tsid": c.tsid, "onid": c.network_id, "sid": c.sid,
                "service_name": c.service_name, "TP": c.TP,
                "slot": c.slot, "visible": c.visible
            } for c in channels
        ]
    finally:
        db.close()

def get_channel_id_for_program(all_channels, prog_sid, current_tp, ch_type):
    for c in all_channels:
        if c.get('type') == ch_type and c.get('sid') == prog_sid:
            if ch_type == 'GR':
                if str(c.get('TP')) == str(current_tp):
                    return c.get('channel')
            else:
                return c.get('channel')
    
    if ch_type == 'GR' and current_tp:
        return f"GR{current_tp}_{prog_sid}"
    return None

def process_program_item(db: SessionLocal, item, channel_info, service_name, all_channels=None):
    try:
        event_id = item.get('event_id')
        service_id = item.get('service_id')
        if not service_id:
            service_id = channel_info.get('sid') or channel_info.get('service_id', 0)
            
        if service_id == 0: return

        ch_type = channel_info.get('type')
        current_tp = channel_info.get('TP')
        target_channel_id = get_channel_id_for_program(all_channels, service_id, current_tp, ch_type)
        if not target_channel_id:
            target_channel_id = channel_info.get('channel')

        start_ts = item.get('start')
        end_ts = item.get('end')
        if not start_ts or not end_ts: return
        
        start_dt = datetime.fromtimestamp(start_ts / 1000.0)
        end_dt = datetime.fromtimestamp(end_ts / 1000.0)
        
        desc = normalize_text(item.get('detail', ''))
        ext = item.get('extdetail', [])
        if ext:
            for ex in ext:
                item_desc = normalize_text(ex.get('item_description', ''))
                item_text = normalize_text(ex.get('item', ''))
                desc += f"\n\n【{item_desc}】\n{item_text}"
        
        genre_major, genre_minor = None, None
        cat_list = item.get('category', [])
        if cat_list:
             m = cat_list[0].get('large', {}).get('ja_JP')
             s = cat_list[0].get('middle', {}).get('ja_JP')
             genre_major = m
             genre_minor = s

        duration_sec = int((end_dt - start_dt).total_seconds())
        title = normalize_text(item.get('title'))
        nid = item.get('original_network_id', 0)
        tsid_val = item.get('transport_stream_id', 0)
        
        if nid == 0:
            nid = channel_info.get('onid') or channel_info.get('network_id', 0)
        if tsid_val == 0:
            tsid_val = channel_info.get('tsid', 0)
            
        if (tsid_val == 0 or nid == 0) and all_channels:
            for c in all_channels:
                if c.get('sid') == service_id:
                    if nid != 0 and c.get('onid') != nid: continue
                    if nid == 0: nid = c.get('onid', 0)
                    tsid_val = c.get('tsid', 0)
                    break

        existing = db.query(EPGProgram).filter(
            EPGProgram.event_id == event_id, 
            EPGProgram.channel == target_channel_id
        ).first()
            
        real_prog = None
        if existing:
            existing.title = title
            existing.description = desc
            existing.start_time = start_dt
            existing.end_time = end_dt
            existing.duration = duration_sec 
            existing.genre_major = genre_major
            existing.genre_minor = genre_minor
            real_prog = existing
        else:
            new_prog = EPGProgram(
                event_id=event_id,
                start_time=start_dt, end_time=end_dt, duration=duration_sec,
                title=title, description=desc,
                channel=target_channel_id,
                genre_major=genre_major, genre_minor=genre_minor
            )
            db.add(new_prog)
            db.flush() 
            real_prog = new_prog
            
        overlap_query = db.query(EPGProgram).join(Channel, EPGProgram.channel == Channel.channel_id).filter(
            Channel.sid == service_id,
            Channel.network_id == nid,
            EPGProgram.id != real_prog.id,
            EPGProgram.end_time > start_dt + timedelta(minutes=1),
            EPGProgram.start_time < end_dt - timedelta(minutes=1)
        )
             
        overlaps = overlap_query.all()
        for old_prog in overlaps:
             logger.info(f"Removing overlapping older program {old_prog.event_id} (New: {event_id})")
             old_recs = db.query(ScheduledRecording).filter(ScheduledRecording.program_id == old_prog.id).all()
             for r in old_recs:
                 existing_target_rec = db.query(ScheduledRecording).filter(
                     ScheduledRecording.program_id == real_prog.id,
                     ScheduledRecording.status.in_(["scheduled", "recording", "completed"])
                 ).first()
                 
                 if existing_target_rec:
                     logger.info(f"Target program already reserved. Dropping overlapping reservation {r.id}")
                     db.delete(r)
                 else:
                     logger.info(f"Migrating reservation {r.id} from {old_prog.event_id} to {real_prog.event_id}")
                     r.program_id = real_prog.id
                     r.event_id = real_prog.event_id
                     r.start_time = real_prog.start_time
                     r.end_time = real_prog.end_time
                     r.title = real_prog.title
                     r.description = real_prog.description
             
             db.delete(old_prog)
        
        reservation = db.query(ScheduledRecording).filter(
            ScheduledRecording.event_id == event_id,
            ScheduledRecording.service_id == service_id,
            ScheduledRecording.status == "scheduled"
        ).first()

        if reservation:
            if reservation.start_time != start_dt or reservation.end_time != end_dt:
                old_start = reservation.start_time
                reservation.start_time = start_dt
                reservation.end_time = end_dt
                logger.info(f"Updated Reservation Time for '{reservation.title}': {old_start} -> {start_dt}")

    except Exception as e:
        logger.error(f"Error processing item: {e}")

def save_programs(db: SessionLocal, programs_data, channel_info):
    all_channels = load_channels()
    ch_type = channel_info.get('type')
    current_ch_num = str(channel_info.get('channel', ''))
    current_tp = str(channel_info.get('TP', ''))

    count = 0
    if not isinstance(programs_data, list):
        return 0

    # Group programs by target_channel_id to process them in batches
    channel_groups = {}
    for service in programs_data:
        sid = service.get('service_id', 0)
        match = None
        for c in all_channels:
            if c.get('type') == ch_type and c.get('sid') == sid:
                if ch_type == 'GR':
                    if str(c.get('channel', '')) == current_ch_num:
                        match = c; break
                else:
                    match = c; break
        
        target_channel_id = match.get('channel') if match else (f"GR{current_tp}_{sid}" if ch_type == 'GR' else channel_info.get('channel'))
        if not target_channel_id: continue
        
        if target_channel_id not in channel_groups:
            channel_groups[target_channel_id] = {'info': match or channel_info, 'programs': []}
        
        if 'programs' in service:
            channel_groups[target_channel_id]['programs'].extend(service['programs'])

    for target_ch_id, group in channel_groups.items():
        prog_items = group['programs']
        if not prog_items: continue
        
        # Fetch all existing programs for this channel once
        existing_progs = db.query(EPGProgram).filter(EPGProgram.channel == target_ch_id).all()
        existing_map = {p.event_id: p for p in existing_progs}
        
        info = group['info']
        nid = info.get('onid') or info.get('network_id', 0)
        sid = info.get('sid') or info.get('service_id', 0)

        for item in prog_items:
            try:
                event_id = item.get('event_id')
                start_ts = item.get('start')
                end_ts = item.get('end')
                if not event_id or not start_ts or not end_ts: continue

                start_dt = datetime.fromtimestamp(start_ts / 1000.0)
                end_dt = datetime.fromtimestamp(end_ts / 1000.0)
                duration_sec = int((end_dt - start_dt).total_seconds())
                title = normalize_text(item.get('title'))
                
                # Build description
                desc = normalize_text(item.get('detail', ''))
                ext = item.get('extdetail', [])
                if ext:
                    for ex in ext:
                        desc += f"\n\n【{normalize_text(ex.get('item_description', ''))}】\n{normalize_text(ex.get('item', ''))}"

                genre_major, genre_minor = None, None
                cat_list = item.get('category', [])
                if cat_list:
                    genre_major = cat_list[0].get('large', {}).get('ja_JP')
                    genre_minor = cat_list[0].get('middle', {}).get('ja_JP')

                existing = existing_map.get(event_id)
                if existing:
                    existing.title = title
                    existing.description = desc
                    existing.start_time = start_dt
                    existing.end_time = end_dt
                    existing.duration = duration_sec
                    existing.genre_major = genre_major
                    existing.genre_minor = genre_minor
                else:
                    new_prog = EPGProgram(
                        event_id=event_id, start_time=start_dt, end_time=end_dt,
                        duration=duration_sec, title=title, description=desc,
                        channel=target_ch_id, genre_major=genre_major, genre_minor=genre_minor
                    )
                    db.add(new_prog)
                
                # Check for reservation updates
                reservation = db.query(ScheduledRecording).filter(
                    ScheduledRecording.event_id == event_id,
                    ScheduledRecording.service_id == sid,
                    ScheduledRecording.status.in_(["scheduled", "recording"])
                ).first()

                if reservation:
                    if reservation.start_time != start_dt or reservation.end_time != end_dt:
                        old_end = reservation.end_time
                        reservation.start_time = start_dt
                        reservation.end_time = end_dt
                        logger.info(f"Updated Reservation/Recording Time for '{reservation.title}' via EPG: {old_end} -> {end_dt}")

                count += 1
            except Exception as e:
                logger.error(f"Error processing item in batch: {e}")

        # Check for overlapping programs to remove (clean up old chunks)
        # For simplicity, we can do this per channel batch
        db.flush() 
    
    return count

def cleanup_old_epg(settings):
    retention_days = settings.get("epg_retention_days", 7)
    if retention_days <= 0:
        logger.info("EPG Retention: Unlimited (0). Skipping cleanup.")
        return

    threshold = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=retention_days)
    logger.info(f"EPG Cleanup: Removing programs ending before {threshold}")
    
    db = SessionLocal()
    try:
        deleted_count = db.query(EPGProgram).filter(EPGProgram.end_time < threshold).delete()
        db.commit()
        logger.info(f"EPG Cleanup: Deleted {deleted_count} old programs.")
    except Exception as e:
        logger.error(f"EPG Cleanup Error: {e}")
        db.rollback()
    finally:
        db.close()
