import logging
logger = logging.getLogger(__name__)
import os
import subprocess

def convert_ts_to_mp4_and_delete(ts_path, options=None, delete_original=False):
    if not os.path.exists(ts_path): return

    mp4_path = os.path.splitext(ts_path)[0] + ".mp4"
    if os.path.exists(mp4_path):
        logger.info(f"MP4 already exists: {mp4_path}")
        if delete_original:
             logger.info(f"Deleting TS as requested: {ts_path}")
             try:
                os.remove(ts_path)
             except Exception as e:
                logger.error(f"Error deleting TS: {e}")
        return

    logger.info(f"Converting TS to MP4: {ts_path} -> {mp4_path}")
    logger.info(f"Options: {options}")
    
    try:
        try:
            from ..settings_manager import split_ffmpeg_options
        except (ImportError, ValueError):
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            from settings_manager import split_ffmpeg_options
            
        input_args, output_args = split_ffmpeg_options(options)

        cmd = ["ffmpeg", "-y"]
        if input_args: cmd.extend(input_args)
        cmd.extend(["-i", ts_path])
        if output_args: cmd.extend(output_args)
        else: cmd.extend(["-c", "copy"]) 
        cmd.append(mp4_path)
        
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0:
            logger.info("Conversion successful.")
            if delete_original:
                logger.info("Deleting TS file.")
                os.remove(ts_path)
        else:
            logger.info(f"FFmpeg failed with code {res.returncode}")
            logger.info(f"FFmpeg Error: {res.stderr.decode(errors='ignore')}")
    except Exception as e:
        logger.error(f"Error during conversion/deletion: {e}")

def is_file_closed(filepath):
    if os.name == 'nt':
        try:
            with open(filepath, 'a') as f:
                pass
            return True
        except PermissionError:
            return False
        except Exception as e:
            logger.error(f"Error checking file lock {filepath}: {e}")
            return False
    else:
        try:
            result = subprocess.run(
                ["lsof", filepath], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            if result.returncode == 0:
                return False
            else:
                return True
        except FileNotFoundError:
            logger.warning("Warning: 'lsof' command not found. Cannot detect file lock on Linux.")
            return True 
        except Exception as e:
            logger.error(f"Error checking file lock (lsof) {filepath}: {e}")
            return True
