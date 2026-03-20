import React from 'react';
import { format } from 'date-fns';
import { ChevronRight, AlertCircle, MonitorPlay, Trash2, Clock, Bot } from 'lucide-react';

const ProgramDetailModal = ({
    selectedProgram,
    setSelectedProgram,
    recordingFolder,
    setRecordingFolder,
    defaultRecordingFolder,
    onPlay,
    setDeleteTarget,
    handleCancelReservation,
    handleReserve,
    onOpenAutoResSettings
}) => {
    if (!selectedProgram) return null;

    const now = new Date();
    const isPast = new Date(selectedProgram.program.end_time) < now;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[90] p-4" onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedProgram(null);
        }}>
            <div className="bg-white rounded-xl shadow-xl w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]">
                <div className="p-4 border-b border-gray-200 flex justify-between items-start bg-gray-50">
                    <div>
                        <h2 className="text-lg font-bold text-gray-900 leading-snug">{selectedProgram.program.title}</h2>
                        <div className="text-sm text-gray-500 font-mono mt-1">
                            {format(new Date(selectedProgram.program.start_time), 'yyyy/MM/dd HH:mm')} - {format(new Date(selectedProgram.program.end_time), 'HH:mm')}
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                            <div className="text-xs font-bold text-gray-600 bg-gray-200 px-2 py-0.5 rounded inline-block">
                                {selectedProgram.program.service_name}
                            </div>
                            {selectedProgram.reservation?.auto_reservation_id && (
                                <div className="text-xs font-bold text-purple-700 bg-purple-100 border border-purple-200 px-2 py-0.5 rounded inline-block">
                                    自動予約
                                </div>
                            )}
                            {selectedProgram.reservation?.status === 'skipped' && (
                                <div className="text-xs font-bold text-orange-700 bg-orange-100 border border-orange-200 px-2 py-0.5 rounded inline-block flex items-center gap-1">
                                    <AlertCircle className="w-3 h-3" /> 予約スキップ (チューナー不足)
                                </div>
                            )}
                        </div>
                    </div>
                    <button onClick={() => setSelectedProgram(null)} className="p-1 hover:bg-gray-200 rounded-full">
                        <ChevronRight className="w-6 h-6 text-gray-400 rotate-90" />
                    </button>
                </div>

                <div className="p-6 overflow-y-auto flex-1">
                    <p className="text-gray-700 whitespace-pre-wrap leading-relaxed text-sm">
                        {selectedProgram.program.description}
                    </p>
                </div>

                <div className="p-4 border-t border-gray-200 bg-gray-50 flex flex-col gap-3">
                    {!selectedProgram.reservation && !selectedProgram.recorded && !isPast && (
                        <div className="mb-2">
                            <label className="block text-xs font-bold text-gray-700 mb-1">録画保存先フォルダ</label>
                            <input
                                type="text"
                                value={recordingFolder || ""}
                                onChange={(e) => setRecordingFolder(e.target.value)}
                                className="w-full text-sm p-2 border border-gray-300 rounded focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                                placeholder={defaultRecordingFolder || "C:\\TVRecordings"}
                            />
                            <div className="text-[10px] text-gray-500 mt-1">
                                ※空欄の場合はデフォルト設定が使用されます。指定フォルダが存在しない場合は自動作成されます。
                            </div>
                        </div>
                    )}
                    <div className="flex gap-3">
                        {selectedProgram.recorded ? (
                            <>
                                <button
                                    onClick={() => onPlay(selectedProgram.recorded.id)}
                                    className="flex-[2] bg-green-600 hover:bg-green-700 text-white py-3 rounded-lg font-bold shadow-lg transition flex items-center justify-center gap-2"
                                >
                                    <MonitorPlay className="w-5 h-5" /> 再生する
                                </button>
                                <button
                                    onClick={() => {
                                        setDeleteTarget(selectedProgram.recorded);
                                        setSelectedProgram(null);
                                    }}
                                    className="flex-1 bg-red-100 hover:bg-red-200 text-red-700 py-3 rounded-lg font-bold shadow-lg transition flex items-center justify-center gap-2"
                                >
                                    <Trash2 className="w-5 h-5" /> 削除
                                </button>
                            </>
                        ) : selectedProgram.reservation ? (
                            <button
                                onClick={() => handleCancelReservation(selectedProgram.reservation.id, selectedProgram.reservation.status)}
                                className={`flex-1 py-3 rounded-lg font-bold text-white shadow-lg transition flex items-center justify-center gap-2 ${selectedProgram.reservation.status === 'recording' ? 'bg-red-600 hover:bg-red-700' : 'bg-orange-500 hover:bg-orange-600'}`}
                            >
                                {selectedProgram.reservation.status === 'recording' ? (
                                    <><div className="animate-pulse bg-white w-2 h-2 rounded-full"></div> 録画中止</>
                                ) : (
                                    <><Trash2 className="w-5 h-5" /> 予約取消</>
                                )}
                            </button>
                        ) : !isPast ? (
                            <button
                                onClick={() => handleReserve(selectedProgram.program)}
                                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg font-bold shadow-lg transition flex items-center justify-center gap-2"
                            >
                                <Clock className="w-5 h-5" /> 録画予約
                            </button>
                        ) : null}
                    </div>
                </div>

                {!selectedProgram.reservation && !selectedProgram.recorded && (
                    <div className="p-4 border-t border-gray-200 bg-white flex justify-center">
                        <button
                            onClick={() => {
                                if (onOpenAutoResSettings) {
                                    onOpenAutoResSettings(selectedProgram.program);
                                }
                                setSelectedProgram(null);
                            }}
                            className="text-indigo-600 hover:text-indigo-800 text-sm font-bold flex items-center gap-1"
                        >
                            <Bot className="w-4 h-4" /> 自動予約設定を開く
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ProgramDetailModal;
