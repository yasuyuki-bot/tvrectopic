import os
import subprocess
import logging

logger = logging.getLogger(__name__)

BILINGUAL_MARKERS = ["【二】", "[二]", "(二)", "二か国語", "二ヵ国語", "二カ国語", "Bilingual", "multilingual", "主・副", "主+副", "副音声", "Dual Mono"]

FFMPEG_VERSION_CACHE = None

def get_ffmpeg_version():
    """
    Returns the FFmpeg version as a tuple of integers (major, minor).
    """
    global FFMPEG_VERSION_CACHE
    if FFMPEG_VERSION_CACHE is not None:
        return FFMPEG_VERSION_CACHE
    
    try:
        res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            line = res.stdout.splitlines()[0]
            parts = line.split("version")
            if len(parts) > 1:
                v_str = parts[1].strip().split("-")[0].split()[0]
                v_parts = []
                for p in v_str.split("."):
                    if p.isdigit():
                        v_parts.append(int(p))
                    else:
                        break
                FFMPEG_VERSION_CACHE = tuple(v_parts)
                logger.info(f"FFmpeg Version Detected: {FFMPEG_VERSION_CACHE}")
                return FFMPEG_VERSION_CACHE
    except Exception as e:
        logger.error(f"Error detecting ffmpeg version: {e}")
    
    FFMPEG_VERSION_CACHE = (0, 0)
    return FFMPEG_VERSION_CACHE

def parse_time(t_val):
    """
    Parses a time value (float, int, or HH:MM:SS string) into total seconds.
    """
    if t_val is None:
        return 0.0
    if isinstance(t_val, (int, float)):
        return float(t_val)
    
    try:
        t_str = str(t_val)
        parts = t_str.split(':')
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return float(t_str)
    except:
        return 0.0

def is_bilingual_program(title, description=None, filepath=None):
    """
    Checks if a program is bilingual based on its title, description, or filename.
    """
    text_to_scan = f"{title or ''} {description or ''} {os.path.basename(filepath or '')}"
    return any(marker in text_to_scan for marker in BILINGUAL_MARKERS)

def get_terrestrial_stations():
    """
    Returns a list of keywords for detecting terrestrial stations.
    """
    return [
        "NHK総合", "NHKEテレ", "NHK Eテレ", "毎日放送", "MBS", "朝日放送", "ABC", 
        "関西テレビ", "カンテレ", "読売テレビ", "ytv", "テレビ大阪", "サンテレビ", "KBS京都"
    ]

def is_terrestrial_station(text):
    """
    Checks if the given text (title, channel name, etc.) contains a terrestrial station keyword.
    """
    if not text:
        return False
    return any(station in text for station in get_terrestrial_stations())

def get_program_type(network_id=None, channel_id=None, service_name=None):
    """
    Determines the program type (GR, BS, or CS) based on network ID, channel ID, and service name.
    """
    # 1. Use Network ID if available
    if network_id == 4:
        return "BS"
    elif network_id in (1, 6, 7): # CS / SkyPerfecTV
        return "CS"
    elif network_id and network_id >= 30000:
        return "GR"
    
    # 2. Fallback to Heuristics
    ch = channel_id or ""
    sn = service_name or ""
    
    if ch.startswith("BS") or sn.startswith("BS"):
        return "BS"
    elif ch.startswith("CS") or sn.startswith("CS"):
        return "CS"
    
    # Check for terrestrial station names
    if is_terrestrial_station(sn) or is_terrestrial_station(ch):
        return "GR"
        
    return "GR" # Default to Terrestrial
