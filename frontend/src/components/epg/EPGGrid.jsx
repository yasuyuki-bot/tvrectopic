import React, { memo } from 'react';
import { format } from 'date-fns';
import { Loader, Clock, MonitorPlay, AlertCircle, Play } from 'lucide-react';

const HOUR_HEIGHT = 180;

const GENRE_COLORS = {
    "ニュース／報道": "bg-blue-100 border-blue-200 text-blue-900 hover:bg-blue-200 hover:border-blue-400",
    "スポーツ": "bg-green-100 border-green-200 text-green-900 hover:bg-green-200 hover:border-green-400",
    "情報／ワイドショー": "bg-purple-100 border-purple-200 text-purple-900 hover:bg-purple-200 hover:border-purple-400",
    "ドラマ": "bg-rose-100 border-rose-200 text-rose-900 hover:bg-rose-200 hover:border-rose-400",
    "音楽": "bg-orange-100 border-orange-200 text-orange-900 hover:bg-orange-200 hover:border-orange-400",
    "バラエティ": "bg-yellow-100 border-yellow-200 text-yellow-900 hover:bg-yellow-200 hover:border-yellow-400",
    "映画": "bg-teal-100 border-teal-200 text-teal-900 hover:bg-teal-200 hover:border-teal-400",
    "アニメ／特撮": "bg-pink-100 border-pink-200 text-pink-900 hover:bg-pink-200 hover:border-pink-400",
    "ドキュメンタリー／教養": "bg-gray-100 border-gray-300 text-gray-900 hover:bg-gray-200 hover:border-gray-500",
    "趣味／教育": "bg-lime-100 border-lime-200 text-lime-900 hover:bg-lime-200 hover:border-lime-400",
    "福祉": "bg-cyan-100 border-cyan-200 text-cyan-900 hover:bg-cyan-200 hover:border-cyan-400",
    "default": "bg-white border-gray-200 text-gray-900 hover:bg-gray-50 hover:border-gray-400"
};

