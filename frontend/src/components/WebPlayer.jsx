import React, { useEffect, useRef, useState } from 'react';
import mpegts from 'mpegts.js';
import axios from 'axios';
import { X, Play, AlertCircle, Tv } from 'lucide-react';
import TopicSidebar from './player/TopicSidebar';
import WebPlayerControls from './player/WebPlayerControls';
import { formatTime } from '../utils/time';
import { useVideoBuffer } from '../hooks/useVideoBuffer';

const WebPlayer = ({ programId, startTime = 0, initialTopics = null, settings, onClose, onPlayProgram }) => {
    const videoRef = useRef(null);
    const playerRef = useRef(null);
    const audioCtxRef = useRef(null);
    const sourceRef = useRef(null);
    const splitterRef = useRef(null);
    const mergerRef = useRef(null);
    const controlTimeoutRef = useRef(null);
    const playerContainerRef = useRef(null);
    const isMouseOverSidebarRef = useRef(false);
    const lastSavedResumeTimeRef = useRef(0);

    const [program, setProgram] = useState(null);
    const [currentTime, setCurrentTime] = useState(0); 
    const [duration, setDuration] = useState(3600);
    const [internalStartTime, _setInternalStartTime] = useState(startTime);
    
    const internalStartTimeRef = useRef(startTime);
    const lastKnownCastTimeRef = useRef(startTime);

    const setInternalStartTime = (val) => {
        _setInternalStartTime(prev => {
            const timeVal = typeof val === 'function' ? val(prev) : val;
            internalStartTimeRef.current = timeVal;
            return timeVal;
        });
    };

    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [forceReloadCount, setForceReloadCount] = useState(0);

    const [isPlaying, setIsPlaying] = useState(false);
    const [isBuffering, setIsBuffering] = useState(false);
    const [showControls, setShowControls] = useState(true);
    const [isSeeking, setIsSeeking] = useState(false);
    const [isMuted, setIsMuted] = useState(false);
    const [audioMode, setAudioMode] = useState('stereo');
    const [selectedAudio, setSelectedAudio] = useState(0);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [serverIp, setServerIp] = useState(window.location.hostname);
    const [sessionId] = useState(() => Math.random().toString(36).substring(2, 11));
    
    const wasControlsVisibleRef = useRef(true);

    const { secondsAhead } = useVideoBuffer(videoRef);
    const secondsAheadRef = useRef(0);
    
    const topics = program?.topics || [];
    const isNative = program?.video_format === 'mp4';

    useEffect(() => { secondsAheadRef.current = secondsAhead; }, [secondsAhead]);

    useEffect(() => {
        const fetchIp = async () => {
            try {
                const res = await axios.get(`http://${window.location.hostname}:8000/api/server-ip`);
                if (res.data && res.data.ip) setServerIp(res.data.ip);
            } catch (err) { console.error(err); }
        };
        fetchIp();
    }, []);

    useEffect(() => {
        if (!sessionId || program?.is_live) return;
        const reportStatus = async () => {
            try {
                const apiBase = `http://${serverIp}:8000`;
                await axios.post(`${apiBase}/api/video/status/${sessionId}`, { ahead: secondsAheadRef.current });
            } catch (err) {}
        };
        const interval = setInterval(reportStatus, 2000);
        return () => clearInterval(interval);
    }, [sessionId, serverIp, program?.is_live]);

    useEffect(() => {
        const fetchProgram = async () => {
            try {
                const apiBase = `http://${serverIp}:8000`;
                const res = await axios.get(`${apiBase}/api/programs/${programId}`);
                const parseTimeStr = (str) => {
                    if (typeof str === 'number') return str;
                    if (!str) return 0;
                    const parts = str.toString().split(':').map(Number);
                    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
                    if (parts.length === 2) return parts[0] * 60 + parts[1];
                    return parseFloat(str) || 0;
                };
                const rawTopics = initialTopics || res.data.topics;
                if (rawTopics) {
                    let parsedTopics = rawTopics.map(t => ({ ...t, start_time: parseTimeStr(t.start_time) }))
                        .sort((a, b) => initialTopics ? 0 : a.start_time - b.start_time);
                    if (!initialTopics && parsedTopics.length > 0 && parsedTopics[0].start_time > 5) {
                        parsedTopics.unshift({ id: 'opening-auto', title: 'Opening / 番組開始', start_time: 0 });
                    }
                    res.data.topics = parsedTopics;
                }
                setProgram(res.data); setIsLoading(false);
                if (res.data.is_live) setDuration(86400 * 7);
                else if (res.data.duration > 0) setDuration(res.data.duration);
            } catch (err) { setError("番組情報の取得に失敗しました"); setIsLoading(false); }
        };
        if (programId) { setProgram(null); setIsLoading(true); fetchProgram(); }
    }, [programId, initialTopics, serverIp]);

    useEffect(() => {
        if (programId && startTime !== 0) {
            setInternalStartTime(startTime); setForceReloadCount(prev => prev + 1);
        } else if (programId && settings?.video_resume_enabled && !initialTopics) {
            const savedTime = localStorage.getItem(`v_resume_${programId}`);
            if (savedTime) { setInternalStartTime(parseFloat(savedTime)); setForceReloadCount(prev => prev + 1); }
        }
    }, [programId, startTime, settings?.video_resume_enabled, initialTopics]);

    useEffect(() => {
        if (!program) return;
        const apiBase = `http://${serverIp}:8000`;
        const baseUrl = `${apiBase}/api/video/${programId}`;
        const commonQuery = `start=${internalStartTime}&audio=${selectedAudio}&session_id=${sessionId}`;
        const cleanup = () => {
            if (playerRef.current) {
                try { playerRef.current.unload(); playerRef.current.detachMediaElement(); playerRef.current.destroy(); } catch (e) {}
                playerRef.current = null;
            }
            if (videoRef.current) { videoRef.current.pause(); videoRef.current.removeAttribute('src'); videoRef.current.load(); }
        };
        setIsBuffering(true);
        if (isNative) {
            if (videoRef.current) {
                videoRef.current.src = `${baseUrl}?${commonQuery}&format=mp4`;
                videoRef.current.load();
                const onLoadedMetadata = () => {
                    if (videoRef.current && internalStartTime > 0) videoRef.current.currentTime = internalStartTime;
                    if (isPlaying) videoRef.current.play().catch(console.error);
                };
                videoRef.current.addEventListener('loadedmetadata', onLoadedMetadata, { once: true });
            }
        } else if (mpegts.isSupported()) {
            const player = mpegts.createPlayer({ type: 'mse', isLive: program.is_live || false, url: `${baseUrl}?${commonQuery}` }, { enableWorker: false, seekType: 'range' });
            player.attachMediaElement(videoRef.current);
            player.load(); playerRef.current = player;
        }
        return cleanup;
    }, [program, internalStartTime, selectedAudio, forceReloadCount]);

    const initAudioContext = () => {
        if (audioCtxRef.current || !videoRef.current) return;
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const source = ctx.createMediaElementSource(videoRef.current);
            const splitter = ctx.createChannelSplitter(2);
            const merger = ctx.createChannelMerger(2);
            source.connect(splitter); splitter.connect(merger, 0, 0); splitter.connect(merger, 1, 1); merger.connect(ctx.destination);
            audioCtxRef.current = ctx; splitterRef.current = splitter; mergerRef.current = merger;
            applyAudioMode(audioMode);
        } catch (e) { console.error(e); }
    };

    const applyAudioMode = (mode) => {
        if (!splitterRef.current || !mergerRef.current) return;
        const s = splitterRef.current; const m = mergerRef.current;
        s.disconnect();
        if (mode === 'left') { s.connect(m, 0, 0); s.connect(m, 0, 1); }
        else if (mode === 'right') { s.connect(m, 1, 0); s.connect(m, 1, 1); }
        else { s.connect(m, 0, 0); s.connect(m, 1, 1); }
    };

    useEffect(() => { applyAudioMode(audioMode); }, [audioMode]);

    const handleTimeUpdate = () => {
        if (videoRef.current && !isSeeking) {
            const current = videoRef.current.currentTime;
            const newTime = isNative ? current : (program?.is_live ? (internalStartTime + current) : Math.min(internalStartTime + current, duration));
            setCurrentTime(newTime); lastKnownCastTimeRef.current = newTime;
            if (settings?.video_resume_enabled && program && !program.is_live && newTime > 10 && newTime < duration - 10) {
                localStorage.setItem(`v_resume_${programId}`, newTime.toString());
            }
        }
    };

    const togglePlay = () => {
        if (!wasControlsVisibleRef.current) { resetControlTimer(); return; }
        if (videoRef.current) {
            if (isPlaying) { videoRef.current.pause(); setIsPlaying(false); }
            else { videoRef.current.play().catch(console.error); setIsPlaying(true); }
        }
    };

    const handleSeekChange = (e) => { setCurrentTime(parseFloat(e.target.value)); setIsSeeking(true); };
    const handleSeekCommit = () => {
        setIsSeeking(false);
        if (isNative) { if (videoRef.current) { videoRef.current.currentTime = currentTime; videoRef.current.play().catch(console.error); setIsPlaying(true); } }
        else { setInternalStartTime(currentTime); setForceReloadCount(c => c + 1); setIsBuffering(true); setIsPlaying(true); }
    };

    const handleSkip = (seconds) => {
        const newTime = Math.max(0, Math.min(currentTime + seconds, duration));
        setCurrentTime(newTime);
        if (isNative) { if (videoRef.current) videoRef.current.currentTime = newTime; }
        else { setInternalStartTime(newTime); setForceReloadCount(c => c + 1); setIsBuffering(true); setIsPlaying(true); }
    };

    const toggleMute = () => {
        if (videoRef.current) { videoRef.current.muted = !isMuted; setIsMuted(!isMuted); }
    };

    const resetControlTimer = () => {
        setShowControls(true);
        if (controlTimeoutRef.current) clearTimeout(controlTimeoutRef.current);
        controlTimeoutRef.current = setTimeout(() => { if (isPlaying && !isMouseOverSidebarRef.current) setShowControls(false); }, 3000);
    };

    useEffect(() => { if (isPlaying) resetControlTimer(); else setShowControls(true); }, [isPlaying]);

    const toggleFullscreen = () => {
        if (!playerContainerRef.current) return;
        if (!document.fullscreenElement) playerContainerRef.current.requestFullscreen().catch(console.error);
        else document.exitFullscreen();
    };

    useEffect(() => {
        const handleFS = () => setIsFullscreen(!!document.fullscreenElement);
        document.addEventListener('fullscreenchange', handleFS);
        return () => document.removeEventListener('fullscreenchange', handleFS);
    }, []);

    const startPlaybackWithAudio = () => {
        if (videoRef.current) {
            videoRef.current.play().then(() => { setIsPlaying(true); initAudioContext(); }).catch(console.error);
        }
    };

    if (error) return <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 text-white p-10"><AlertCircle className="w-10 h-10 text-red-500 mr-4" />{error}</div>;

    return (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black backdrop-blur-sm p-4 md:p-8">
            <div ref={playerContainerRef} className="relative w-full max-w-7xl h-[85vh] bg-gray-900 rounded-xl overflow-hidden shadow-2xl flex flex-col md:flex-row">
                <button onClick={() => {
                    if (program?.is_live) axios.post(`/api/stream/stop/${programId}`).catch(() => {});
                    onClose();
                }} className="absolute top-4 right-4 z-[60] p-2 bg-black/50 text-white rounded-full hover:bg-white/20 transition backdrop-blur-md"><X className="w-6 h-6" /></button>
                <div className="flex-1 bg-black flex items-center justify-center relative group/video overflow-hidden" onMouseMove={() => resetControlTimer()} onPointerDown={() => { wasControlsVisibleRef.current = showControls; }} onClick={togglePlay}>
                    {!isLoading && (
                        <video
                            ref={videoRef}
                            className="w-full h-full object-contain cursor-pointer"
                            autoPlay
                            crossOrigin="anonymous"
                            onTimeUpdate={handleTimeUpdate}
                            onPlay={() => {
                                setIsPlaying(true);
                                initAudioContext();
                            }}
                            onPause={() => setIsPlaying(false)}
                            onWaiting={() => setIsBuffering(true)}
                            onPlaying={() => {
                                setIsPlaying(true);
                                setIsBuffering(false);
                            }}
                            muted={isMuted}
                        />
                    )}
                    {isLoading && <div className="flex flex-col items-center gap-3"><div className="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div><span className="text-white text-sm font-bold">番組読み込み中...</span></div>}
                    {isBuffering && !isLoading && <div className="absolute inset-0 flex items-center justify-center bg-black/40 z-20 pointer-events-none"><div className="flex flex-col items-center gap-3"><div className="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div></div></div>}
                    {!isPlaying && !isLoading && (
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                            <div className="bg-black/40 p-6 rounded-full backdrop-blur-sm border border-white/10 cursor-pointer pointer-events-auto" onClick={(e) => { e.stopPropagation(); startPlaybackWithAudio(); }}>
                                <Play className="w-12 h-12 text-white fill-white" />
                            </div>
                        </div>
                    )}
                    {!isLoading && <WebPlayerControls showControls={showControls} duration={duration} currentTime={currentTime} handleSeekChange={handleSeekChange} handleSeekCommit={handleSeekCommit} handleSkip={handleSkip} togglePlay={togglePlay} isPlaying={isPlaying} toggleMute={toggleMute} isMuted={isMuted} program={program} secondsAhead={secondsAhead} audioMode={audioMode} setAudioMode={setAudioMode} selectedAudio={selectedAudio} setSelectedAudio={setSelectedAudio} toggleFullscreen={toggleFullscreen} isFullscreen={isFullscreen} setInternalStartTime={setInternalStartTime} setForceReloadCount={setForceReloadCount} lastKnownCastTimeRef={lastKnownCastTimeRef} setIsBuffering={setIsBuffering} />}
                </div>
                <TopicSidebar program={program} topics={topics} currentTime={currentTime} duration={duration} programId={programId} settings={settings} isLoading={isLoading} isNative={isNative} videoRef={videoRef} setIsPlaying={setIsPlaying} setCurrentTime={setCurrentTime} setInternalStartTime={setInternalStartTime} setForceReloadCount={setForceReloadCount} setIsBuffering={setIsBuffering} onPlayProgram={onPlayProgram} initialTopics={initialTopics} showControls={showControls} handleMouseMove={() => resetControlTimer()} resetControlTimer={resetControlTimer} isMouseOverSidebarRef={isMouseOverSidebarRef} formatTime={formatTime} />
            </div>
        </div>
    );
};

export default WebPlayer;
