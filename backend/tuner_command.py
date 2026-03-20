import os
import json
import shlex

try:
    from .database import SessionLocal, Channel
except ImportError:
    from database import SessionLocal, Channel
def get_channel_info(service_id=None, channel_str=None, type_str=None, network_id=None):
    with SessionLocal() as db:
        query = db.query(Channel)
        if service_id is not None:
            query = query.filter(Channel.sid == service_id)
        if type_str is not None:
            query = query.filter(Channel.type == type_str)
        if network_id is not None:
            query = query.filter(Channel.network_id == network_id)
        if channel_str is not None:
            # We map channel_str to channel_id in DB, or TP for GR tuning
            query = query.filter(Channel.channel_id == channel_str)
        
        c = query.first()
        if c:
            return {
                'id': c.id,
                'channel': c.channel_id,
                'type': c.type,
                'sid': c.sid,
                'tsid': c.tsid,
                'onid': c.network_id,
                'service_name': c.service_name,
                'TP': c.TP,
                'slot': c.slot,
                'visible': c.visible
            }
    return None

def build_recording_command(settings, service_id, channel_type, duration, dest_path, channel_num=None, network_id=None, return_string=False):
    """
    Builds the command list or string for recording (backend & live_stream).
    Returns list of arguments or a shell-escaped string.
    """
    recording_cmd = settings.get("recording_command")
    exec_path = settings.get("recdvb_path")
    if not exec_path.strip():
        exec_path = f"/usr/local/bin/{recording_cmd}"

    args = [exec_path]
    
    if settings.get("recdvb_voltage"):
        args.extend(["--lnb", "15"])
        
    args.extend(["--b25", "--strip"])
    
    c_info = None
    if service_id:
         c_info = get_channel_info(service_id=service_id, type_str=channel_type, network_id=network_id)
         
    if recording_cmd == "recpt1":
        # recpt1 style: recpt1 --b25 --strip --sid SID CHANNEL DUR PATH
        if service_id:
            args.extend(["--sid", str(service_id)])
            
        ch_arg = ""
        if channel_type in ['BS', 'CS']:
            if channel_type == 'BS' and c_info and c_info.get('TP'):
                # For BS, use "TP_slot" format (e.g., BS15_0)
                tp = c_info.get('TP')
                slot = c_info.get('slot', 0)
                if slot is None: slot = 0
                ch_arg = f"{tp}_{slot}"
            else:
                # CS or fallback BS: Use TP if available (e.g., CS2)
                ch_arg = c_info.get('TP') if (c_info and c_info.get('TP')) else (c_info.get('channel') if c_info else channel_num)
                ch_arg = str(ch_arg) if ch_arg else "0"
                # Fallback for BS if TP is missing but it starts with BS
                if channel_type == 'BS' and ch_arg.startswith('BS') and '_' not in ch_arg:
                    ch_arg += "_0"
        else:
            # Terrestrial (GR): Use TP (physical channel)
            ch_arg = c_info.get('TP') if (c_info and c_info.get('TP')) else (c_info.get('channel') if c_info else channel_num)
            ch_arg = str(ch_arg) if ch_arg else "0"
            
        args.extend([ch_arg, str(duration), str(dest_path)])
        
    else:
        # Default recdvb style
        use_tsid = c_info.get('tsid') if c_info else None
        if channel_type in ['BS', 'CS'] and use_tsid:
            # recdvb style for BS/CS: --sid SID TSID DUR PATH
            args.extend(["--sid", str(service_id or (c_info['sid'] if c_info else "0")), str(use_tsid)])
            args.extend([str(duration), str(dest_path)])
        else:
            if service_id:
                 args.extend(["--sid", str(service_id)])
            ch_arg = c_info.get('TP') if c_info else channel_num
            ch_arg = str(ch_arg) if ch_arg else "0"
            args.extend([ch_arg, str(duration), str(dest_path)])

    if return_string:
        return shlex.join(args)
    return args

def build_epg_command(settings, channel_num, channel_type, duration, dest_path, service_id=None, network_id=None, return_string=False):
    """
    Builds the command list or string for grabbing EPG data.
    """
    recording_cmd = settings.get("recording_command")
    exec_path = settings.get("recdvb_path")
    if not exec_path.strip():
        exec_path = f"/usr/local/bin/{recording_cmd}"
    
    args = [exec_path, "--b25"]
    
    if settings.get("recdvb_voltage"):
        args.extend(["--lnb", "15"])
        
    c_info = None
    if channel_num:
         # Try to resolve physical channel (TP) from channel_id
         c_info = get_channel_info(channel_str=channel_num, type_str=channel_type, network_id=network_id, service_id=service_id)

    if channel_num is not None:
        if channel_type == 'BS' and c_info and c_info.get('TP'):
            # Use TP_0 for BS EPG (slot 0 usually carries everything)
            tp = c_info.get('TP')
            ch_arg = f"{tp}_0"
        else:
            ch_arg = c_info.get('TP') if (c_info and c_info.get('TP')) else str(channel_num)
            if channel_type == 'BS' and ch_arg.startswith('BS') and '_' not in ch_arg:
                ch_arg += "_0"
        args.append(ch_arg)
        
    args.extend([str(duration), str(dest_path)])
    
    if return_string:
        return shlex.join(args)
    return args

def get_pkill_pattern(settings, service_id, duration):
    """
    Returns the process matching pattern to be killed safely.
    """
    recording_cmd = settings.get("recording_command")
    exec_path = settings.get("recdvb_path")
    exec_exe = os.path.basename(exec_path or recording_cmd)
    return f"{exec_exe} .* --sid {service_id} .* {duration} -"