const ProgramCell = memo(({
    program,
    baseTime,
    requestMap,
    recordedMap,
    recordedPrograms,
    reservations,
    defaultRecordingFolder,
    setRecordingFolder,
    setSelectedProgram,
    fontConfig
}) => {
    const startTime = program.start_time_dt;
    const endTime = program.end_time_dt;
    const durationSec = (endTime.getTime() - startTime.getTime()) / 1000;

    // Position calculation
    const diff = (startTime.getTime() - baseTime.getTime()) / 1000 / 3600;
    const top = diff * HOUR_HEIGHT;
    const height = (durationSec / 3600) * HOUR_HEIGHT;

    const visibleTop = Math.max(0, top);
    const hiddenTop = visibleTop - top;
    const visibleHeight = Math.min(height - hiddenTop, 4320 - visibleTop);

    if (visibleHeight <= 0) return null;

    const genreClass = GENRE_COLORS[program.genre_major] || GENRE_COLORS.default;

    // Lookup reservation
    let res = requestMap.get(program.id);
    if (!res) {
        res = requestMap.get(`${program.service_id}-${startTime.getTime()}`);
    }

    // Lookup recorded
    let recorded = recordedMap.get(`${program.event_id}-${program.service_id}`);
    if (!recorded) {
        recorded = recordedPrograms.find(r => {
            if (r.event_id && program.event_id && r.event_id !== program.event_id) return false;
            if (r.service_id && program.service_id && r.service_id === program.service_id) {
                const t1 = new Date(r.start_time).getTime();
                const t2 = startTime.getTime();
                return Math.abs(t1 - t2) < 120000;
            }
            return false;
        });
    }

    const isAuto = res && res.auto_reservation_id;
    const statusColor = res
        ? (res.status === 'recording'
            ? 'bg-red-500/10 border-red-500 ring-1 ring-inset ring-red-500'
            : (res.status === 'skipped'
                ? 'bg-orange-500/10 border-orange-500 ring-1 ring-inset ring-orange-500'
                : (isAuto
                    ? 'bg-purple-500/10 border-purple-500 ring-1 ring-inset ring-purple-500'
                    : 'bg-blue-500/10 border-blue-500 ring-1 ring-inset ring-blue-500')))
        : (recorded ? 'bg-green-500/10 border-green-500 ring-1 ring-inset ring-green-500' : '');

    const handleClick = () => {
        const activeRes = reservations.find(r =>
            (r.program_id === program.id) ||
            (r.service_id === program.service_id &&
                new Date(r.start_time).getTime() === startTime.getTime())
        );
        const uniqueRecorded = recordedPrograms.find(r => {
            if (r.event_id && r.service_id && program.event_id && program.service_id) {
                if (r.event_id === program.event_id && r.service_id === program.service_id) return true;
                if (r.event_id !== program.event_id) return false;
            }
            if (r.service_id && program.service_id && r.service_id === program.service_id) {
                const t1 = new Date(r.start_time).getTime();
                const t2 = startTime.getTime();
                return Math.abs(t1 - t2) < 120000;
            }
            return false;
        });

        setRecordingFolder(activeRes?.recording_folder || defaultRecordingFolder);
        setSelectedProgram({ program, reservation: activeRes, recorded: uniqueRecorded });
    };

    return (
        <div
            onClick={handleClick}
            className={`absolute w-[95%] left-[2.5%] rounded border transition overflow-hidden cursor-pointer group p-1 shadow-sm z-0 hover:z-40 hover:shadow-md ${genreClass} ${statusColor} ${fontConfig.base}`}
            style={{ top: `${visibleTop}px`, height: `${visibleHeight}px` }}
            title={`${program.title}\n${format(startTime, 'HH:mm')} - ${format(endTime, 'HH:mm')}\n${program.description}`}
        >
            {res && (
                <div
                    className={`absolute top-0 right-0 p-0.5 rounded-bl shadow-sm z-10 ${res.status === 'recording'
                        ? 'bg-red-500 text-white'
                        : (res.status === 'skipped'
                            ? 'bg-orange-500 text-white'
                            : (res.auto_reservation_id ? 'bg-purple-600 text-white' : 'bg-blue-500 text-white'))}`}
                    title={res.status === 'skipped' ? (res.skip_reason === 'conflict' ? "チューナー不足のためスキップされました" : "同一番組が重複しているためスキップされました") : ""}
                >
                    {res.status === 'skipped' ? <AlertCircle className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
                </div>
            )}
            {recorded && !res && (
                <div className="absolute top-0 right-0 p-0.5 rounded-bl shadow-sm z-10 bg-green-500 text-white">
                    <MonitorPlay className="w-3 h-3" />
                </div>
            )}
            <div className={`${fontConfig.title} font-bold line-clamp-1 group-hover:line-clamp-none leading-snug break-all`}>
                {program.title}
            </div>
            <div className={`${fontConfig.meta} opacity-75 font-mono`}>
                {format(startTime, 'HH:mm')}
            </div>
            {height > 40 && (
                <div className={`${fontConfig.meta} opacity-75 mt-1 line-clamp-2 leading-tight group-hover:block break-all`}>
                    {program.description}
                </div>
            )}
        </div>
    );
});

const EPGGrid = ({
    loading,
    isToday,
    currentTimeTop,
    displayChannels,
    programsByServiceId,
    programsByChannel,
    requestMap,
    recordedMap,
    reservations,
    recordedPrograms,
    defaultRecordingFolder,
    setRecordingFolder,
    setSelectedProgram,
    onPlay,
    fontConfig,
    scrollContainerRef,
    baseTime
}) => {
    return (
        <div className="flex-1 overflow-auto relative bg-white" ref={scrollContainerRef}>
            {loading ? (
                <div className="flex h-full items-center justify-center">
                    <Loader className="w-8 h-8 animate-spin text-blue-600" />
                </div>
            ) : (
                <div className="flex min-w-max relative">
                    {/* Time Column */}
                    <div className="sticky left-0 w-10 md:w-16 bg-gray-50 z-[60] border-r border-gray-200">
                        <div className="h-10 border-b border-gray-200 bg-gray-100 sticky top-0 z-[70] shadow-sm"></div>
                        {[...Array(24)].map((_, i) => (
                            <div key={i} className="h-[180px] border-b border-gray-200 flex items-start justify-center">
                                <div className="text-[10px] md:text-xs font-bold text-gray-400 p-0.5 md:p-1">{i}時</div>
                            </div>
                        ))}
                    </div>

                    {/* Current Time Line */}
                    {isToday && (
                        <div
                            className="absolute left-0 w-full border-t-2 border-red-500 z-30 pointer-events-none"
                            style={{ top: currentTimeTop + 40 }}
                        >
                            <div className="absolute -left-1 -top-1.5 w-3 h-3 bg-red-500 rounded-full"></div>
                            <div className="absolute left-16 -top-2.5 bg-red-500 text-white text-[10px] px-1 rounded font-mono">
                                {format(new Date(), 'HH:mm')}
                            </div>
                        </div>
                    )}

                    {displayChannels.length === 0 ? (
                        <div className="p-10 text-gray-500">チャンネル設定がありません</div>
                    ) : (
                        displayChannels.map(ch => {
                            let channelPrograms = [];
                            if (ch.service_id) {
                                const candidates = programsByServiceId[ch.service_id] || [];
                                channelPrograms = candidates.filter(p => {
                                    const chNid = ch.network_id || ch.onid;
                                    const nidMatch = (chNid && p.network_id) ? p.network_id === chNid : true;
                                    const chMatch = ch.type === 'GR' ? p.channel === ch.channel : true;
                                    return nidMatch && chMatch;
                                });
                            } else {
                                channelPrograms = programsByChannel[ch.channel] || [];
                            }

                            return (
                                <div key={`${ch.channel}-${ch.service_id}`} className="w-32 md:w-48 border-r border-gray-200 relative bg-gray-50/30">
                                    {/* Header */}
                                    <div className="h-10 px-1 border-b border-gray-200 bg-gray-100 sticky top-0 z-[50] flex flex-col items-center justify-center overflow-hidden relative group">
                                        <span className="text-[10px] md:text-sm font-bold text-gray-700 whitespace-nowrap">
                                            {ch.name}
                                        </span>
                                        {ch.service_id && (
                                            <span className="text-[8px] md:text-[10px] text-gray-500 font-mono leading-none">
                                                SID: {ch.service_id}
                                            </span>
                                        )}
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                const id = ch.type === 'GR'
                                                    ? `live_GR_${ch.channel}_${ch.service_id}`
                                                    : `live_${ch.type}_0_${ch.service_id}`;
                                                onPlay(id);
                                            }}
                                            className="absolute right-0.5 md:right-1 top-1/2 -translate-y-1/2 text-gray-400 hover:text-blue-600 transition"
                                            title="現在放送を視聴"
                                        >
                                            <Play className="w-3 h-3 md:w-4 md:h-4 fill-current" />
                                        </button>
                                    </div>

                                    {/* Program Cells Container */}
                                    <div className="relative h-[4320px]">
                                        {[...Array(24)].map((_, i) => (
                                            <div key={`line-${i}`} className="absolute w-full border-b border-gray-100 h-[180px]" style={{ top: i * 180 }}></div>
                                        ))}

                                        {channelPrograms.map(p => (
                                            <ProgramCell
                                                key={p.id}
                                                program={p}
                                                baseTime={baseTime}
                                                requestMap={requestMap}
                                                recordedMap={recordedMap}
                                                recordedPrograms={recordedPrograms}
                                                reservations={reservations}
                                                defaultRecordingFolder={defaultRecordingFolder}
                                                setRecordingFolder={setRecordingFolder}
                                                setSelectedProgram={setSelectedProgram}
                                                fontConfig={fontConfig}
                                            />
                                        ))}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            )}
        </div>
    );
};

export default memo(EPGGrid);
