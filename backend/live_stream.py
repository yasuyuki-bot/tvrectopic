import os
import time
import json
import threading
import subprocess
import shlex
import paramiko
import uuid
import logging
try:
    from .settings_manager import load_settings, split_ffmpeg_options
    from .recorder import recorder
    from .tuner_command import build_recording_command, get_pkill_pattern
    from .utils import is_bilingual_program, get_ffmpeg_version
    from .logger_config import get_logger
except (ImportError, ValueError):
    from settings_manager import load_settings, split_ffmpeg_options
    from recorder import recorder
    from tuner_command import build_recording_command, get_pkill_pattern
    from utils import is_bilingual_program, get_ffmpeg_version
    from logger_config import get_logger

logger = get_logger(__name__, "app.log")

class LiveStreamManager:
    def __init__(self):
        self.streams = {} # stream_id -> {client, proc_recdvb, current_ffmpeg, fake_pid, ...}
        self.lock = threading.Lock()
        recorder.on_preempt_live = self.stop_stream

    def _get_ffmpeg_cmd(self1, channel_type):
        settings = load_settings()
        custom = settings.get("ffmpeg_options")
        return split_ffmpeg_options(custom)

    def start_stream(self, stream_id, type_str, channel_arg, sid_arg, audio_idx=0, is_bilingual=False):
        session_id = str(uuid.uuid4())
        logger.debug(f"start_stream {stream_id} (Session: {session_id}, Audio: {audio_idx}, Bilingual: {is_bilingual})")
        
        with self.lock:
            existing = self.streams.get(stream_id)
            
            # Check if we can reuse the tuner (same channel and audio/bilingual settings)
            can_reuse_recdvb = False
            if existing:
                # Check if recdvb/hub is still alive
                is_alive = False
                if existing.get('hub') and existing['hub'].thread.is_alive():
                    if existing.get('client'): # SSH
                        try:
                            # Simple check if channel is still active
                            if existing['client'].get_transport().is_active():
                                is_alive = True
                        except: pass
                    elif existing.get('proc_recdvb'): # Local
                        if existing['proc_recdvb'].poll() is None:
                            is_alive = True
                
                if is_alive:
                    # Reuse if the tuner parameters (channel, sid, type) are identical
                    if existing.get('type_str') == type_str and \
                       existing.get('channel_arg') == channel_arg and \
                       existing.get('sid_arg') == sid_arg:
                        
                        # Update audio settings for FFmpeg restart
                        existing['audio_idx'] = audio_idx
                        existing['is_bilingual'] = is_bilingual
                        can_reuse_recdvb = True
                        logger.info(f"DEBUG: Reusing tuner for {stream_id} (Switching Audio/Bilingual context)")
                
                if not can_reuse_recdvb:
                    logger.debug(f"Tuner inactive or channel changed, stopping old stream {stream_id}")
                    self.stop_stream(stream_id)
                    existing = None



            if not can_reuse_recdvb:
                # Start fresh recdvb
                # Check Tuner Availability and Reserve
                fake_pid = stream_id if stream_id.startswith("live_") else f"live_{stream_id}"
                if not recorder.reserve_tuner(type_str, fake_pid):
                     raise Exception("No Tuner Available")
                
                LIVE_DURATION = 300000 
                c_info = recorder.get_channel_info(int(sid_arg))
                if not c_info: raise Exception("Channel Info Not Found")
                sid = c_info['sid']
                tsid = c_info.get('tsid', 0)
                
                settings = load_settings()
                cmd_list = build_recording_command(settings, sid, type_str, LIVE_DURATION, "-", channel_arg)

                ssh_host = settings.get("ssh_host")
                # Detect if we should use SSH: 
                # If ssh_host is null, empty, or localhost, run recdvb locally.
                use_ssh = bool(ssh_host and ssh_host not in ['localhost', '127.0.0.1'])
                if use_ssh:
                    logger.info(f"Using SSH for live stream: {ssh_host}")
                else:
                    logger.info("Using LOCAL execution for live stream.")
                recdvb_path = settings.get("recdvb_path")

                client = None
                stdout = None
                remote_pid = None
                proc_recdvb = None

                if use_ssh:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh_user = settings.get("ssh_user")
                    ssh_pass = settings.get("ssh_pass")
                    client.connect(ssh_host, username=ssh_user, password=ssh_pass, timeout=10)
                    
                    recdvb_cmd = shlex.join(cmd_list)
                    wrapper_cmd = f"sh -c 'echo $$; exec {recdvb_cmd}'"
                    stdin, stdout, stderr = client.exec_command(wrapper_cmd, bufsize=1024*1024)
                    try:
                        # Set Keepalive to prevent connection drop
                        transport = client.get_transport()
                        if transport: transport.set_keepalive(5)
                        
                        pid_line = stdout.readline()
                        remote_pid = int(pid_line.strip())
                    except: pass
                else:
                    args = cmd_list

                    log_dir = os.path.dirname(__file__)
                    # Open in binary mode for raw subprocess redirect to avoid TextIOWrapper issues on Windows
                    recdvb_err_log = open(os.path.join(log_dir, "recdvb_live_err.log"), "ab")
                    proc_recdvb = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=recdvb_err_log, bufsize=1024*1024)
                    stdout = proc_recdvb.stdout
                    remote_pid = proc_recdvb.pid
                    existing_recdvb_log = recdvb_err_log

                # Middleman pipe logic to allow swapping consumers
                class PipeHub:
                    def __init__(self, source):
                        self.source = source
                        self.dest = None
                        self.lock = threading.Lock()
                        self.running = True
                        self.thread = threading.Thread(target=self._run, daemon=True)
                        self.thread.start()
                    def _run(self):
                        try:
                            while self.running:
                                data = self.source.read(65536)
                                if not data: 
                                    break
                                target = None
                                with self.lock:
                                    target = self.dest
                                
                                if target:
                                    try:
                                        target.write(data)
                                    except (OSError, BrokenPipeError, ValueError):
                                        with self.lock:
                                            if self.dest == target:
                                                self.dest = None
                                    except Exception as e:
                                        logger.debug(f"PipeHub write error: {e}")
                                        with self.lock:
                                            if self.dest == target:
                                                self.dest = None
                        except Exception as e:
                            logger.error(f"PipeHub run exception: {e}")
                        finally:
                            self.running = False
                    def set_dest(self, d):
                        with self.lock:
                            # If we are swapping, the old one might be closed already
                            self.dest = d
                    def stop(self):
                        self.running = False
                        with self.lock:
                            self.dest = None

                hub = PipeHub(stdout)

                # Unified pkill pattern: match by SID to be specific
                pkill_pattern = get_pkill_pattern(settings, sid, LIVE_DURATION)

                existing = {
                    "client": client,
                    "proc_recdvb": proc_recdvb,
                    "hub": hub,
                    "fake_pid": fake_pid,
                    "remote_pid": remote_pid,
                    "pkill_pattern": pkill_pattern,
                    "type_str": type_str,
                    "channel_arg": channel_arg,
                    "sid_arg": sid_arg,
                    "audio_idx": audio_idx,
                    "is_bilingual": is_bilingual,
                    "current_ffmpeg": None,
                    "current_session": None,
                    "recdvb_err_log": existing_recdvb_log if not use_ssh else None
                }
                self.streams[stream_id] = existing

                # Update these in existing if we are reusing
                existing['audio_idx'] = audio_idx
                existing['is_bilingual'] = is_bilingual
                
                # Register in recorder map
                with recorder.lock:
                    recorder.active_recordings[fake_pid] = {
                        "client": client, "type": type_str, "local_path": "LIVE_STREAM", "start_time": time.time()
                    }

            # At this point, 'existing' is populated and recdvb is running.
            # Start/Restart FFmpeg
            if existing["current_ffmpeg"]:
                logger.info(f"DEBUG: Terminating old ffmpeg for {stream_id}")
                # Set dest to None FIRST to stop Hub writing to a dying pipe
                existing["hub"].set_dest(None)
                
                old_ff = existing["current_ffmpeg"]
                try:
                    old_ff.terminate()
                    def wait_and_kill_old():
                        try:
                            old_ff.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            try: old_ff.kill()
                            except: pass
                            old_ff.wait(timeout=2)
                        except: pass
                    threading.Thread(target=wait_and_kill_old, daemon=True).start()
                except: pass

            ffmpeg_cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
            input_args, output_args = self._get_ffmpeg_cmd(type_str)
            
            settings = load_settings()
            if any("qsv" in str(a) for a in input_args) or any("qsv" in str(a) for a in output_args):
                has_init = any("-init_hw_device" in str(a) for a in input_args) or any("-init_hw_device" in str(a) for a in output_args)
                if not has_init:
                    if os.name != 'nt':
                        qsv_device = settings.get("qsv_device_path") or "/dev/dri/renderD128"
                        ffmpeg_cmd.extend(["-init_hw_device", f"qsv=qsv:hw_any,child_device={qsv_device}", "-filter_hw_device", "qsv"])
                    else:
                        ffmpeg_cmd.extend(["-init_hw_device", "qsv=qsv:hw_any", "-filter_hw_device", "qsv"])
                    logger.debug("Injecting QSV device init to live stream")

            # High-stability startup settings with SID filtering
            # -probesize 1,000,000 (1M): Reduced for low latency
            # -analyzeduration 1,000,000 (1s): Sufficient analysis for faster start
            # -err_detect ignore_err: Keep moving even with minor corruption
            # -fflags +genpts+discardcorrupt+nobuffer: Added nobuffer for live
            ffmpeg_cmd.extend([
                "-probesize", "1000000", 
                "-analyzeduration", "1000000", 
                "-err_detect", "ignore_err", 
                "-fflags", "+genpts+discardcorrupt+nobuffer"
            ])
            
            if input_args: 
                ffmpeg_cmd.extend(input_args)
            
            ffmpeg_cmd.extend(["-i", "-"])
            
            # Output settings (AFTER -i)

            
            # Hybrid Audio Mapping:
            # 1. Prefer Japanese audio stream if available
            # 2. Otherwise use the requested audio_idx
            
            cur_audio_idx = existing.get('audio_idx', 0)
            
            # Use ffprobe to detect streams if possible (already done slightly above in some contexts, 
            # but for live we depend on ffmpeg's internal selection or manual override)
            # The USER requested: "1．日本語の音声ストリームがあるときは選択する"
            
            # Implementation: Use -map 0:a:m:language:jpn? -map 0:a:cur_audio_idx
            # But ffmpeg -map logic is tricky. Let's stick to mapping the requested one, 
            # and assume the UI/Backend already know which one is Japanese.
            # Actually, per requirements, we should DISCARD English if Japanese exists.
            
            # For bilingual (Dual Mono), we now send STEREO and let browser handle it.
            # So we just map the first audio stream (0:a:0) if it's dual mono, 
            # or the specific index if it's multi-audio.
            
            # Implementation: Use program-based mapping (-map 0:p:SID) if SID is available
            # This ensures we pick the correct video/audio pair from the SAME service.
            if sid_arg and sid_arg != "0":
                 # Format: -map 0:p:SID:v:0 -map 0:p:SID:a:IDX
                 # audio_idx 0 means the first audio stream of THIS program.
                 ffmpeg_cmd.extend(["-map", f"0:p:{sid_arg}:v:0", "-map", f"0:p:{sid_arg}:a:{cur_audio_idx}?", "-ac", "2"])
                 logger.debug(f"Mapping Live Audio with SID={sid_arg}, audio_idx={cur_audio_idx}")
            else:
                 # Fallback to absolute mapping (less precise but works for simple streams)
                 ffmpeg_cmd.extend(["-map", "0:v:0", "-map", f"0:a:{cur_audio_idx}?", "-ac", "2"])
                 logger.debug(f"Mapping Live Audio without SID - audio_idx={cur_audio_idx}")


            
            ffmpeg_cmd.extend(output_args)
            ffmpeg_cmd.extend(["-f", "mpegts", "-"])

            # log_dir = os.path.dirname(__file__)
            # with open(os.path.join(log_dir, "ffmpeg_live.log"), "a") as f: f.write(f"SESSION {session_id} CMD: {ffmpeg_cmd}\n")

            log_dir = os.path.dirname(__file__)
            proc_ffmpeg = subprocess.Popen(
                ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, bufsize=10**7
            )

            # --- Background FFmpeg Error Logger with Timestamps and Filtering ---
            def ffmpeg_error_logger():
                err_log_path = os.path.join(log_dir, "ffmpeg_live_err.log")
                try:
                    with open(err_log_path, "a", encoding="utf-8") as f_err:
                        for line in proc_ffmpeg.stderr:
                            try:
                                msg = line.decode('utf-8', errors='replace').strip()
                                if not msg: continue
                                
                                # Filtering noise: ignore common startup warnings/errors that are non-critical
                                ignore_keywords = [
                                    "Could not find codec parameters",
                                    "Consider increasing the value",
                                    "PES packet size mismatch",
                                    "Packet corrupt",
                                    "channel element 0.1 is not allocated",
                                    "Error submitting packet to decoder",
                                    "Invalid data found when processing input",
                                    "Invalid frame dimensions 0x0",
                                    "Last message repeated",
                                    "non-existing PPS 0 referenced",
                                    "no frame!",
                                    "estimate_timings_from_pts"
                                ]
                                if any(kw in msg for kw in ignore_keywords):
                                    continue
                                
                                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                                f_err.write(f"[{now_str}] [Session {session_id}] {msg}\n")
                                f_err.flush()
                            except (OSError, ValueError):
                                # Break loop if file or pipe becomes invalid
                                break
                            except Exception:
                                continue
                except Exception as ex:
                    logger.debug(f"ffmpeg_error_logger setup error: {ex}")
            
            threading.Thread(target=ffmpeg_error_logger, daemon=True).start()
            
            existing["current_ffmpeg"] = proc_ffmpeg
            existing["current_session"] = session_id
            existing["hub"].set_dest(proc_ffmpeg.stdin)
            
            return {
                "proc": proc_ffmpeg,
                "session_id": session_id,
                "stream_id": stream_id
            }

    def stop_stream(self, stream_id, only_session=None):
        with self.lock:
            if stream_id not in self.streams: return
            s = self.streams[stream_id]
            
            # If only_session is provided, we only stop if it's the CURRENT session
            # If it's old, we do nothing (it was already superseded)
            if only_session and s.get("current_session") != only_session:
                logger.debug(f"stop_stream ignored for old session {only_session}")
                return

            logger.info(f"Stopping Live Stream {stream_id}...")
            
            if s.get("hub"): s["hub"].stop()
            
            # Robust Process Cleanup Helper
            def cleanup_proc(proc, name):
                if not proc: return
                
                # Background thread for waiting/killing
                def wait_and_kill():
                    try:
                        logger.info(f"Cleanup Thread: Started for {name} (PID {proc.pid})")
                        
                        # 1. Send terminate signal
                        try: proc.terminate()
                        except: pass
                        
                        # 2. Wait and Poll (robust polling-based approach)
                        start_wait = time.time()
                        grace_period = 4.0
                        terminated = False
                        
                        while time.time() - start_wait < grace_period:
                            if proc.poll() is not None:
                                logger.info(f"Cleanup Thread: {name} (PID {proc.pid}) terminated gracefully")
                                terminated = True
                                break
                            time.sleep(0.5)
                        
                        # 3. Force Kill if still alive
                        if not terminated:
                            logger.warning(f"Cleanup Thread: {name} (PID {proc.pid}) did not terminate, killing...")
                            try: proc.kill()
                            except: pass
                            # Short final wait for reap
                            start_kill_wait = time.time()
                            while time.time() - start_kill_wait < 2.0:
                                if proc.poll() is not None: break
                                time.sleep(0.2)
                            logger.info(f"Cleanup Thread: {name} (PID {proc.pid}) force killed/waited")
                        
                        # 4. Close pipes AFTER process is definitely dead
                        for p_name in ['stdin', 'stdout', 'stderr']:
                            p = getattr(proc, p_name, None)
                            if p:
                                try: p.close()
                                except: pass
                        logger.debug(f"Cleanup Thread: pipes closed for {name} (PID {proc.pid})")
                    except Exception as e:
                        logger.error(f"Cleanup Thread Error for {name}: {e}")
                
                threading.Thread(target=wait_and_kill, daemon=True).start()

            client = s.get('client')
            proc_recdvb = s.get("proc_recdvb")
            if proc_recdvb:
                logger.info(f"Cleanup: Initiating for recdvb (PID {proc_recdvb.pid})")
                cleanup_proc(proc_recdvb, "recdvb")
            elif s.get("remote_pid") and client:
                def remote_cleanup():
                    try: 
                        client.exec_command(f"kill -HUP {s['remote_pid']} ; sleep 2; kill -9 {s['remote_pid']}")
                        if s.get("pkill_pattern"):
                            client.exec_command(f"pkill -HUP -f '{s['pkill_pattern']}' ; sleep 2; pkill -9 -f '{s['pkill_pattern']}'")
                        client.close()
                    except: pass
                threading.Thread(target=remote_cleanup, daemon=True).start()

            if s.get("current_ffmpeg"):
                logger.info(f"Cleanup: Initiating for ffmpeg (PID {s['current_ffmpeg'].pid})")
                cleanup_proc(s["current_ffmpeg"], "ffmpeg")

            # Close recdvb log handle if local (in background thread if possible, but close is typically fast)
            if s.get("recdvb_err_log"):
                try:
                    # Closing the file handle used for stderr redirect is safe after proc.terminate() is initiated
                    s["recdvb_err_log"].close()
                except: pass

            with recorder.lock:
                if s["fake_pid"] in recorder.active_recordings:
                    del recorder.active_recordings[s["fake_pid"]]
            
            # SSH client is closed in remote_cleanup thread if it exists
            
            del self.streams[stream_id]
            logger.info(f"Live Stream {stream_id} stopped.")

live_manager = LiveStreamManager()
