import React, { useState, useEffect, memo, useMemo } from 'react';
import axios from 'axios';
import { PlayCircle, Video, Search, Trash2, CheckSquare, Square, CheckCircle2, Clock, Bot, Calendar, Settings } from 'lucide-react';
import { format, parseISO, addSeconds } from 'date-fns';
import { ja } from 'date-fns/locale';
import DeleteConfirmDialog from './DeleteConfirmDialog';
import BulkDeleteConfirmDialog from './BulkDeleteConfirmDialog';

// Safe date formatter
const formatDateSafe = (dateStr, fmt) => {
    if (!dateStr) return "";
    try {
        return format(parseISO(dateStr), fmt, { locale: ja });
    } catch (e) {
        return dateStr;
    }
};

const parseStartTime = (timeStr) => {
    if (!timeStr) return "";
    return String(timeStr).split('.')[0];
};

const ProgramItem = memo(({ prog, onPlay, onDelete, isSelected, onToggle }) => {
    return (
        <div className={`bg-white p-3 md:p-4 rounded-xl shadow-sm border transition group flex flex-col md:flex-row justify-between items-start md:items-center gap-4 hover:bg-green-50 ${isSelected ? 'border-green-500 bg-green-50' : 'border-gray-100'}`}>
            <div className="flex items-center gap-3 flex-1 w-full">
                <button
                    onClick={(e) => { e.stopPropagation(); onToggle(prog.id); }}
                    className={`shrink-0 transition-colors ${isSelected ? 'text-green-600' : 'text-gray-300 hover:text-gray-400'}`}
                    title={isSelected ? "選択解除" : "選択"}
                >
                    {isSelected ? <CheckSquare className="w-6 h-6" /> : <Square className="w-6 h-6" />}
                </button>

                <div className="flex-1 cursor-pointer min-w-0" onClick={() => onPlay(prog.id)}>
                    <div className="text-xs text-gray-500 mb-1 flex items-center gap-2">
                        <span className="bg-gray-100 px-2 py-0.5 rounded text-gray-600 truncate">{prog.service_name || prog.channel}</span>
                        <span className="shrink-0">{prog.display_time}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <h3 className="font-bold text-gray-900 group-hover:text-green-700 truncate">{prog.title}</h3>
                        {prog.status === 'recording' && (
                            <span className="shrink-0 flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-600 text-[10px] font-bold rounded-full animate-pulse border border-red-200">
                                <div className="w-1.5 h-1.5 bg-red-600 rounded-full"></div>
                                録画中
                            </span>
                        )}
                    </div>
                    <p className="text-sm text-gray-600 mt-1 line-clamp-2">{prog.description}</p>
                    {prog.topics && prog.topics.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                            {prog.topics.slice(0, 3).map((t) => (
                                <span key={t.id} className="inline-block px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">
                                    {t.title}
                                </span>
                            ))}
                            {prog.topics.length > 3 && <span className="text-xs text-gray-400">+{prog.topics.length - 3}</span>}
                        </div>
                    )}
                </div>
            </div>
            <div className="flex items-center gap-4 shrink-0 w-full md:w-auto justify-end border-t md:border-t-0 pt-2 md:pt-0 border-gray-100">
                <button onClick={() => onPlay(prog.id)} className="text-gray-300 hover:text-green-600 transition" title="再生">
                    <PlayCircle className="w-8 h-8" />
                </button>
                <button
                    onClick={(e) => { e.stopPropagation(); onDelete(prog); }}
                    className="text-gray-300 hover:text-red-500 transition p-1 rounded-full hover:bg-red-50"
                    title="削除"
                >
                    <Trash2 className="w-5 h-5" />
                </button>
            </div>
        </div>
    );
});

