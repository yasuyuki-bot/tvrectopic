import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Trash2, Edit, List, Bot, Loader, Calendar, Video, Clock, Settings } from 'lucide-react';
import { format } from 'date-fns';

const AutoReservationView = ({ onEdit, onRefresh, refreshTrigger, mode, setMode }) => {
    const [rules, setRules] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expandedRuleId, setExpandedRuleId] = useState(null);
    const [reservations, setReservations] = useState({}); // Map ruleId -> reservation list

    const fetchRules = async () => {
        try {
            const res = await axios.get(`http://${window.location.hostname}:8000/api/auto_reservations`);
            setRules(res.data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const fetchReservationsForRule = async (ruleId) => {
        try {
            const res = await axios.get(`http://${window.location.hostname}:8000/api/auto_reservations/${ruleId}/reservations`);
            setReservations(prev => ({ ...prev, [ruleId]: res.data }));
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        fetchRules();
        // If a rule is expanded, refresh its reservations too
        if (expandedRuleId) {
            fetchReservationsForRule(expandedRuleId);
        } else {
            // Optional: Clear cache to force fetch on next open?
            // But valid cache is nice. Maybe just clear everything if we don't know what changed?
            // Safests: setReservations({});
            setReservations({});
        }
    }, [refreshTrigger]);

    const handleDelete = async (id, name) => {
        if (!confirm(`自動予約「${name}」を削除しますか？\n（このルールによる未完了の予約も削除されます）`)) return;
        try {
            await axios.delete(`http://${window.location.hostname}:8000/api/auto_reservations/${id}`);
            setRules(rules.filter(r => r.id !== id));
            // Trigger global refresh (for EPG etc.)
            if (onRefresh) onRefresh();
            // If we have an expanded rule, its reservations might have changed (recovery)
            if (expandedRuleId && expandedRuleId !== id) {
                fetchReservationsForRule(expandedRuleId);
            }
        } catch (e) {
            alert("削除に失敗しました");
        }
    };

    const toggleReservations = async (ruleId) => {
        if (expandedRuleId === ruleId) {
            setExpandedRuleId(null);
            return;
        }

        setExpandedRuleId(ruleId);
        // Always fetch fresh data on toggle? Or trust cache?
        // Trust cache for UX speed, but if we just saved, the useEffect handled it.
        // If we just clicked toggle, maybe we should fetch if missing.
        if (!reservations[ruleId]) {
            fetchReservationsForRule(ruleId);
        }
    };

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center bg-white">
                <Loader className="w-8 h-8 animate-spin text-blue-600" />
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-gray-50 overflow-hidden">
            {/* Landscape Integrated Header */}
            <div className="md:hidden bg-white p-1 border-b border-gray-200 landscape-inline-flex hidden items-center justify-between w-full">
                <div className="flex items-center gap-1 overflow-x-auto no-scrollbar">
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
                <button
                    onClick={() => onEdit(null)}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-bold shadow hover:bg-blue-700 transition shrink-0"
                >
                    <Bot className="w-3.5 h-3.5" /> 新規
                </button>
            </div>

            {/* Header */}
            <div className="p-4 border-b border-gray-200 bg-white shadow-sm flex items-center justify-between landscape-hide">
                <div className="flex items-center gap-2">
                    <Bot className="w-6 h-6 text-blue-600" />
                    <h2 className="text-xl font-bold text-gray-800">自動予約一覧</h2>
                </div>
                <button
                    onClick={() => onEdit(null)}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 text-white font-bold shadow hover:bg-blue-700 transition"
                >
                    <Bot className="w-5 h-5" /> 新規作成
                </button>
            </div>

            {/* List Body */}
            <div className="flex-1 overflow-y-auto p-4 md:p-6">
                {rules.length === 0 ? (
                    <div className="max-w-4xl mx-auto text-center py-20 bg-white rounded-xl border border-dashed border-gray-300">
                        <Bot className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                        <p className="text-lg text-gray-500 font-medium">自動予約設定はありません</p>
                        <p className="text-sm text-gray-400 mt-1">番組表の番組詳細から自動予約を追加できます</p>
                    </div>
                ) : (
                    <div className="max-w-4xl mx-auto space-y-4">
                        {rules.map(rule => (
                            <div key={rule.id} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden transition hover:shadow-md">
                                <div className="p-4 md:p-5 flex flex-col md:flex-row md:items-center gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className="text-lg font-bold text-gray-900 truncate">{rule.name}</h3>
                                            {!rule.active && (
                                                <span className="bg-gray-100 text-gray-500 text-[10px] font-bold px-2 py-0.5 rounded-full border border-gray-200 uppercase">
                                                    Disabled
                                                </span>
                                            )}
                                        </div>
                                        <div className="text-sm text-gray-500 flex flex-wrap gap-2 mt-2">
                                            {rule.keyword && (
                                                <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded-md border border-blue-100 flex items-center gap-1 font-medium">
                                                    <span className="text-[10px] opacity-70 uppercase">KW:</span> {rule.keyword}
                                                </span>
                                            )}
                                            <span className="bg-gray-100 text-gray-700 px-2 py-0.5 rounded-md border border-gray-200 font-medium">
                                                {rule.types}
                                            </span>
                                            {rule.time_range_start && (
                                                <span className="bg-green-50 text-green-700 px-2 py-0.5 rounded-md border border-green-100 flex items-center gap-1 font-medium">
                                                    <span className="text-[10px] opacity-70 uppercase">TIME:</span> {rule.time_range_start} - {rule.time_range_end}
                                                </span>
                                            )}
                                            <span className="bg-amber-50 text-amber-700 px-2 py-0.5 rounded-md border border-amber-100 flex items-center gap-1 font-medium">
                                                <span className="text-[10px] opacity-70 uppercase">優先度:</span> {rule.priority ?? 5}
                                            </span>
                                        </div>
                                    </div>

                                    <div className="flex flex-wrap gap-2 shrink-0 border-t md:border-t-0 pt-3 md:pt-0 border-gray-100">

                                        <button
                                            onClick={() => toggleReservations(rule.id)}
                                            className={`flex-1 md:flex-none flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-bold transition ${expandedRuleId === rule.id ? 'bg-blue-50 border-blue-300 text-blue-600' : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'}`}
                                            title="予約済み番組を表示"
                                        >
                                            <List className="w-4 h-4" /> 予約一覧
                                        </button>
                                        <button
                                            onClick={() => onEdit(rule)}
                                            className="flex-1 md:flex-none flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 text-sm font-bold transition"
                                            title="設定を変更"
                                        >
                                            <Edit className="w-4 h-4" /> 設定
                                        </button>
                                        <button
                                            onClick={() => handleDelete(rule.id, rule.name)}
                                            className="flex-1 md:flex-none flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-red-100 bg-white text-red-600 hover:bg-red-50 text-sm font-bold transition"
                                            title="削除"
                                        >
                                            <Trash2 className="w-4 h-4" /> 削除
                                        </button>
                                    </div>

                                </div>

                                {/* Reservations List (Expanded) */}
                                {expandedRuleId === rule.id && (
                                    <div className="border-t border-gray-100 bg-gray-50/50 p-4">
                                        <div className="flex items-center justify-between mb-3">
                                            <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">予約中の番組</h4>
                                            <span className="text-xs text-gray-400 font-mono">
                                                {reservations[rule.id]?.length || 0} 件
                                            </span>
                                        </div>
                                        {!reservations[rule.id] ? (
                                            <div className="text-sm text-gray-400 flex items-center gap-2 py-2">
                                                <Loader className="w-3 h-3 animate-spin" /> 読み込み中...
                                            </div>
                                        ) : reservations[rule.id].length === 0 ? (
                                            <div className="text-sm text-gray-400 py-2 italic">予約された番組はありません</div>
                                        ) : (
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                                {reservations[rule.id].map(rec => (
                                                    <div key={rec.id} className="flex justify-between items-center bg-white p-3 rounded-lg border border-gray-200 text-sm shadow-sm transition hover:border-gray-300">
                                                        <div className="min-w-0 pr-2">
                                                            <div className="font-bold text-gray-900 truncate">{rec.title}</div>
                                                            <div className="text-[11px] text-gray-500 mt-0.5 flex items-center gap-1">
                                                                <span className="font-mono">{format(new Date(rec.start_time), 'MM/dd')}({['日', '月', '火', '水', '木', '金', '土'][new Date(rec.start_time).getDay()]}) {format(new Date(rec.start_time), 'HH:mm')}</span>
                                                                <span className="opacity-50">|</span>
                                                                <span className="truncate">{rec.service_name}</span>
                                                            </div>
                                                        </div>
                                                        <div className={`shrink-0 px-2 py-0.5 rounded text-[10px] font-bold uppercase ${rec.status === 'recording' ? 'bg-red-100 text-red-600 border border-red-200' :
                                                            rec.status === 'skipped' ? 'bg-gray-100 text-gray-500 border border-gray-200' :
                                                                'bg-blue-50 text-blue-600 border border-blue-100'
                                                            }`}>
                                                            {rec.status === 'skipped' ? (rec.skip_reason === 'conflict' ? '時間重複スキップ' : rec.skip_reason === 'manual_delete' ? '手動削除' : '重複スキップ') : rec.status}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default AutoReservationView;
