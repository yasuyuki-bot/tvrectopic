from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, not_
from datetime import datetime, timedelta
import logging
import unicodedata

# Import models
try:
    from .database import Program, EPGProgram, ScheduledRecording, AutoReservation, Channel, SessionLocal
    from .recorder import recorder
    from .utils import get_program_type
except ImportError:
    from database import Program, EPGProgram, ScheduledRecording, AutoReservation, Channel, SessionLocal
    from recorder import recorder
    from utils import get_program_type

logger = logging.getLogger(__name__)

import os
import json

try:
    from .utils import normalize_string
except (ImportError, ValueError):
    from utils import normalize_string


def match_program(rule: AutoReservation, program: EPGProgram):
    # 1. Keyword
    keyword = rule.keyword.strip() if rule.keyword else ""
    if rule.keyword:
        # Split original keyword by spaces for AND search
        # We use the original string before full normalization to find spaces
        keywords = rule.keyword.split()
        
        # Determine Search Target
        target_text = normalize_string(program.title)
        
        # Check if search_target is 'title_and_description'
        if getattr(rule, 'search_target', 'title') == 'title_and_description':
            desc = normalize_string(program.description)
            target_text += " " + desc
            
        for k in keywords:
            # Normalize each keyword segment individually
            normalized_k = normalize_string(k)
            if normalized_k not in target_text:
                return False
    
    # 2. Day of Week
    # rule.days_of_week is "0,1,2..."
    if rule.days_of_week:
        target_dows = [int(x) for x in rule.days_of_week.split(',') if x.strip().isdigit()]
        # program.start_time is datetime
        prog_dow = program.start_time.weekday() # 0=Mon
        if prog_dow not in target_dows:
            return False
            
    # 3. Genre
    # rule.genres is string (maybe JSON list or CSV). Let's assume CSV of major genres.
    if rule.genres and rule.genres.strip():
        # strict match or partial? Modal usually provides exact strings.
        # program.genre_major
        if program.genre_major:
             target_genres = rule.genres.split(',')
             if program.genre_major not in target_genres:
                 return False

    # 4. Channel / Type
    # rule.channels is CSV of "BS15_0" etc.
    # rule.types is "GR,BS,CS"
    
    # Filter by Type first
    # We don't strictly have 'type' in EPGProgram, but we have service_id/channel.
    # We can infer type or check channel config?
    # EPGProgram has 'channel' (e.g. "24", "BS15_0").
    # Simple heuristic:
    if rule.types:
        allowed_types = rule.types.split(',')
        # Use centralized type detection
        nid = program.network_id
        ch = program.channel or ""
        sn = program.service_name or ""
        p_type = get_program_type(nid, ch, sn)
        
        if p_type not in allowed_types:
            return False

    # Filter by specific Channel
    if rule.channels:
        target_channels = rule.channels.split(',')
        # We need to check if the program matches any of the targets.
        # Targets can be:
        # - "NID-SID" (New Precise Format) e.g. "4-101"
        # - "SID" (Legacy) e.g. "101" (Ambiguous, matches any NID with this SID)
        # - "ChannelString" e.g. "BS15_0", "24"
        
        # Construct candidate keys for this program
        candidates = set()
        
        # 1. Precise Key (NID-SID) - Preferred
        if program.network_id and program.service_id:
            candidates.add(f"{program.network_id}-{program.service_id}")
            
        # 2. Legacy SID Key
        if program.service_id:
            candidates.add(str(program.service_id))
            
        # 3. Channel String Key (e.g. from scanner)
        if program.channel:
            candidates.add(str(program.channel))
            
        # Check intersection
        is_match = False
        for t in target_channels:
            if t in candidates:
                is_match = True
                break
        
        if not is_match:
            return False

    # 5. Time Range
    # rule.time_range_start/end "HH:MM"
    # Logic: Program must be within this range.
    # Actually requirement: "Program Start <= Time Range <= Program End"
    # -> The Time Range is contained within the program?
    # Wait, "時刻範囲が、番組の開始時刻から終了時刻の範囲に含まれる番組"
    # Literally: "Time Range is inside [Start, End]"
    # E.g. Range 10:00-11:00. Program 09:00-12:00. -> Match (Range is inside Program)
    # E.g. Range 10:00-11:00. Program 10:30-11:30. -> No match (11:00 is outside 10:30-11:30? No, 11:00 is inside. But 10:00 is not.)
    # Interpretation: The User specifies a "Time Window" they are interested in.
    # The requirement says: "Time Range is contained in Program Range".
    # So if I set "19:00-20:00", I want programs that COVER this hour fully? That sounds strict.
    # Or maybe "Program contains ANY part of the Time Range?" NO.
    # "時刻範囲が...範囲に含まれる" -> Subject=TimeRange, Target=ProgramRange.
    # TimeRange \subset ProgramRange.
    # Start_Range >= Start_Prog AND End_Range <= End_Prog.
    if rule.time_range_start and rule.time_range_end:
        try:
            t_start = datetime.strptime(rule.time_range_start, "%H:%M").time()
            t_end = datetime.strptime(rule.time_range_end, "%H:%M").time()
            
            p_start = program.start_time.time()
            p_end = program.end_time.time()
            
            p_wraps = p_start > p_end
            t_wraps = t_start > t_end
            
            # Universal Overlap Logic for wrapping intervals
            if not t_wraps:
                if not p_wraps:
                    # Both standard
                    if not (p_end >= t_start and p_start <= t_end):
                        return False
                else:
                    # Program wraps, Range standard
                    if not (p_start <= t_end or p_end >= t_start):
                        return False
            else:
                if not p_wraps:
                    # Range wraps, Program standard
                    if not (p_start <= t_end or p_end >= t_start):
                        return False
                else:
                    # Both wrap -> always match (both contain midnight)
                    pass

        except Exception as e:
            logger.error(f"Time match error: {e}")
            pass # invalid time format, ignore filter

    return True