const TopicItem = memo(({ item, onPlay, allFiles }) => {
    return (
        <div
            className="bg-white p-3 md:p-4 rounded-xl shadow-sm border border-gray-100 hover:bg-green-50 transition cursor-pointer group"
            onClick={() => onPlay(item.program_id, item.start_time, allFiles)}
        >
            <div className="flex justify-between items-start">
                <div>
                    <div className="text-xs text-gray-500 mb-1 flex items-center gap-2">
                        <span className="bg-gray-100 px-2 py-0.5 rounded text-gray-600">{item.service_name || item.channel}</span>
                        <span>{item.display_time}</span>
                        <span className="text-gray-400">- {item.program_title}</span>
                    </div>
                    <h3 className="font-bold text-gray-900 group-hover:text-green-700">{item.title}</h3>
                </div>
                <PlayCircle className="w-6 h-6 text-gray-300 group-hover:text-green-600 transition shrink-0" />
            </div>
        </div>
    );
});

const RecordedView = ({ onPlay, mode, setMode }) => {
    const [files, setFiles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");
    const [searchType, setSearchType] = useState('program');
    const [deleteTarget, setDeleteTarget] = useState(null);
    const [selectedIds, setSelectedIds] = useState([]);
    const [isBulkDeleteOpen, setIsBulkDeleteOpen] = useState(false);

    const fetchFiles = async () => {
        setLoading(true);
        try {
            let url = `http://${window.location.hostname}:8000/api/recorded`;
            if (searchQuery) {
                url = searchType === 'program'
                    ? `http://${window.location.hostname}:8000/api/search/programs?q=${searchQuery}`
                    : `http://${window.location.hostname}:8000/api/search/topics?q=${searchQuery}`;
            }
            const res = await axios.get(url);
            setFiles(res.data);
            setSelectedIds([]); // Reset selection on fetch
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchFiles();
    }, [searchQuery, searchType]);

    const processedFiles = useMemo(() => {
        return files.map(item => {
            const isTopic = item.program_title !== undefined;
            if (isTopic) {
                return {
                    ...item,
                    isTopic: true,
                    display_time: `${formatDateSafe(item.program_date, 'yyyy/MM/dd(EEE)')} ${parseStartTime(item.start_time)}`
                };
            } else {
                const endTimeStr = (item.end_time || item.duration)
                    ? ` - ${formatDateSafe(item.end_time || addSeconds(parseISO(item.start_time), item.duration).toISOString(), 'HH:mm')}`
                    : '';
                return {
                    ...item,
                    isTopic: false,
                    display_time: `${formatDateSafe(item.start_time, 'yyyy/MM/dd(EEE) HH:mm')}${endTimeStr}`
                };
            }
        });
    }, [files]);

    const handleDelete = async (deleteFile) => {
        if (!deleteTarget) return;
        try {
            await axios.delete(`http://${window.location.hostname}:8000/api/recorded/${deleteTarget.id}?delete_file=${deleteFile}`);
            fetchFiles();
            setDeleteTarget(null);
        } catch (err) {
            console.error("Delete failed", err);
            alert("削除に失敗しました: " + (err.response?.data?.detail || err.message));
        }
    };

    const toggleSelect = (id) => {
        setSelectedIds(prev =>
            prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
        );
    };

    const selectAll = () => {
        const selectable = processedFiles
            .filter(f => !f.isTopic)
            .map(f => f.id);
        setSelectedIds(selectable);
    };

    const deselectAll = () => {
        setSelectedIds([]);
    };

    const handleBulkDelete = async (deleteFile) => {
        if (selectedIds.length === 0) return;
        try {
            await axios.post(`http://${window.location.hostname}:8000/api/recorded/bulk_delete`, {
                ids: selectedIds,
                delete_file: deleteFile
            });
            fetchFiles();
            setIsBulkDeleteOpen(false);
            setSelectedIds([]);
        } catch (err) {
            console.error("Bulk delete failed", err);
            alert("一括削除に失敗しました");
        }
    };

    return (
        <div className="max-w-4xl mx-auto space-y-6">
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

            <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2 landscape-hide">
                <Video className="w-6 h-6 text-green-600" />
                録画済み番組
            </h2>

            <div className="flex flex-col lg:flex-row gap-4 bg-white p-4 rounded-xl shadow-sm border border-gray-100">
                <div className="flex gap-4 items-center">
                    {['program', 'topic'].map(type => (
                        <label key={type} className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="radio"
                                checked={searchType === type}
                                onChange={() => setSearchType(type)}
                                className="text-green-600 focus:ring-green-500"
                            />
                            <span className="font-bold text-sm">{type === 'program' ? '番組検索' : 'トピック検索'}</span>
                        </label>
                    ))}
                </div>
                <div className="flex-1 flex gap-2">
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder={searchType === 'program' ? "タイトルまたは詳細で検索..." : "トピックタイトルで検索..."}
                        className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 outline-none"
                    />
                    <button className="bg-green-600 text-white px-6 py-2 rounded-lg font-bold hover:bg-green-700 transition flex items-center gap-2">
                        <Search className="w-4 h-4" /> 検索
                    </button>
                </div>
            </div>

            {searchType === 'program' && processedFiles.length > 0 && (
                <div className="flex items-center justify-between bg-white px-4 py-2 rounded-lg border border-gray-100 shadow-sm">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={selectedIds.length === processedFiles.filter(f => !f.isTopic).length ? deselectAll : selectAll}
                            className="text-sm font-medium text-gray-600 hover:text-green-600 flex items-center gap-2"
                        >
                            {selectedIds.length === processedFiles.filter(f => !f.isTopic).length ? (
                                <><Square className="w-4 h-4" /> 全て選択解除</>
                            ) : (
                                <><CheckSquare className="w-4 h-4" /> 全て選択</>
                            )}
                        </button>
                        {selectedIds.length > 0 && (
                            <span className="text-xs font-bold text-green-700 bg-green-50 px-2 py-0.5 rounded-full border border-green-100 flex items-center gap-1">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                {selectedIds.length} 個選択中
                            </span>
                        )}
                    </div>
                    {selectedIds.length > 0 && (
                        <button
                            onClick={() => setIsBulkDeleteOpen(true)}
                            className="text-sm font-bold text-red-600 hover:bg-red-50 px-3 py-1 rounded-lg transition border border-transparent hover:border-red-100 flex items-center gap-2"
                        >
                            <Trash2 className="w-4 h-4" /> 一括削除
                        </button>
                    )}
                </div>
            )}

            {loading ? (
                <div className="text-center py-20 text-gray-500">読み込み中...</div>
            ) : processedFiles.length === 0 ? (
                <div className="text-center py-20 bg-white rounded-xl border border-dashed border-gray-300 text-gray-500">
                    {searchQuery ? "一致する項目はありません。" : "録画済みのファイルはありません。"}
                </div>
            ) : (
                <div className="space-y-4">
                    {processedFiles.map(item => (
                        item.isTopic ? (
                            <TopicItem key={item.id || item.start_time} item={item} onPlay={onPlay} allFiles={files} />
                        ) : (
                            <ProgramItem
                                key={item.id}
                                prog={item}
                                onPlay={onPlay}
                                onDelete={setDeleteTarget}
                                isSelected={selectedIds.includes(item.id)}
                                onToggle={toggleSelect}
                            />
                        )
                    ))}
                </div>
            )}

            <DeleteConfirmDialog
                isOpen={!!deleteTarget}
                program={deleteTarget}
                onClose={() => setDeleteTarget(null)}
                onConfirm={handleDelete}
            />

            <BulkDeleteConfirmDialog
                isOpen={isBulkDeleteOpen}
                count={selectedIds.length}
                onClose={() => setIsBulkDeleteOpen(false)}
                onConfirm={handleBulkDelete}
            />
        </div>
    );
};

export default RecordedView;
