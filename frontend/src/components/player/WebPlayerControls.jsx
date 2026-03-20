import React from 'react';
import { Play, Pause, RotateCcw, RotateCw, Volume2, VolumeX, Maximize, Minimize, Zap } from 'lucide-react';
import { formatTime } from '../../utils/time';

const WebPlayerControls = ({
    showControls,
    duration,
    currentTime,
    handleSeekChange,
    handleSeekCommit,
    handleSkip,
    togglePlay,
    isPlaying,
    toggleMute,
    isMuted,
    program,
    secondsAhead,
    audioMode,
    setAudioMode,
    selectedAudio,
    setSelectedAudio,
    toggleFullscreen,
    isFullscreen,
    setInternalStartTime,
    setForceReloadCount,
    lastKnownCastTimeRef,
    setIsBuffering
}) => {
    return (
        <div className={`absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/95 via-black/70 to-transparent px-3 md:px-6 py-4 md:py-6 transition-transform duration-300 z-30 ${showControls ? 'translate-y-0' : 'translate-y-full'}`} onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-4 mb-2 md:mb-4">
                <input type="range" min="0" max={duration} step="1" value={currentTime} onChange={handleSeekChange} onMouseUp={handleSeekCommit} onKeyUp={(e) => e.key === 'Enter' && handleSeekCommit()} onTouchEnd={handleSeekCommit} className="w-full h-1.5 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-blue-500 hover:h-2 transition-all" />
            </div>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-3 md:gap-3 w-full">
                {/* Group 1: Essential Playback */}
                <div className="flex items-center gap-2 md:gap-4 shrink-0 pr-2">
                    <button onClick={() => handleSkip(-10)} title="10秒戻る" className="relative group/skip text-white hover:text-blue-400 transition shrink-0 flex items-center justify-center p-1 md:p-2">
                        <RotateCcw className="w-6 h-6 md:w-7 md:h-7 opacity-70" />
                        <span className="absolute text-[9px] md:text-[11px] font-bold mt-0.5">10</span>
                    </button>
                    <button onClick={() => handleSkip(-5)} title="5秒戻る" className="relative group/skip text-white hover:text-blue-400 transition shrink-0 flex items-center justify-center p-1 md:p-2">
                        <RotateCcw className="w-7 h-7 md:w-8 md:h-8" />
                        <span className="absolute text-[10px] md:text-[11px] font-bold mt-0.5">5</span>
                    </button>
                    <button onClick={togglePlay} className="text-white hover:text-blue-400 transition shrink-0 mx-1 md:mx-2 p-1 md:p-2">
                        {isPlaying ? <Pause className="w-8 h-8 md:w-9 md:h-9 fill-current" /> : <Play className="w-8 h-8 md:w-9 md:h-9 fill-current" />}
                    </button>
                    <button onClick={() => handleSkip(5)} title="5秒進む" className="relative group/skip text-white hover:text-blue-400 transition shrink-0 flex items-center justify-center p-1 md:p-2">
                        <RotateCw className="w-7 h-7 md:w-8 md:h-8" />
                        <span className="absolute text-[10px] md:text-[11px] font-bold mt-0.5">5</span>
                    </button>
                    <button onClick={() => handleSkip(10)} title="10秒進む" className="relative group/skip text-white hover:text-blue-400 transition shrink-0 flex items-center justify-center p-1 md:p-2">
                        <RotateCw className="w-6 h-6 md:w-7 md:h-7 opacity-70" />
                        <span className="absolute text-[9px] md:text-[11px] font-bold mt-0.5">10</span>
                    </button>
                </div>

                <div className="flex items-center gap-2 md:gap-3 shrink-0">
                    <button onClick={toggleMute} className="text-white hover:text-gray-300 transition shrink-0">{isMuted ? <VolumeX className="w-4 h-4 md:w-5 md:h-5" /> : <Volume2 className="w-4 h-4 md:w-5 md:h-5" />}</button>
                    <div className="flex items-center gap-1 md:gap-2 text-[10px] md:text-sm font-mono text-gray-200 shrink-0">
                        <span className="tabular-nums">{formatTime(currentTime)}</span>
                        {!program?.is_live && (
                            <>
                                <span className="text-gray-600">/</span>
                                <span className="tabular-nums text-gray-400">{formatTime(duration)}</span>
                            </>
                        )}
                        {program?.is_live && (
                            <div className="flex items-center gap-1 px-1 py-0.5 bg-red-600/20 rounded border border-red-500/30">
                                <div className="w-1 h-1 rounded-full bg-red-500 animate-pulse"></div>
                                <span className="text-[8px] font-bold text-red-500 uppercase tracking-tighter">LIVE</span>
                            </div>
                        )}
                        {!program?.is_live && (
                            <div className={`flex items-center gap-0.5 md:gap-1 px-1 py-0.5 rounded text-[9px] md:text-[10px] font-bold transition-colors ${secondsAhead < 5 ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-blue-500/5 text-blue-400/60'}`}>
                                <Zap className={`w-2.5 h-2.5 md:w-3 md:h-3 ${secondsAhead < 5 ? 'animate-pulse' : ''}`} />
                                <span className="hidden sm:inline">{secondsAhead.toFixed(1)}s</span>
                                <span className="sm:hidden">{Math.round(secondsAhead)}s</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Group 3: Settings & Fullscreen */}
                <div className="flex items-center gap-1.5 md:gap-3 ml-auto shrink-0">
                    {/* Binaural/Dual-Mono */}
                    <div className="flex bg-gray-800/80 rounded-lg p-0.5 border border-gray-700/50">
                        <button onClick={() => {
                            setAudioMode('stereo');
                        }} className={`px-1.5 md:px-2 py-0.5 text-[9px] md:text-xs rounded transition-all ${audioMode === 'stereo' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-300'}`}>ST</button>
                        <button onClick={() => {
                            setAudioMode('left');
                        }} className={`px-1.5 md:px-2 py-0.5 text-[9px] md:text-xs rounded transition-all ${audioMode === 'left' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-300'}`}>L</button>
                        <button onClick={() => {
                            setAudioMode('right');
                        }} className={`px-1.5 md:px-2 py-0.5 text-[9px] md:text-xs rounded transition-all ${audioMode === 'right' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-300'}`}>R</button>
                    </div>

                    {/* Multi-Audio */}
                    {program && program.audio_tracks > 1 && (
                        <div className="flex bg-gray-800/80 rounded-lg p-0.5 border border-gray-700/50">
                            {[...Array(program.audio_tracks)].map((_, i) => (
                                <button key={i} onClick={() => {
                                    setSelectedAudio(i);
                                    setInternalStartTime(currentTime);
                                    setForceReloadCount(c => c + 1);
                                    setIsBuffering(true);
                                }} className={`px-1.5 md:px-2 py-0.5 text-[9px] md:text-xs rounded transition-all ${selectedAudio === i ? 'bg-green-600 text-white' : 'text-gray-500 hover:text-gray-300'}`}>{`音${i + 1}`}</button>
                            ))}
                        </div>
                    )}

                    <button onClick={toggleFullscreen} className="text-white hover:text-blue-400 transition p-1" title={isFullscreen ? "全画面解除" : "全画面表示"}>
                        {isFullscreen ? <Minimize className="w-5 h-5" /> : <Maximize className="w-5 h-5" />}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default WebPlayerControls;
