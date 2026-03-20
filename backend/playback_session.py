import asyncio
import time
from .logger_config import get_logger
logger = get_logger(__name__, "app.log")

class PlaybackSession:
    def __init__(self, session_id, cmd, params, chunk_size=131072):
        self.session_id = session_id
        self.cmd = cmd
        self.params = params  # Store identifying params (filepath, start, end, etc.)
        self.chunk_size = chunk_size
        self.proc = None
        self.queue = asyncio.Queue(maxsize=400) # Increased buffer
        self.last_access = time.time()
        self.running = False
        self.eof = False
        self.read_task = None
        self.stderr_task = None
        self.lock = asyncio.Lock()
        self.clients_count = 0
        self.is_async_proc = False

    async def start(self):
        logger.info(f"Starting PlaybackSession: {self.session_id}")
        try:
            try:
                self.proc = await asyncio.create_subprocess_exec(
                    *self.cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                self.is_async_proc = True
                logger.info(f"FFmpeg started (async) for session {self.session_id}")
            except (NotImplementedError, AttributeError):
                import subprocess
                self.proc = await asyncio.to_thread(
                    subprocess.Popen, self.cmd, 
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL
                )
                self.is_async_proc = False
                logger.info(f"FFmpeg started (blocking fallback) for session {self.session_id}")
            
            self.running = True
            self.read_task = asyncio.create_task(self._read_stdout())
            self.stderr_task = asyncio.create_task(self._read_stderr())
        except Exception as e:
            logger.error(f"Failed to start FFmpeg for session {self.session_id}: {e}", exc_info=True)
            self.running = False
            self.eof = True

    async def _read_stdout(self):
        try:
            while self.running:
                if self.is_async_proc:
                    data = await self.proc.stdout.read(self.chunk_size)
                else:
                    data = await asyncio.to_thread(self.proc.stdout.read, self.chunk_size)
                
                if not data:
                    logger.info(f"FFmpeg stdout EOF for session {self.session_id}")
                    break
                # This will block if queue is full, effectively throttling FFmpeg
                await self.queue.put(data)
        except Exception as e:
            logger.error(f"Error reading FFmpeg stdout for session {self.session_id}: {e}")
        finally:
            self.eof = True
            self.running = False
            # Signal EOF to any waiting clients
            await self.queue.put(None)
            logger.info(f"PlaybackSession {self.session_id} read task finished (EOF reached)")

    async def _read_stderr(self):
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
        try:
            while self.running:
                if self.is_async_proc:
                    line = await self.proc.stderr.readline()
                else:
                    line = await asyncio.to_thread(self.proc.stderr.readline)
                
                if not line:
                    break
                msg = line.decode('utf-8', errors='replace').strip()
                if msg:
                    if not any(kw in msg for kw in ignore_keywords):
                        logger.debug(f"FFMPEG_STDERR ({self.session_id}): {msg}")
        except Exception:
            pass

    async def get_stream(self):
        """Yields data from the queue for a client."""
        async with self.lock:
            self.clients_count += 1
            self.last_access = time.time()
        
        try:
            while True:
                data = await self.queue.get()
                self.last_access = time.time()
                if data is None:
                    # EOF signal
                    # Put it back for other potential readers
                    await self.queue.put(None)
                    break
                yield data
        finally:
            async with self.lock:
                self.clients_count -= 1
            logger.debug(f"Client disconnected from session {self.session_id}. Remaining clients: {self.clients_count}")

    async def stop(self, graceful=True):
        logger.info(f"Stopping PlaybackSession: {self.session_id} (graceful={graceful})")
        self.running = False
        if self.proc:
            try:
                if graceful:
                    self.proc.terminate()
                    # Shorter wait for better response
                    for _ in range(3):
                        if self.proc.returncode is not None:
                            break
                        await asyncio.sleep(0.1)
                
                if self.proc.returncode is None:
                    self.proc.kill()
            except:
                pass
            
            # Close pipes
            for p_name in ['stdin', 'stdout', 'stderr']:
                p = getattr(self.proc, p_name, None)
                if p:
                    try: p.close()
                    except: pass

        if self.read_task:
            self.read_task.cancel()
        if self.stderr_task:
            self.stderr_task.cancel()

class PlaybackSessionManager:
    def __init__(self, timeout=60):
        self.sessions = {} # session_id -> PlaybackSession
        self.timeout = timeout
        self.lock = asyncio.Lock()
        self.cleanup_task = None

    def _start_cleanup_loop(self):
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(10)
            now = time.time()
            to_delete = []
            async with self.lock:
                for sid, session in self.sessions.items():
                    # If no clients are connected AND last access was long ago
                    if session.clients_count == 0 and (now - session.last_access) > self.timeout:
                        to_delete.append(sid)
            
            for sid in to_delete:
                logger.info(f"Session {sid} timed out. Cleaning up.")
                session = None
                async with self.lock:
                    session = self.sessions.pop(sid, None)
                if session:
                    await session.stop()

    async def get_or_create_session(self, session_id, cmd, params):
        self._start_cleanup_loop()
        
        async with self.lock:
            existing = self.sessions.get(session_id)
            if existing:
                # Check if params match (is it the same file, start position, etc?)
                if existing.params == params and existing.running:
                    logger.info(f"Reusing existing session: {session_id}")
                    return existing
                else:
                    # Params mismatch or session died, stop old one
                    logger.info(f"Session {session_id} params mismatch or not running. Replacing.")
                    # We will replace it below
            
            # If we reached here, we need a new session or to replace the old one
            new_session = PlaybackSession(session_id, cmd, params)
            
            old_session = self.sessions.get(session_id)
            self.sessions[session_id] = new_session
        
        if old_session:
            # During seek/replacement, stop the old one in background without blocking the new one
            asyncio.create_task(old_session.stop(graceful=False))
            
        await new_session.start()
        return new_session

playback_session_manager = PlaybackSessionManager()
