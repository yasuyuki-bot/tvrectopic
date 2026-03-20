import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

export const useCast = ({
    programId,
    internalStartTime,
    selectedAudio,
    audioMode,
    castMode,
    serverIp,
    program,
    duration,
    isNative,
    videoRef,
    lastKnownCastTimeRef,
    internalStartTimeRef,
    setInternalStartTime,
    setIsPlaying,
    setCurrentTime,
    setIsMuted
}) => {
    const [castSession, setCastSession] = useState(null);
    const [remotePlayer, setRemotePlayer] = useState(null);
    const [remotePlayerController, setRemotePlayerController] = useState(null);
    const [isCasting, setIsCasting] = useState(false);
    const lastLoadedUrlRef = useRef(null);

    // SDK constants helper
    const getSdk = useCallback(() => window.cast?.framework, []);

    const endSession = useCallback((stopMedia = true) => {
        const framework = getSdk();
        if (!framework) return;
        const ctx = framework.CastContext.getInstance();
        ctx.endCurrentSession(stopMedia);
    }, [getSdk]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            // Not ending session on unmount to allow multi-device/multi-app flow
        };
    }, []);

    // Initialization & Listeners
    useEffect(() => {
        const framework = getSdk();
        if (!framework) return;
        
        const ctx = framework.CastContext.getInstance();
        const player = new framework.RemotePlayer();
        const ctrl = new framework.RemotePlayerController(player);

        setRemotePlayer(player);
        setRemotePlayerController(ctrl);

        const sessionListener = (e) => {
            const sess = ctx.getCurrentSession();
            setCastSession(sess);
            
            const SessionState = framework.SessionState;
            const active = e.sessionState === SessionState.SESSION_STARTED || 
                           e.sessionState === SessionState.SESSION_RESUMED;

            if (active) {
                console.log("Cast Session Active. Syncing time...");
                const syncTime = lastKnownCastTimeRef.current;
                setInternalStartTime(syncTime);
                setIsCasting(true);
                setIsPlaying(false);
                if (videoRef.current) {
                    videoRef.current.pause();
                    videoRef.current.src = "";
                }
            } else if (e.sessionState === SessionState.SESSION_ENDED) {
                console.log("Cast Session Ended.");
                setInternalStartTime(lastKnownCastTimeRef.current);
                setIsCasting(false);
                setIsPlaying(false);
            }
        };

        const muteListener = () => { if (player.isConnected) setIsMuted(player.isMuted); };
        const playListener = () => { if (player.isConnected) setIsPlaying(!player.isPaused); };
        const timeListener = () => {
            if (player.isConnected) {
                // For Mp4 (Buffered), player.currentTime is the absolute time
                // For Live/Transcode, it's relative to the stream start
                let total;
                if (isNative) {
                    total = Math.min(player.currentTime, duration);
                } else {
                    total = Math.min(internalStartTimeRef.current + player.currentTime, duration);
                }
                setCurrentTime(total);
                lastKnownCastTimeRef.current = total;
            }
        };

        const playerStateListener = () => {
            if (!player.isConnected) return;
            // States: 'IDLE', 'PLAYING', 'PAUSED', 'BUFFERING'
            // Reasons: 'CANCELLED', 'INTERRUPTED', 'FINISHED', 'ERROR'
            console.log(`[Cast SDK] Player: ${player.playerState}, Reason: ${player.idleReason}`);
            
            if (player.playerState === 'IDLE' && (player.idleReason === 'FINISHED' || player.idleReason === 'CANCELLED')) {
                console.log("[Cast SDK] Content ended or cancelled. Closing session...");
                endSession(true);
            }
        };

        const sessionStateListener = (e) => {
            // e.sessionState: 'SESSION_STARTED', 'SESSION_ENDED', etc.
            if (e.sessionState === framework.SessionState.SESSION_ENDED) {
                console.log("[Cast SDK] Session ended event.");
                setIsCasting(false);
                setCastSession(null);
            }
        };

        const CastContextEventType = framework.CastContextEventType;
        const RemotePlayerEventType = framework.RemotePlayerEventType;

        ctx.addEventListener(CastContextEventType.SESSION_STATE_CHANGED, sessionListener);
        ctx.addEventListener(CastContextEventType.SESSION_STATE_CHANGED, sessionStateListener);
        ctrl.addEventListener(RemotePlayerEventType.IS_PAUSED_CHANGED, playListener);
        ctrl.addEventListener(RemotePlayerEventType.IS_MUTED_CHANGED, muteListener);
        ctrl.addEventListener(RemotePlayerEventType.CURRENT_TIME_CHANGED, timeListener);
        ctrl.addEventListener(RemotePlayerEventType.PLAYER_STATE_CHANGED, playerStateListener);

        // Check for existing session
        const currentSess = ctx.getCurrentSession();
        if (currentSess) {
            setCastSession(currentSess);
            setIsCasting(true);
        }

        return () => {
            ctx.removeEventListener(CastContextEventType.SESSION_STATE_CHANGED, sessionListener);
            ctx.removeEventListener(CastContextEventType.SESSION_STATE_CHANGED, sessionStateListener);
            ctrl.removeEventListener(RemotePlayerEventType.IS_PAUSED_CHANGED, playListener);
            ctrl.removeEventListener(RemotePlayerEventType.IS_MUTED_CHANGED, muteListener);
            ctrl.removeEventListener(RemotePlayerEventType.CURRENT_TIME_CHANGED, timeListener);
            ctrl.removeEventListener(RemotePlayerEventType.PLAYER_STATE_CHANGED, playerStateListener);
        };
    }, [duration, endSession, getSdk, setCurrentTime, setIsMuted, setIsPlaying, setInternalStartTime, isNative]);

    // Media Loading and Seeking
    useEffect(() => {
        if (!isCasting || !castSession || !program) return;

        const apiBase = `http://${serverIp}:8000`;
        const chromeCastMedia = window.chrome.cast.media;

        let url;
        if (isNative) {
            url = `${apiBase}/api/video/${programId}?cast=1`;
        } else {
            url = `${apiBase}/api/video/${programId}?start=${Math.floor(internalStartTime)}&audio=${selectedAudio}&pan=${audioMode}&format=mp4&cast=1`;
        }

        // Handle Seek vs Load
        if (isNative && lastLoadedUrlRef.current === url) {
            // If already loaded native MP4, perform a standard SEEK instead of reload
            const player = getSdk()?.framework.RemotePlayer;
            const ctrl = getSdk()?.framework.RemotePlayerController;
            if (player && ctrl && player.isConnected) {
                const diff = Math.abs(player.currentTime - internalStartTime);
                if (diff > 2) { // 2 seconds threshold
                    console.log(`[Cast SDK] Native Seek to: ${internalStartTime}`);
                    player.currentTime = internalStartTime;
                    ctrl.seek();
                }
            }
            return;
        }

        if (lastLoadedUrlRef.current === url) return; 
        lastLoadedUrlRef.current = url;
            
        const mi = new chromeCastMedia.MediaInfo(url, 'video/mp4');
        if (isNative) {
            mi.streamType = chromeCastMedia.StreamType.BUFFERED;
            mi.duration = duration;
            // Native MP4: Allow all commands including SEEK
        } else {
            mi.streamType = chromeCastMedia.StreamType.LIVE; 
            // Transcoded: Explicitly disable SEEK and FAST_FORWARD on the TV side
            // This tells the receiver/TV remote not to attempt seeking.
            // Commands bitmask: PAUSE=1, SEEK=2, VOLUME=4, MUTE=8
            // We only allow PAUSE, VOLUME, MUTE. (1 | 4 | 8 = 13)
            mi.supportedMediaCommands = 1 | 4 | 8;
        }

        mi.metadata = new chromeCastMedia.GenericMediaMetadata();
        mi.metadata.metadataType = chromeCastMedia.MetadataType.GENERIC;
        mi.metadata.title = program.title;
        mi.metadata.subtitle = program.description || "";
        if (program.image) mi.metadata.images = [{ url: program.image }];

        const req = new chromeCastMedia.LoadRequest(mi);
        req.autoplay = true;
        req.currentTime = isNative ? internalStartTime : 0;

        console.log(`[Cast SDK] loading media: ${url} (Native: ${isNative}, Type: ${mi.streamType}, Start: ${req.currentTime})`);
        castSession.loadMedia(req).catch(e => console.error("[Cast SDK] loadMedia error", e));

    }, [isCasting, castSession, programId, internalStartTime, selectedAudio, audioMode, serverIp, program, isNative, duration, getSdk]);

    return {
        isCasting,
        castSession,
        remotePlayer,
        remotePlayerController,
        endSession
    };
};