# Global cache for channels to avoid repeated IO
_channels_cache = None
_channels_mtime = 0

def get_cached_channels():
    # Database-backed channel info
    try:
        with SessionLocal() as db:
            channels = db.query(Channel).all()
            return [
                {
                    'type': c.type,
                    'onid': c.network_id,
                    'tsid': c.tsid,
                    'sid': c.sid,
                    'service_name': c.service_name,
                    'channel': c.channel_id,
                    'visible': c.visible
                } for c in channels
            ]
    except Exception as e:
        logger.error(f"Error loading channels from DB: {e}")
        return []

def search_programs(db: Session, rule: AutoReservation, channels_data: list = None):
    # If channels_data not provided, fetch it (fallback)
    if channels_data is None:
        channels_data = get_cached_channels()
        
    # Optimizing search by filtering service_id in DB query if possible
    # Base query: Future programs
    now = datetime.now()
    query = db.query(EPGProgram).join(Channel, EPGProgram.channel == Channel.channel_id).filter(EPGProgram.start_time > now)
    
    # 1. Resolve Target Service IDs based on Rule Types/Channels
    type_sids = set()
    channel_sids = set()
    has_type_filter = False
    
    # Filter by Type (GR, BS, CS)
    if rule.types:
        has_type_filter = True
        allowed_types = [t.strip() for t in rule.types.split(',')]
        
        for c in channels_data:
            c_type = c.get('type')
            if c_type in allowed_types:
                if 'sid' in c:
                    type_sids.add(c['sid'])
                    
    # Filter by Specific Channels
    if rule.channels:
        target_channels = [c.strip() for c in rule.channels.split(',')]
        
        for c in channels_data:
            # Match by different keys
            # 1. NID-SID
            nid_sid = f"{c.get('onid')}-{c.get('sid')}"
            # 2. SID
            sid_str = str(c.get('sid'))
            # 3. Channel String
            ch_str = str(c.get('channel'))
            
            for t in target_channels:
                 if t == nid_sid or t == sid_str or t == ch_str:
                     if 'sid' in c:
                         channel_sids.add(c['sid'])

    # Determine Final Target SIDs - INTERSECTION / OVERRIDE Logic
    # If channels are specified, we should restrict to ONLY those channels.
    # But usually valid config means those channels also match the type.
    # If a channel is specified but doesn't match the type, what happens?
    # Old logic (match_program) requires BOTH type check AND channel check.
    # So if I pick "CS" and "GR-NHK", it returns nothing.
    # So Intersection is correct.
    
    target_sids = set()
    
    if rule.channels:
        if has_type_filter:
            # Intersection: Only SIDs that are in BOTH sets
            if not type_sids: # Type is set but no SIDs found for it?
                 target_sids = set()
            else:
                 target_sids = channel_sids.intersection(type_sids)
        else:
            # Only Channel filter
            target_sids = channel_sids
    else:
        # Only Type filter (or None)
        target_sids = type_sids

    # Apply DB Filter if we have targets
    # If no types/channels specified, search ALL (fallback)
    if target_sids:
        query = query.filter(Channel.sid.in_(target_sids))
    elif has_type_filter and not rule.channels: # Types set but empty?
        return []
    elif rule.channels and not target_sids: # Channels set but no SIDs found?
        return []

    # Apply DB Keyword Pre-filtering
    if rule.keyword:
        keywords = rule.keyword.split()
        if keywords:
            # For each keyword, it must match either title or desc depending on target
            and_conditions = []
            for k in keywords:
                # NORMALIZE the keyword to match the DB-stored format (NFKC)
                # SQLite LIKE is case-insensitive for ASCII but width-sensitive.
                # Since titles are saved with normalize_text (NFKC), we must match that.
                norm_k = unicodedata.normalize('NFKC', k)
                like_term = f"%{norm_k}%"
                
                if getattr(rule, 'search_target', 'title') == 'title_and_description':
                    and_conditions.append(or_(
                        EPGProgram.title.like(like_term),
                        EPGProgram.description.like(like_term)
                    ))
                else:
                    and_conditions.append(EPGProgram.title.like(like_term))
                    
            if and_conditions:
                query = query.filter(and_(*and_conditions))

    # 2. Load invisible channels for filtering (using cached data)

    # 2. Load invisible channels for filtering (using cached data)
    invisible_service_keys = set()
    for c in channels_data:
        if c.get("visible") is False:
             key = (str(c.get('channel')), c.get('sid'), c.get('onid'))
             invisible_service_keys.add(key)

    candidates = query.all()
    seen = {}
    
    for p in candidates:
        # Check if channel is visible
        p_key = (str(p.channel), p.service_id, p.network_id)
        if p_key in invisible_service_keys:
            continue
            
        if match_program(rule, p):
            # Deduplication based on Channel + Event ID
            # Use channel string because ServiceID might be 0 or inconsistent in some data sources
            key = (p.channel, p.event_id)
            
            if key in seen:
                # If we already have this event, check if current one is "better"
                # Prefer entry with non-zero Service ID
                existing = seen[key]
                if existing.service_id == 0 and p.service_id != 0:
                    seen[key] = p
            else:
                seen[key] = p
            
    # Sort results by start_time
    results = sorted(seen.values(), key=lambda x: x.start_time)
            
    return results

