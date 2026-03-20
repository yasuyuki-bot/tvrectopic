import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { format, startOfDay, addDays, subDays } from 'date-fns';
import { ja } from 'date-fns/locale';
import { Calendar, ChevronLeft, ChevronRight, RefreshCw, Loader, Bot, Video, Clock, Settings } from 'lucide-react';
import DeleteConfirmDialog from './DeleteConfirmDialog';

import { useEPGData } from './epg/useEPGData';
import EPGGrid from './epg/EPGGrid';
import ProgramDetailModal from './epg/ProgramDetailModal';

const EPGView = ({ onPlay, onOpenAutoResSettings, settings, settingsUpdateTrigger, mode, setMode }) => {
    const [updating, setUpdating] = useState(false);
    const [selectedProgram, setSelectedProgram] = useState(null);
    const [recordingFolder, setRecordingFolder] = useState("");
    const [defaultRecordingFolder, setDefaultRecordingFolder] = useState("");
    const [deleteTarget, setDeleteTarget] = useState(null);
    const scrollContainerRef = useRef(null);
    const dateInputRef = useRef(null);

    const [currentDate, setCurrentDate] = useState(new Date());
    const [selectedType, setSelectedType] = useState('GR');
    const [currentTimeTop, setCurrentTimeTop] = useState(-1);

    const isToday = format(currentDate, 'yyyy-MM-dd') === format(new Date(), 'yyyy-MM-dd');

    const {
        epgData, setEpgData,
        loading, setLoading,
        reservations, setReservations,
        recordedPrograms, setRecordedPrograms,
        channelsConfig, fetchChannels,
        dateRange, fetchDateRange,
        fetchEPG, fetchReservations, fetchRecorded,
        requestMap, recordedMap,
        programsByServiceId, programsByChannel
    } = useEPGData(currentDate, selectedType, settingsUpdateTrigger);

    useEffect(() => {
        if (settings && settings.recording_folder) {
            setDefaultRecordingFolder(settings.recording_folder);
        }
    }, [settings]);

    useEffect(() => {
        const updateTimeLine = () => {
            if (!isToday) return;
            const now = new Date();
            const startOfToday = startOfDay(now);
            const diffHours = (now - startOfToday) / 1000 / 3600;
            setCurrentTimeTop(diffHours * 180);
        };

        updateTimeLine();
        const interval = setInterval(updateTimeLine, 60000); // 1 min
        return () => clearInterval(interval);
    }, [isToday]);

    const [shouldScrollToNow, setShouldScrollToNow] = useState(true);

    useEffect(() => {
        setShouldScrollToNow(true);
    }, [currentDate]);

    useEffect(() => {
        if (!loading && isToday && shouldScrollToNow && scrollContainerRef.current) {
            const now = new Date();
            const startOfToday = startOfDay(now);
            const diffHours = (now - startOfToday) / 1000 / 3600;
            const targetScroll = Math.max(0, (diffHours * 180) - 300);

            scrollContainerRef.current.scrollTop = targetScroll;
            setShouldScrollToNow(false);
        }
    }, [loading, isToday, shouldScrollToNow]);

    const handleUpdate = async (type = null) => {
        if (updating) return;
        setUpdating(true);
        try {
            const apiBase = `http://${window.location.hostname}:8000`;
            const url = type ? `${apiBase}/api/epg/update?type=${type}` : `${apiBase}/api/epg/update`;
            await axios.post(url);
            const msg = type ? `${type}のEPG更新を開始しました。` : "全チャンネルのEPG更新を開始しました。";
            alert(`${msg}完了まで数分かかります。`);
        } catch (e) {
            alert("更新開始に失敗しました");
        } finally {
            setUpdating(false);
        }
    };

    const handleReserve = async (program, force = false) => {
        if (!force && !confirm(`${program.title}\n予約しますか？`)) return;
        try {
            const now = new Date();
            const start = new Date(program.start_time);
            const isImmediate = start <= now;

            const payload = {
                event_id: program.event_id,
                service_id: program.service_id,
                program_id: program.id,
                title: program.title,
                description: program.description || "",
                start_time: program.start_time,
                end_time: program.end_time,
                channel: program.channel,
                service_name: program.service_name,
                recording_folder: recordingFolder || null,
                force: force
            };

            const endpoint = isImmediate
                ? `http://${window.location.hostname}:8000/api/record/start`
                : `http://${window.location.hostname}:8000/api/record/schedule`;

            const res = await axios.post(endpoint, payload);

            if (res.data.status === "Conflict") {
                if (confirm(res.data.message)) {
                    return handleReserve(program, true);
                }
                return;
            }

            alert(isImmediate ? "録画を開始しました" : "予約しました");
            setSelectedProgram(null);
            await Promise.all([fetchReservations(), fetchRecorded()]);
        } catch (e) {
            console.error(e);
            if (e.response && e.response.data && e.response.data.detail) {
                alert(`失敗しました: ${e.response.data.detail}`);
            } else if (e.response && e.response.status === 409) {
                alert("チューナー不足のため予約できません");
            } else {
                alert("予約/録画開始に失敗しました（サーバーエラー）");
            }
        }
    };

    const handleCancelReservation = async (id, status) => {
        const isRecording = status === 'recording';
        if (!confirm(isRecording ? "録画を中止しますか？（ファイルは保存されます）" : "予約を取り消しますか？")) return;
        try {
            if (isRecording) {
                await axios.post(`http://${window.location.hostname}:8000/api/record/stop?program_id=${id}`);
            } else {
                await axios.delete(`http://${window.location.hostname}:8000/api/reservations/${id}`);
            }
            alert(isRecording ? "中止しました" : "取り消しました");
            setSelectedProgram(null);
            if (isRecording) {
                await Promise.all([fetchReservations(), fetchRecorded()]);
            } else {
                fetchReservations();
            }
        } catch (e) {
            alert("操作に失敗しました");
        }
    };

    const handleDeleteRecorded = async (deleteFile) => {
        if (!deleteTarget) return;
        try {
            await axios.delete(`http://${window.location.hostname}:8000/api/recorded/${deleteTarget.id}?delete_file=${deleteFile}`);
            setDeleteTarget(null);
            setSelectedProgram(null);
            await Promise.all([fetchRecorded(), fetchReservations()]);
            alert("削除しました");
        } catch (e) {
            alert("削除に失敗しました: " + (e.response?.data?.detail || e.message));
        }
    };

    const displayChannels = channelsConfig.filter(ch => {
        if (ch.visible === false) return false;
        if (selectedType === 'GR') return ch.type === 'GR';
        if (selectedType === 'BS') return ch.type === 'BS';
        if (selectedType === 'CS') return ch.type === 'CS';
        return false;
    });

    const getFontSizeConfig = () => {
        switch (settings?.font_size || 'medium') {
            case 'small': return { base: 'text-xs', title: 'text-xs', meta: 'text-[10px]' };
            case 'large': return { base: 'text-base', title: 'text-base', meta: 'text-sm' };
            case 'xlarge': return { base: 'text-lg', title: 'text-lg', meta: 'text-base' };
            default: return { base: 'text-sm', title: 'text-sm', meta: 'text-xs' };
        }
    };
    const fontConfig = getFontSizeConfig();

    const handlePrevDay = () => {
        const next = subDays(currentDate, 1);
        if (dateRange.min && startOfDay(next) < dateRange.min) return;
        setCurrentDate(next);
    };
    const handleNextDay = () => {
        const next = addDays(currentDate, 1);
        if (dateRange.max && startOfDay(next) > dateRange.max) return;
        setCurrentDate(next);
    };
    const handleToday = () => {
        const today = new Date();
        if (dateRange.min && startOfDay(today) < dateRange.min) {
            setCurrentDate(dateRange.min);
        } else if (dateRange.max && startOfDay(today) > dateRange.max) {
            setCurrentDate(dateRange.max);
        } else {
            setCurrentDate(today);
        }
    };

    const [clickTime, setClickTime] = useState(0);
    useEffect(() => {
        if (clickTime > 0 && !loading) {
            const end = performance.now();
            console.log(`[EPG Performance] Tab Switch to Render: ${(end - clickTime).toFixed(2)}ms`);
            setClickTime(0);
        }
    }, [epgData, loading, selectedType]);

    return (
        <div className="h-full flex flex-col bg-gray-50 text-gray-900 overflow-hidden">
            {/* Header */}
            <div className="p-1 md:p-4 border-b border-gray-200 flex flex-nowrap md:flex-row items-center justify-between gap-1 md:gap-3 bg-white z-10 shadow-sm overflow-x-auto no-scrollbar landscape-compact-p">

                <div className="flex items-center gap-1 md:gap-6 flex-shrink-0 landscape-compact-gap">
                    {/* App Tabs (Visible only in landscape-mobile and maybe small screens) */}
                    <div className="flex md:hidden bg-gray-100 rounded p-0.5 border border-gray-200 landscape-inline-flex hidden">
                        {[
                            { id: 'epg', label: '番組', icon: <Calendar className="w-3.5 h-3.5" /> },
                            { id: 'recording', label: '録画', icon: <Video className="w-3.5 h-3.5" /> },
                            { id: 'reservation', label: '予約', icon: <Clock className="w-3.5 h-3.5" /> },
                            { id: 'autores', label: '自動', icon: <Bot className="w-3.5 h-3.5" /> },
                            { id: 'settings', label: '設定', icon: <Settings className="w-3.5 h-3.5" /> }
                        ].map(m => (
                            <button
                                key={m.id}
                                onClick={() => setMode(m.id)}
                                className={`px-1.5 py-1 rounded text-[10px] font-bold transition-all whitespace-nowrap flex flex-col items-center gap-0 ${mode === m.id ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500'}`}
                            >
                                {m.icon}
                                <span className="text-[8px] leading-none">{m.label}</span>
                            </button>
                        ))}
                    </div>

                    <h1 className="flex items-center gap-0.5 md:gap-2 text-gray-800 flex-shrink-0 landscape-hide">
                        <Calendar className="w-3.5 h-3.5 md:w-6 md:h-6 text-blue-600" />
                        <span className="hidden sm:inline text-xs md:text-xl font-bold">番組表</span>
                    </h1>

                    <div className="flex bg-gray-100 rounded md:rounded-lg p-0.5 border border-gray-200 w-auto">
                        {['GR', 'BS', 'CS'].map(type => (
                            <button
                                key={type}
                                onClick={() => {
                                    setClickTime(performance.now());
                                    setSelectedType(type);
                                }}
                                className={`px-2 md:px-4 py-1.5 md:py-1.5 rounded text-xs md:text-sm font-bold transition-all whitespace-nowrap ${selectedType === type
                                    ? 'bg-white text-blue-600 shadow-sm border border-gray-100 md:border-gray-200'
                                    : 'text-gray-500 hover:text-gray-900'
                                    }`}
                            >
                                {type}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Date Nav on the same line */}
                <div className="flex items-center gap-1 md:gap-6 flex-shrink-0 landscape-compact-gap">
                    <div className="flex items-center bg-gray-100 rounded md:rounded-lg p-0.5 border border-gray-200 landscape-compact-gap">
                        <button onClick={handlePrevDay} className="p-1 md:p-1 hover:bg-gray-200 rounded text-gray-500">
                            <ChevronLeft className="w-5 h-5 md:w-5 md:h-5" />
                        </button>

                        <div
                            className="relative group flex items-center cursor-pointer"
                            onClick={() => dateInputRef.current?.showPicker()}
                        >
                            <input
                                ref={dateInputRef}
                                type="date"
                                className="absolute inset-0 opacity-0 cursor-pointer pointer-events-none"
                                value={format(currentDate, 'yyyy-MM-dd')}
                                min={dateRange.min ? format(dateRange.min, 'yyyy-MM-dd') : undefined}
                                max={dateRange.max ? format(dateRange.max, 'yyyy-MM-dd') : undefined}
                                onChange={(e) => e.target.value && setCurrentDate(new Date(e.target.value))}
                            />
                            <div className="px-2 md:px-2 py-1 font-mono font-bold text-xs md:text-sm text-gray-800 whitespace-nowrap">
                                {format(currentDate, "M/d(E)", { locale: ja })}
                            </div>
                        </div>

                        <button onClick={handleNextDay} className="p-1 md:p-1 hover:bg-gray-200 rounded text-gray-500">
                            <ChevronRight className="w-5 h-5 md:w-5 md:h-5" />
                        </button>
                    </div>

                    <button
                        onClick={handleToday}
                        className="text-xs md:text-xs px-2.5 md:px-2 py-1.5 md:py-1 bg-white border border-gray-200 rounded hover:bg-gray-50 text-gray-600 font-bold shadow-sm whitespace-nowrap"
                    >
                        今日
                    </button>
                </div>
            </div>

            <EPGGrid
                loading={loading}
                isToday={isToday}
                currentTimeTop={currentTimeTop}
                displayChannels={displayChannels}
                programsByServiceId={programsByServiceId}
                programsByChannel={programsByChannel}
                requestMap={requestMap}
                recordedMap={recordedMap}
                reservations={reservations}
                recordedPrograms={recordedPrograms}
                defaultRecordingFolder={defaultRecordingFolder}
                setRecordingFolder={setRecordingFolder}
                setSelectedProgram={setSelectedProgram}
                onPlay={onPlay}
                fontConfig={fontConfig}
                scrollContainerRef={scrollContainerRef}
                baseTime={startOfDay(currentDate)}
            />

            <ProgramDetailModal
                selectedProgram={selectedProgram}
                setSelectedProgram={setSelectedProgram}
                recordingFolder={recordingFolder}
                setRecordingFolder={setRecordingFolder}
                defaultRecordingFolder={defaultRecordingFolder}
                onPlay={onPlay}
                setDeleteTarget={setDeleteTarget}
                handleCancelReservation={handleCancelReservation}
                handleReserve={handleReserve}
                onOpenAutoResSettings={onOpenAutoResSettings}
            />

            <DeleteConfirmDialog
                isOpen={!!deleteTarget}
                program={deleteTarget}
                onClose={() => setDeleteTarget(null)}
                onConfirm={handleDeleteRecorded}
            />
        </div>
    );
};

export default EPGView;
