import React from 'react';
import { Clock, Play } from 'lucide-react';

const TopicSidebar = ({
    program,
    topics,
    currentTime,
    duration,
    programId,
    settings,
    isLoading,
    isNative,
    videoRef,
    setIsPlaying,
    setCurrentTime,
    setInternalStartTime,
    setForceReloadCount,
    setIsBuffering,
    onPlayProgram,
    initialTopics,
    showControls,
    handleMouseMove,
    resetControlTimer,
    isMouseOverSidebarRef,
    formatTime
}) => {
    if (program?.is_live || topics.length === 0) return null;

    return (
        <div
            className={`bg-gray-800 flex flex-col z-20 transition-all duration-300 overflow-hidden ${showControls
                ? 'w-full md:w-80 h-1/2 md:h-full opacity-100 border-l border-gray-700'
                : 'w-0 h-0 md:w-0 md:h-full md:max-w-0 opacity-0 border-l-0'
                }`}
            onMouseMove={handleMouseMove}
            onTouchStart={resetControlTimer}
            onTouchMove={resetControlTimer}
            onMouseEnter={() => { if (isMouseOverSidebarRef) isMouseOverSidebarRef.current = true; resetControlTimer(); }}
            onMouseLeave={() => { if (isMouseOverSidebarRef) isMouseOverSidebarRef.current = false; resetControlTimer(); }}
        >
            <div className="p-4 border-b border-gray-700 bg-gray-800 shrink-0">
                <h2 className="font-bold text-white text-lg truncate" title={program?.title || ""}>{program?.title || "読み込み中..."}</h2>
                <div className="hidden md:flex text-sm text-gray-400 mt-1 items-center gap-2">
                    <Clock className="w-4 h-4" />
                    {formatTime(currentTime)}
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {topics.map((t, i) => {
                    const offset = settings?.topic_offset_sec || 0;
                    const topicProgramId = t.program_id || programId;
                    const isSameProgram = topicProgramId === programId;

                    let isActive = false;
                    if (isSameProgram && !isLoading) {
                        const myProgTopics = topics.filter(tp => (tp.program_id || programId) === programId);
                        const myIdx = myProgTopics.findIndex(x => x === t);
                        if (myIdx !== -1) {
                            const myNext = myProgTopics[myIdx + 1];
                            const nextStart = myNext ? myNext.start_time : duration;
                            isActive = currentTime >= (t.start_time + offset - 0.5) && currentTime < (nextStart + offset - 0.5);
                        }
                    }

                    return (
                        <div key={t.id || i} onClick={() => {
                            const targetProgramId = t.program_id || programId;
                            if (targetProgramId !== programId) {
                                if (onPlayProgram) onPlayProgram(targetProgramId, t.start_time, initialTopics);
                            } else {
                                let targetTime = Math.max(0, t.start_time + offset);
                                setCurrentTime(targetTime);
                                if (isNative) {
                                    if (videoRef.current) {
                                        videoRef.current.currentTime = targetTime;
                                        videoRef.current.play().catch(console.error);
                                        setIsPlaying(true);
                                    }
                                } else {
                                    setInternalStartTime(targetTime);
                                    setForceReloadCount(prev => prev + 1);
                                    setIsBuffering(true);
                                    setIsPlaying(true);
                                }
                            }
                        }} className={`p-3 rounded-lg cursor-pointer transition flex gap-3 items-start group ${isActive ? 'bg-blue-600/90 text-white shadow-lg' : (isSameProgram ? 'text-gray-300 hover:bg-gray-700' : 'text-gray-500 hover:bg-gray-800 italic')}`}>
                            <div className={`mt-0.5 ${isActive ? 'text-blue-200' : 'text-gray-500 group-hover:text-gray-400'}`}>
                                <Play className="w-4 h-4 fill-current" />
                            </div>
                            <div>
                                <div className="text-xs opacity-70 mb-0.5 font-mono">{formatTime(t.start_time)}</div>
                                <div className="text-sm font-medium leading-tight">{t.title}</div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default TopicSidebar;