def get_recorded_titles_set(db: Session) -> set:
    """Returns a set of normalized titles for all completed or recording programs."""
    titles = set()
    
    # History/Recording
    recs = db.query(ScheduledRecording.title).filter(
        ScheduledRecording.status.in_(["recording", "completed"])
    ).all()
    for (t,) in recs:
        if t: titles.add(normalize_string(t))
            
    # Library

    progs = db.query(Program.title).all()
    for (t,) in progs:
        if t: titles.add(normalize_string(t))
            
    return titles

def get_scheduled_titles_map(db: Session) -> dict:
    """Returns a map of {normalized_title: [id1, id2, ...]} for all scheduled programs."""
    title_map = {}
    recs = db.query(ScheduledRecording.id, ScheduledRecording.title).filter(
        ScheduledRecording.status == "scheduled"
    ).all()
    for rid, title in recs:
        if not title: continue
        norm = normalize_string(title)
        if norm not in title_map:
            title_map[norm] = []
        title_map[norm].append(rid)
    return title_map

def is_program_duplicate(db: Session, rule, title: str, existing_normalized_titles: set = None) -> bool:
    # Deprecated in favor of direct logic in execute_auto_reservation for finer control
    return False

def execute_auto_reservation(db: Session, rule_id: int, force_recover_manual: bool = False, channels_data: list = None):
    rule = db.query(AutoReservation).filter(AutoReservation.id == rule_id).first()
    if not rule or not rule.active:
        return 0
    
    if channels_data is None:
        channels_data = get_cached_channels()
        
    matches = search_programs(db, rule, channels_data=channels_data)
    count = 0
    
    # 0. Prep comparison sets
    # tracked_in_run: Titles specifically picked as 'scheduled' during this execution
    scheduled_titles_in_run = set()
    recorded_titles = get_recorded_titles_set(db)
    scheduled_title_map = get_scheduled_titles_map(db) # title -> [scheduled_ids]
    
    # 0. Cleanup Old Reservations (that no longer match the rule)
    # Fetch all current future reservations for this rule once
    all_future_res = db.query(ScheduledRecording).filter(
        ScheduledRecording.auto_reservation_id == rule.id,
        ScheduledRecording.start_time > datetime.now()
    ).all()
    
    # Create lookup for existing reservations to avoid N+1 inside the loop
    existing_map = {(res.service_id, res.event_id): res for res in all_future_res}
    
    match_ids = set()
    for m in matches:
        match_ids.add((m.service_id, m.event_id))
        
    for res in all_future_res:
        if res.status in ["recording", "completed"]:
            continue
        key = (res.service_id, res.event_id)
        if key not in match_ids:
            # Check if there's another program with the same service/event in matches
            # EPG update might have slightly changed NID or something? 
            # Usually strict match is fine, but EPG update shouldn't cancel valid runs.
            # Use logger for cancelling reservations to ensure it's captured in log files
            logger.info(f"Auto Reservation Cleanup: Cancelling {res.title} (Reason: No longer matches rule {rule.name})")
            db.delete(res)
    
    # Re-fetch matches to ensure we have latest states if needed, but 'matches' is from recent search
    for prog in matches:
        key = (prog.service_id, prog.event_id)
        existing = existing_map.get(key)
        norm_title = normalize_string(prog.title)
        
        # Determine if this broadcast is a duplicate of *another* broadcast
        is_dub = False
        if not getattr(rule, 'allow_duplicates', True):
            # A broadcast is a duplicate if:
            # - It's already recorded in history/library
            # - It's already been picked as 'the winner' in this current run
            # - It's already scheduled in DB, UNLESS it's the specific instance we're going to pick as the winner.
            
            if norm_title in recorded_titles:
                is_dub = True
            elif norm_title in scheduled_titles_in_run:
                is_dub = True
            elif norm_title in scheduled_title_map:
                # If we haven't picked a winner yet for this title in this run, 
                # we check if 'existing' is one of the currently scheduled ones.
                # If it is, WE MUST PICK ONE as the primary.
                # Usually we pick the EARLIEST one. matches is already ordered by start_time.
                # So the FIRST match we see for this title that hasn't been blocked by recorded_titles 
                # will be our winner.
                pass
            
        # If it's NOT a duplicate (due to recorded history or being after the winner), 
        # we mark this title as 'seen' (winner picked) for this run.
        if not is_dub:
            scheduled_titles_in_run.add(norm_title)
            # If we just picked this title as the 'winner' for this run, 
            # any OTHER instance in the DB that isn't this 'existing' one is now effectively a duplicate.
            # But the is_dub logic above for 'scheduled_titles_in_run' handles subsequent matches in the loop.

        if is_dub:
             if existing:
                  if existing.status == "scheduled" or (existing.status == "skipped" and existing.skip_reason == "re-evaluating"):
                      existing.status = "skipped"
                      existing.skip_reason = "duplicate"
                      logger.info(f"Auto Reservation Updated to Skipped (Duplicate): {prog.title}")
                  elif existing.status == "skipped" and existing.skip_reason == "manual_delete" and force_recover_manual:
                      # If manually requested to recover, and it turned out to be a duplicate,
                      # update reason to duplicate so it can be handled properly.
                      existing.skip_reason = "duplicate"
             else:
                  new_rec = ScheduledRecording(
                      program_id=prog.id,
                      event_id=prog.event_id,
                      service_id=prog.service_id,
                      network_id=prog.network_id,
                      start_time=prog.start_time,
                      end_time=prog.end_time,
                      title=prog.title,
                      description=prog.description,
                      channel=prog.channel or rule.channels, 
                      service_name=prog.service_name,
                      status="skipped",
                      skip_reason="duplicate",
                      auto_reservation_id=rule.id,
                      recording_folder=rule.recording_folder
                  )
                  db.add(new_rec)
                  db.flush()
                  logger.info(f"Auto Reservation Created as Skipped (Duplicate): {prog.title}")
             continue

        # If it reaches here, it's NOT a duplicate (or duplicates allowed).
        # We want to make it 'scheduled' if it's currently 'skipped' (recovery)
        
        # Check for manual delete priority
        if existing and existing.status == "skipped" and existing.skip_reason == "manual_delete":
            if not force_recover_manual:
                logger.info(f"Auto Reservation ignored due to manual delete: {prog.title}")
                continue # Skip this program entirely, do not re-schedule
            else:
                existing.status = "scheduled"
                existing.skip_reason = None
                logger.info(f"Auto Reservation Manually Recovered from Delete: {prog.title}")
                
        # If previously skipped due to duplicate, but now duplicates are allowed or duplicate gone
        elif existing and existing.status == "skipped" and existing.skip_reason == "duplicate":
             existing.status = "scheduled"
             existing.skip_reason = None
             logger.info(f"Auto Reservation Restored from Duplicate Skip: {prog.title}")

        # 1. Check Tuner Conflict
        
        # NOTE: check_tuner_conflict should see sequential updates since we db.flush() below.
        conflict_status, msg = recorder.check_tuner_conflict(db, prog.start_time, prog.end_time, prog.channel, service_id=prog.service_id, network_id=prog.network_id, is_manual=False, exclude_id=existing.id if existing else None)
        is_conflict = (conflict_status != "ok")
        
        if existing:
            # Sync recording folder if rule changed
            if existing.recording_folder != rule.recording_folder:
                logger.info(f"Syncing recording folder for {existing.title}: {existing.recording_folder} -> {rule.recording_folder}")
                existing.recording_folder = rule.recording_folder

            # If currently recording or completed, we don't change status to skipped/scheduled
            if existing.status in ["recording", "completed"]:
                continue

            # If time has changed (EPG Update)
            start_diff = abs((existing.start_time - prog.start_time).total_seconds())
            end_diff = abs((existing.end_time - prog.end_time).total_seconds())
            if start_diff > 1 or end_diff > 1:
                logger.info(f"EPG Update Detected for {existing.title}: Time changed. Updating {existing.start_time} -> {prog.start_time}")
                existing.start_time = prog.start_time
                existing.end_time = prog.end_time
                count += 1
            
            # Re-evaluate status based on current conflict check
            if is_conflict:
                if existing.status != "skipped" or existing.skip_reason != "conflict":
                    existing.status = "skipped"
                    existing.skip_reason = "conflict"
                    logger.info(f"Auto Reservation changed to skipped due to conflict: {prog.title} (Rule: {rule.name})")
                    db.flush()
            else:
                if existing.status != "scheduled":
                    existing.status = "scheduled"
                    existing.skip_reason = None
                    logger.info(f"Auto Reservation Scheduled/Recovered: {prog.title} (Rule: {rule.name})")
                    db.flush()
                    count += 1
                scheduled_titles_in_run.add(norm_title)
            continue
            
        # 2. Create New Reservation (either scheduled or skipped)
        status = "skipped" if is_conflict else "scheduled"
        skip_reason = "conflict" if is_conflict else None
        
        new_rec = ScheduledRecording(
            program_id = prog.id,
            event_id = prog.event_id,
            service_id = prog.service_id,
            network_id = prog.network_id,
            start_time = prog.start_time,
            end_time = prog.end_time,
            title = prog.title,
            description = prog.description,
            channel = prog.channel,
            service_name = prog.service_name,
            status = status,
            skip_reason = skip_reason,
            recording_folder = rule.recording_folder,
            auto_reservation_id = rule.id
        )
        db.add(new_rec)
        db.flush()
        if status == "scheduled":
            count += 1
            scheduled_titles_in_run.add(norm_title)
            logger.info(f"Auto Reserved: {prog.title} (Rule: {rule.name})")
        else:
            logger.info(f"Auto Reservation Skipped (Saved as skipped): {prog.title} - {msg}")
        
    db.commit()
    return count

