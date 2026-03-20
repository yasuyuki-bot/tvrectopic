import os
import re
import subprocess
try:
    from ..logger_config import get_logger
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logger_config import get_logger

gemini_logger = get_logger("gemini_api", "gemini_api.log")

def extract_subtitles_srt(ts_file):
    base_dir = os.path.dirname(ts_file)
    filename_no_ext = os.path.splitext(os.path.basename(ts_file))[0]
    
    srt_dir = os.path.join(base_dir, "srt")
    final_srt_path = os.path.join(srt_dir, f"{filename_no_ext}.srt")
    
    if os.path.exists(final_srt_path):
        return final_srt_path

    if not os.path.exists(srt_dir):
        os.makedirs(srt_dir, exist_ok=True)

    # current_dir is backend/extract_modules
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # project_root is backend
    backend_dir = os.path.dirname(current_dir)
    # the actual project root is parent of backend (where cap/ tools/ etc reside)
    project_root = os.path.dirname(backend_dir)
    
    cap_exe = None
    if os.name == 'nt':
        win_specific_path = os.path.join(project_root, "cap", "Caption2AssC_x64.exe")
        if os.path.exists(win_specific_path):
             cap_exe = win_specific_path
        else:
             cap_exe = os.path.join(project_root, "cap", "Caption2AssC_x64.exe")
    else:
        cap_exe = os.path.join(project_root, "cap", "Caption2Ass")
    
    if cap_exe and os.path.exists(cap_exe):
        try:
            cmd = [cap_exe, "-format", "srt", ts_file]
            gemini_logger.info(f"Executing Caption2Ass: {' '.join(cmd)}")
            
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            generated_srt = os.path.splitext(ts_file)[0] + ".srt"
            
            if os.path.exists(generated_srt):
                import shutil
                import time
                
                max_retries = 3
                for i in range(max_retries):
                    try:
                        shutil.copy2(generated_srt, final_srt_path)
                        break
                    except PermissionError:
                        if i < max_retries - 1:
                            time.sleep(1)
                        else:
                            gemini_logger.error(f"Failed to copy SRT after retries: {generated_srt}")
                            raise
                
                if os.path.exists(generated_srt):
                    for i in range(max_retries):
                        try:
                            os.remove(generated_srt)
                            break
                        except:
                            time.sleep(1)
                            pass

                return final_srt_path
                
        except subprocess.CalledProcessError as e:
            gemini_logger.info(f"Caption2Ass failed: {e}")
            pass
        except Exception as e:
            gemini_logger.error(f"Error running Caption2Ass: {e}")

    return None

def get_transcript_text(file_path):
    if not file_path or not os.path.exists(file_path):
        return None
        
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        gemini_logger.error(f"Error reading subtitle file {file_path}: {e}")
        return None

    transcript_lines = []
    
    if ext == ".srt":
        current_time = ""
        for line in lines:
            line = line.strip()
            if " --> " in line:
                match = re.match(r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})", line)
                if match:
                    current_time = match.group(1).replace(",", ".")
            elif line and not line.isdigit():
                text = line
                text = text.replace('≫', '').strip()
                if text and current_time:
                    transcript_lines.append(f"[{current_time}] {text}")
                    current_time = ""
    
    elif ext == ".ass":
        for line in lines:
            if line.startswith("Dialogue:"):
                try:
                    parts = line.split(":", 1)[1].strip().split(",", 9)
                    if len(parts) < 10: continue
                    start_str = parts[1].strip()
                    text = parts[9].strip()
                    text = re.sub(r'\{.*?\}', '', text)
                    text = text.replace(r'\N', ' ').replace('\n', ' ').strip()
                    if text:
                        transcript_lines.append(f"[{start_str}] {text}")
                except:
                    continue
    
    if not transcript_lines:
        gemini_logger.warning(f"No transcript lines parsed from {file_path}")
        return None

    gemini_logger.info(f"Parsed {len(transcript_lines)} lines from {os.path.basename(file_path)}. Start: {transcript_lines[0]}")
    return "\n".join(transcript_lines)
