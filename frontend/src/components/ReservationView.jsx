import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Trash2, Clock, CheckCircle, AlertCircle, StopCircle, Bot, Calendar, Video, Settings } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { ja } from 'date-fns/locale';

const ReservationView = ({ mode, setMode }) => {
    const [reservations, setReservations] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchReservations = async () => {
        setLoading(true);
        try {
            const res = await axios.get(`http://${window.location.hostname}:8000/api/reservations`);
            setReservations(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchReservations();
    }, []);

    const handleAction = async (id, status) => {
        const isRecording = status === 'recording';
        if (isRecording) {
            if (!confirm("録画を中止しますか？（ファイルは保存されます）")) return;
            try {
                // Call Stop Endpoint
                await axios.post(`http://${window.location.hostname}:8000/api/record/stop?program_id=${id}`);
                // Instead of deleting, we refresh to show "completed" or "stopped"
                fetchReservations();
            } catch (e) {
                alert("中止に失敗しました");
            }
        } else {
            if (!confirm("予約を削除しますか？")) return;
            try {
                await axios.delete(`http://${window.location.hostname}:8000/api/reservations/${id}`);
                fetchReservations();
            } catch (err) {
                alert("削除に失敗しました");
            }
        }
    };

    // Safe date formatter
    const formatDateSafe = (dateStr, fmt) => {
        if (!dateStr) return "";
        try {
            return format(parseISO(dateStr), fmt, { locale: ja });
        } catch (e) {
            return dateStr;
        }
    };

    if (loading) return <div className="text-center py-20 text-gray-500">読み込み中...</div>;

    // Filter out old completed ones? Or show all? User said "near time top". 
    // Usually reservation list implies future. But failed/recording is also good.
    // Let's split into "Upcoming/Active" and "History"? Or just simple list.
    // User: "Reservation List" -> "Time near current on top"
    // So sort by difference from now? Or just start time ASC (for future) and DESC (for past)?
    // Usually simply Start Time ASC (Upcoming first) suitable.
    // Let's filter out 'completed' if too many, but for now show all.

    return (
        <div className="max-w-4xl mx-auto space-y-4">
            {/* Landscape Integrated Header */}
            <div className="md:hidden bg-white p-1 border-b border-gray-200 landscape-inline-flex hidden items-center gap-1 w-full overflow-x-auto no-scrollbar">
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
                        className={`px-2 py-1.5 rounded text-[10px] font-bold transition-all whitespace-nowrap flex flex-col items-center gap-0 ${mode === m.id ? 'bg-blue-50 text-blue-600' : 'text-gray-500'}`}
                    >
                        {m.icon}
                        <span className="text-[8px] leading-none">{m.label}</span>
                    </button>
                ))}
            </div>

            <h2 className="text-xl font-bold text-gray-800 mb-6 flex items-center gap-2 landscape-hide">
                <Clock className="w-6 h-6 text-blue-600" />
                予約一覧
            </h2>

            {reservations.length === 0 ? (
                <div className="bg-white p-8 rounded-xl text-center text-gray-500 border border-gray-200">
                    予約はありません。
                </div>
            ) : (
                reservations.map(res => (
                    <div key={res.id} className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex justify-between items-center group">
                        <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                                <span className={`text-xs font-bold px-2 py-0.5 rounded text-white ${res.status === 'recording' ? 'bg-red-500 animate-pulse' :
                                    res.status === 'scheduled' ? 'bg-blue-500' :
                                        res.status === 'skipped' ? 'bg-orange-500' :
                                            res.status === 'completed' ? 'bg-green-500' : 'bg-gray-400'
                                    }`}>
                                    {res.status === 'recording' ? '録画中' :
                                        res.status === 'scheduled' ? '予約' :
                                            res.status === 'skipped' ? (res.skip_reason === 'conflict' ? '時間重複スキップ' : res.skip_reason === 'manual_delete' ? '手動削除' : '重複スキップ') :
                                                res.status === 'completed' ? '完了' : res.status}
                                </span>
                                {res.auto_reservation_id && (
                                    <span className="text-xs font-bold px-2 py-0.5 rounded bg-purple-100 text-purple-700 border border-purple-200">
                                        自動
                                    </span>
                                )}
                                <span className="text-sm text-gray-500">
                                    {formatDateSafe(res.start_time, 'yyyy/MM/dd(EEE) HH:mm')} - {formatDateSafe(res.end_time, 'HH:mm')}
                                </span>
                                <span className="text-sm font-bold text-gray-600">{res.service_name}</span>
                            </div>
                            <h3 className="font-bold text-gray-900 text-lg">{res.title}</h3>
                        </div>

                        <button
                            onClick={() => handleAction(res.id, res.status)}
                            className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-full transition"
                            title={res.status === 'recording' ? "中止・削除" : "削除"}
                        >
                            {res.status === 'recording' ? <StopCircle className="w-6 h-6" /> : <Trash2 className="w-5 h-5" />}
                        </button>
                    </div>
                ))
            )}
        </div>
    );
};

export default ReservationView;
