import logging
logger = logging.getLogger(__name__)
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

# FFmpeg Presets (Internal Defaults)
FFMPEG_PRESETS = {
    "playback": {
        "cpu": "-vf yadif -c:v libx264 -preset fast -crf 18 -c:a aac",
        "nvenc": "-hwaccel cuda -hwaccel_output_format cuda -vf yadif_cuda -c:v h264_nvenc -preset p5 -rc vbr -cq 20 -c:a aac",
        "qsv": "-vf \"yadif,format=nv12\" -c:v h264_qsv -preset slow -global_quality 18 -c:a aac"
    },
    "mp4": {
        "cpu": "-vf yadif -c:v libx264 -preset fast -crf 18 -c:a aac",
        "nvenc": "-hwaccel cuda -hwaccel_output_format cuda -vf yadif_cuda -c:v h264_nvenc -preset p5 -rc vbr -cq 20 -qmin 15 -qmax 25 -profile:v high -spatial-aq 1 -temporal-aq 1 -c:a aac",
        "qsv": "-vf \"yadif,format=nv12\" -c:v h264_qsv -preset slow -global_quality 18 -c:a aac"
    }
}

def get_default_settings():
    """
    Returns the single source of truth for default settings.
    """
    return {
        # EPG / System
        "epg_duration": {"GR": 60, "BS": 240, "CS": 150},
        "update_times": ["05:30"],
        "epg_retention_days": 7,
        "font_size": "medium",
        
        # Tuner Limits
        "tuner_count_gr": 2,
        "tuner_count_bs_cs": 2,
        "tuner_count_shared": 0,
        
        # Recording General
        "recording_folder": r"C:\TVRecordings" if os.name == 'nt' else "/var/lib/tvrectopic/recordings",
        "filename_format": "{ServiceName}_{Title}_{Date}{Time}-{EndDate}{EndTime}.ts",
        "recdvb_voltage": False,
        "recording_start_margin": 2,
        "recording_retry_interval": 1,
        "recording_margin_end": 3,
        
        # External Tools / SSH
        "recording_command": "recdvb",
        "recdvb_path": "/usr/local/bin/recdvb",
        "epgdump_path": "/usr/local/bin/epgdump",
        "ssh_host": "",
        "ssh_user": "",
        "ssh_pass": "",
        "qsv_device_path": "/dev/dri/renderD128",
        
        # AI / Topics
        "gemini_model_name": "gemini-2.5-flash",
        "topic_prompt": "Analyze the following video transcripts (separated by VIDEO_ID) and split each into distinct topics.\n\nFor each topic in each video, provide:\n1. start: The starting timestamp (H:MM:SS.cs) from the text.\n2. end: The ending timestamp (H:MM:SS.cs) from the text.\n3. title: A concise, catchy headline for the topic (Japanese).\n\nRules:\n- <b>Topic Grouping</b>: Identify distinct segments or stories. <b>Group all related content</b> for the same subject into a single topic.\n- <b>INCLUDE ALL CONTENT</b>: Commercials (CM), Weather Forecasts, Openings, Endings, and transitions. \n- <b>NO GAPS</b>: There should be NO gaps between topics. The end of one topic should be the start of the next.\n- <b>Labeling</b>: Label non-content segments clearly (e.g. \"CM\", \"Weather\", \"Opening\").\n- <b>NO SUMMARY</b>: Do not generate a summary.\n- <b>STRICT SEPARATION</b>: Each 'VIDEO_ID' block corresponds to a DIFFERENT video file. The contents are completely unrelated. \n  - <b>DO NOT</b> mix information between VIDEO_IDs. \n  - <b>DO NOT</b> let the topics of one video influence another.\n  - If a video contains only CMs or irrelevant content, label it as such WITHIN that VIDEO_ID's list only.\n\nOutput Format (JSON):\n{\n  \"VID_0\": [\n      { \"start\": \"0:00:00.00\", \"end\": \"0:01:23.00\", \"title\": \"Headline...\" },\n      ...\n  ]\n}\n\nTRANSCRIPTS:\n{transcripts}", 
        "topic_batch_size": 4,
        "topic_schedules": [],
        "topic_scan_folders": [],
        "topic_offset_sec": -6,
        
        # MP4 Conversion / Playback (referencing presets)
        "video_resume_enabled": True,
        "video_resume_sync_enabled": False,
        "auto_mp4_convert": False,
        "delete_ts_after_convert": False,
        "ffmpeg_options": FFMPEG_PRESETS["playback"]["qsv"],
        "mp4_convert_options": FFMPEG_PRESETS["mp4"]["cpu"],
        "adaptive_streaming_enabled": True,  # 25s+: 0.5x, 15s+: 1.0x, 8s+: 40Mbps, <8s: 80Mbps burst
        "burst_transmission_size": 20 * 1024 * 1024  # 20MB default burst
    }

def load_settings():
    """
    Loads settings from JSON and merges with defaults.
    """
    settings = get_default_settings()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # --- Auto-Migration: Refactor Presets (2026-03-07) ---
                # Remove ffmpeg_presets from settings.json as they are now managed in code.
                needs_save = False
                if 'ffmpeg_presets' in data:
                    del data['ffmpeg_presets']
                    needs_save = True

                if needs_save:
                    logger.info("Cleaning up settings.json: Removing redundant FFmpeg presets.")
                    with open(SETTINGS_FILE, "w", encoding="utf-8") as fw:
                        json.dump(data, fw, indent=4, ensure_ascii=False)
                # --------------------------------------------------------------------

                settings.update(data)
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
    return settings

def save_settings(settings_dict):
    """
    Saves settings to JSON.
    """
    try:
        # Don't save internal presets to settings.json
        save_data = settings_dict.copy()
        if "ffmpeg_presets" in save_data:
            del save_data["ffmpeg_presets"]

        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False

def split_ffmpeg_options(options_str):
    """
    Splits ffmpeg options into input options (e.g., -hwaccel) and output options.
    """
    import shlex
    input_args = []
    output_args = []
    
    if not options_str:
        return input_args, output_args
        
    try:
        parts = shlex.split(options_str)
        i = 0
        while i < len(parts):
            arg = parts[i]
            # Input-related flags that should appear before -i
            if arg in ["-hwaccel", "-hwaccel_device", "-hwaccel_output_format", "-probesize", "-analyzeduration", "-fflags"]:
                input_args.append(arg)
                if i + 1 < len(parts):
                    input_args.append(parts[i+1])
                    i += 1
            else:
                output_args.append(arg)
            i += 1
    except:
        # Fallback to output if parsing fails
        output_args = shlex.split(options_str)
        
    return input_args, output_args