def cleanup_past_skipped_reservations(db: Session):
    """
    Deletes past reservations that were skipped or manually deleted.
    This keeps the reservation list clean from old, irrelevant entries.
    """
    now = datetime.now()
    # Target reasons: duplicate (重複スキップ), conflict (時間重複スキップ), manual_delete (手動削除)
    target_reasons = ["duplicate", "conflict", "manual_delete"]
    
    deleted = db.query(ScheduledRecording).filter(
        ScheduledRecording.end_time < now,
        ScheduledRecording.status == "skipped",
        ScheduledRecording.skip_reason.in_(target_reasons)
    ).delete(synchronize_session=False)
    
    if deleted > 0:
        db.commit()
        logger.info(f"Cleaned up {deleted} past skipped/manual_delete reservations.")
    return deleted

def run_all_auto_reservations(db: Session):
    # 0. Cleanup past skipped/manual_delete entries
    cleanup_past_skipped_reservations(db)
    
    # 1. Global Masking: Temporarily treat all future auto-reservations as skipped
    # to allow fair re-evaluation and filling of available tuner slots in rule order.
    # Exclude those already recording or completed.
    future_auto_res = db.query(ScheduledRecording).filter(
        ScheduledRecording.auto_reservation_id != None,
        ScheduledRecording.start_time > datetime.now(),
        ScheduledRecording.status == "scheduled"
    ).all()
    
    for res in future_auto_res:
        res.status = "skipped"
        res.skip_reason = "re-evaluating"
    db.flush()

    rules = db.query(AutoReservation).filter(AutoReservation.active == True).all()
    # Sort by priority (1 is highest, so ascending)
    rules.sort(key=lambda r: getattr(r, 'priority', 5))
    
    channels_data = get_cached_channels()
    total = 0
    for rule in rules:
        total += execute_auto_reservation(db, rule.id, channels_data=channels_data)
    return total

def recover_skipped_reservations(db: Session):
    """
    Scans all 'skipped' reservations and tries to schedule them again.
    Used when a reservation is deleted or cancelled, potentially freeing up a tuner.
    """
    skipped_res = db.query(ScheduledRecording).filter(
        ScheduledRecording.status == "skipped",
        ScheduledRecording.start_time > datetime.now()
    ).all()
    
    recovered_count = 0
    
    for res in skipped_res:
        # Check if it was skipped due to being a duplicate!
        if res.skip_reason in ["duplicate", "manual_delete"]: # Never auto-recover a manual delete request
            continue # Do not recover, it's a duplicate or manually deleted!

        # Check Tuner Conflict again
        conflict_status, msg = recorder.check_tuner_conflict(db, res.start_time, res.end_time, res.channel, service_id=res.service_id, is_manual=False)
        is_conflict = (conflict_status != "ok")        
        if not is_conflict:
            res.status = "scheduled"
            logger.info(f"Recovered Skipped Reservation: {res.title}")
            recovered_count += 1
            
    if recovered_count > 0:
        db.commit()
        
    return recovered_count
