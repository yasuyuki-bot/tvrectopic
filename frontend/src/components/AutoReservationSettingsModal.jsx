import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { X, Search, Save, Check } from 'lucide-react';
import { format } from 'date-fns';

const AutoReservationSettingsModal = ({ initialProgram, initialRule, onClose, onSaved }) => {
    // Determine initial state
    const [name, setName] = useState(initialRule?.name || initialProgram?.title || "");
    const [keyword, setKeyword] = useState(initialRule?.keyword || initialProgram?.title || "");
    const [searchTarget, setSearchTarget] = useState(initialRule?.search_target || 'title');

    // Days: 0-6. Default all [0,1,2,3,4,5,6] if new
    const parseDays = (str) => str ? str.split(',').map(Number) : [0, 1, 2, 3, 4, 5, 6];
    const [days, setDays] = useState(initialRule ? parseDays(initialRule.days_of_week) : [0, 1, 2, 3, 4, 5, 6]);

    // Genre: List of strings
    const parseGenres = (str) => str ? str.split(',') : (initialRule ? [] : []); // If new, should we select all?
    // Requirement says: "Default all checked". 
    // But we need to fetch all genres first to know what "all" is.
    // We'll init as empty and "check all" after fetch if new.
    const [selectedGenres, setSelectedGenres] = useState(initialRule ? parseGenres(initialRule.genres) : []);
    const [allGenres, setAllGenres] = useState([]);

    // Types: GR,BS,CS. Default all.
    const parseTypes = (str) => str ? str.split(',') : ['GR', 'BS', 'CS'];
    const [selectedTypes, setSelectedTypes] = useState(initialRule ? parseTypes(initialRule.types) : ['GR', 'BS', 'CS']);

    // Channels: CSV of channel "number" or "id".
    // Requirement: "Default unchecked. Default value is clicked program's channel."
    // If initialRule exists, use it.
    // If new (initialProgram), set checking that program's channel.
    // We need channel list.
    const [selectedChannels, setSelectedChannels] = useState([]);
    const [allChannelsConfig, setAllChannelsConfig] = useState([]);

    // Time Search
    const [enableTime, setEnableTime] = useState(!!((initialRule?.time_range_start) || false));
    // Default range is program start-end if new
    // Default range is program start-end if new
    const getDefaultStart = () => (initialProgram && initialProgram.start_time) ? format(new Date(initialProgram.start_time), 'HH:mm') : "";
    const getDefaultEnd = () => (initialProgram && initialProgram.end_time) ? format(new Date(initialProgram.end_time), 'HH:mm') : "";

    const [timeStart, setTimeStart] = useState(initialRule?.time_range_start || getDefaultStart());
    const [timeEnd, setTimeEnd] = useState(initialRule?.time_range_end || getDefaultEnd());

    // Duplicates
    const [allowDuplicates, setAllowDuplicates] = useState(initialRule ? (initialRule.allow_duplicates !== false) : true);
    // Priority
    const [priority, setPriority] = useState(initialRule?.priority ?? 5);

    const [folder, setFolder] = useState(initialRule?.recording_folder || "");
    const [defaultFolder, setDefaultFolder] = useState("");

    // Search Preview
    const [searchResults, setSearchResults] = useState([]);
    const [searching, setSearching] = useState(false);
    const [saving, setSaving] = useState(false);

    // Init Type for new rule
    // If new, `selectedChannels` should init to [initialProgram.channel] or SID?
    // Let's use `channel` string from EPGProgram as ID for simplicity match with backend logic.
    // Backend logic checks `program.channel` vs list or `program.service_id` vs list.
    // It's safer to use Service ID if available, but backend logic also checks channel string.
    // Let's use Channel String (e.g. "24", "BS15_0") as primary key for selection.

    useEffect(() => {
        const init = async () => {
            const apiBase = `http://${window.location.hostname}:8000`;
            try {
                // 1. Fetch Settings (for folder)
                const sRes = await axios.get(`${apiBase}/api/settings`);
                setDefaultFolder(sRes.data.recording_folder || "");
                if (!folder && !initialRule) {
                    setFolder(sRes.data.recording_folder || "");
                }

                // 2. Fetch Genres
                const gRes = await axios.get(`${apiBase}/api/genres`);
                setAllGenres(gRes.data);
                if (!initialRule) {
                    // Default all genres checked
                    setSelectedGenres(gRes.data);
                }

                // 3. Fetch Channels
                const cRes = await axios.get(`${apiBase}/api/channels`);
                const visChannels = cRes.data.filter(c => c.visible !== false);
                setAllChannelsConfig(visChannels);

                if (!initialRule && initialProgram && (initialProgram.service_id || initialProgram.channel)) {
                    // Default to Clicked Program's Channel (using new Key format)
                    const key = getProgKey(initialProgram);
                    setSelectedChannels([key]);
                } else if (initialRule && initialRule.channels) {
                    setSelectedChannels(initialRule.channels.split(','));
                }

            } catch (e) {
                console.error("Init failed", e);
            }
        };
        init();
    }, []);

    const handleSearch = async () => {
        setSearching(true);
        try {
            const payload = {
                name: name,
                keyword: keyword,
                days_of_week: days.join(','),
                genres: selectedGenres.join(','),
                types: selectedTypes.join(','),
                channels: selectedChannels.join(','),
                time_range_start: enableTime ? timeStart : null,
                time_range_end: enableTime ? timeEnd : null,
                search_target: searchTarget,
                allow_duplicates: allowDuplicates,
                priority: parseInt(priority) || 5
            };
            const res = await axios.post(`http://${window.location.hostname}:8000/api/auto_reservations/preview`, payload);
            setSearchResults(res.data);
        } catch (e) {
            alert("検索に失敗しました");
        } finally {
            setSearching(false);
        }
    };

    const handleSave = async () => {
        if (!name) return alert("自動予約名を入力してください");
        setSaving(true);
        try {
            const payload = {
                name: name,
                keyword: keyword,
                days_of_week: days.join(','),
                genres: selectedGenres.join(','),
                types: selectedTypes.join(','),
                channels: selectedChannels.join(','),
                time_range_start: enableTime ? timeStart : null,
                time_range_end: enableTime ? timeEnd : null,
                search_target: searchTarget,
                allow_duplicates: allowDuplicates,
                priority: parseInt(priority) || 5,
                active: true
            };

            if (initialRule) {
                await axios.put(`http://${window.location.hostname}:8000/api/auto_reservations/${initialRule.id}`, payload);
            } else {
                await axios.post(`http://${window.location.hostname}:8000/api/auto_reservations`, payload);
            }

            alert("登録しました");
            onSaved();
            onClose();
        } catch (e) {
            alert("登録に失敗しました");
        } finally {
            setSaving(false);
        }
    };

    // UI Helpers
    const toggleGenre = (g) => {
        if (selectedGenres.includes(g)) setSelectedGenres(selectedGenres.filter(x => x !== g));
        else setSelectedGenres([...selectedGenres, g]);
    };

    const toggleType = (t) => {
        if (selectedTypes.includes(t)) setSelectedTypes(selectedTypes.filter(x => x !== t));
        else setSelectedTypes([...selectedTypes, t]);
    };

    // Use channel_id (e.g. "GR17_2080", "BS_101") as primary key for selection
    const getChannelKey = (ch) => {
        return ch.channel;
    };

    // Helper to generate key from EPGProgram (which has channel field)
    const getProgKey = (prog) => {
        return prog.channel;
    }

    const toggleChannel = (ch) => {
        const key = getChannelKey(ch);
        if (selectedChannels.includes(key)) setSelectedChannels(selectedChannels.filter(x => x !== key));
        else setSelectedChannels([...selectedChannels, key]);
    };

    const toggleDay = (d) => {
        if (days.includes(d)) setDays(days.filter(x => x !== d));
        else setDays([...days, d].sort());
    };

    const DOW_LABELS = ['月', '火', '水', '木', '金', '土', '日']; // 0=Mon, ... 6=Sun (Python/JS checks)
    const JS_DOW_LABELS = ['日', '月', '火', '水', '木', '金', '土']; // 0=Sun

    return (
        <div className="fixed inset-0 bg-black/50 z-[90] flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden">
                {/* Header */}
                <div className="p-4 border-b border-gray-200 flex justify-between items-center bg-gray-50">
                    <h2 className="text-xl font-bold text-gray-800">自動予約設定</h2>
                    <button onClick={onClose} className="p-2 hover:bg-gray-200 rounded-full">
                        <X className="w-5 h-5 text-gray-500" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 flex flex-col md:flex-row gap-6 bg-gray-50">

                    {/* Left: Search Conditions */}
                    <div className="flex-1 space-y-6">
                        {/* 1. Name & Keyword */}
                        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 space-y-4">
                            <div>
                                <label className="block text-sm font-bold text-gray-700 mb-1">自動予約名</label>
                                <input type="text" value={name} onChange={e => setName(e.target.value)} className="w-full p-2 border rounded" />
                            </div>
                            <div>
                                <label className="block text-sm font-bold text-gray-700 mb-1">検索キーワード (番組名)</label>
                                <input type="text" value={keyword} onChange={e => setKeyword(e.target.value)} className="w-full p-2 border rounded" placeholder="キーワード検索なし（空欄）" />

                                <div className="mt-2 flex items-center gap-4 text-sm text-gray-700">
                                    <label className="flex items-center gap-1 cursor-pointer">
                                        <input
                                            type="radio"
                                            name="searchTarget"
                                            checked={searchTarget === 'title'}
                                            onChange={() => setSearchTarget('title')}
                                            className="text-blue-600"
                                        />
                                        タイトルのみ
                                    </label>
                                    <label className="flex items-center gap-1 cursor-pointer">
                                        <input
                                            type="radio"
                                            name="searchTarget"
                                            checked={searchTarget === 'title_and_description'}
                                            onChange={() => setSearchTarget('title_and_description')}
                                            className="text-blue-600"
                                        />
                                        タイトルと内容
                                    </label>
                                </div>

                                <div className="text-xs text-gray-500 mt-1">※ 全角半角・大文字小文字は区別されません</div>

                                <div className="mt-4 pt-4 border-t border-gray-100">
                                    <label className="block text-sm font-bold text-gray-700 mb-1">保存先フォルダ</label>
                                    <input type="text" value={folder} onChange={e => setFolder(e.target.value)} className="w-full p-2 border rounded text-sm" placeholder={defaultFolder} />
                                </div>

                                <div className="mt-3 pt-3 border-t border-gray-100">
                                    <label className="flex items-center gap-2 cursor-pointer font-bold text-gray-700">
                                        <input
                                            type="checkbox"
                                            checked={allowDuplicates}
                                            onChange={e => setAllowDuplicates(e.target.checked)}
                                            className="w-5 h-5 text-blue-600"
                                        />
                                        重複予約を許可する
                                    </label>
                                    <div className="text-xs text-gray-500 mt-1 pl-7">
                                        ※OFFにすると、過去に録画済み（または予約中）の同じタイトルの番組は自動予約されません。
                                    </div>
                                </div>
                                
                                <div className="mt-3 pt-3 border-t border-gray-100">
                                    <label className="block text-sm font-bold text-gray-700 mb-1">優先順位 (1=最高)</label>
                                    <div className="flex items-center gap-2">
                                        <input 
                                            type="number" 
                                            min="1" 
                                            max="99" 
                                            value={priority} 
                                            onChange={e => setPriority(e.target.value)} 
                                            className="w-20 p-2 border rounded text-center font-bold"
                                        />
                                        <div className="text-xs text-gray-500">
                                            ※数値が小さいほど優先されます（デフォルト: 5）。<br/>
                                            チューナー不足時、優先度の高い予約が優先されます。
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* 2. Time Search */}
                        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
                            <div>
                                <label className="flex items-center gap-2 cursor-pointer font-bold text-gray-700 mb-2">
                                    <input type="checkbox" checked={enableTime} onChange={e => setEnableTime(e.target.checked)} className="w-5 h-5 text-blue-600" />
                                    時刻検索
                                </label>
                                {enableTime && (
                                    <div className="flex items-center gap-2 pl-6">
                                        <input type="time" value={timeStart} onChange={e => setTimeStart(e.target.value)} className="p-2 border rounded" />
                                        <span>～</span>
                                        <input type="time" value={timeEnd} onChange={e => setTimeEnd(e.target.value)} className="p-2 border rounded" />
                                        <span className="text-xs text-gray-500">※一部でも重なればヒット</span>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* 3. Filters */}
                        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 space-y-4">
                            {/* Days */}
                            <div>
                                <label className="block text-sm font-bold text-gray-700 mb-2">曜日</label>
                                <div className="flex gap-2">
                                    {DOW_LABELS.map((label, idx) => (
                                        <label key={idx} className={`cursor-pointer px-3 py-1 rounded border text-sm font-bold transition select-none ${days.includes(idx) ? 'bg-blue-600 text-white border-blue-600' : 'bg-gray-100 text-gray-500 border-gray-200'}`}>
                                            <input type="checkbox" className="hidden" checked={days.includes(idx)} onChange={() => toggleDay(idx)} />
                                            {label}
                                        </label>
                                    ))}
                                </div>
                            </div>

                            {/* Type */}
                            <div>
                                <label className="block text-sm font-bold text-gray-700 mb-2">放送波</label>
                                <div className="flex gap-2">
                                    {['GR', 'BS', 'CS'].map(t => (
                                        <label key={t} className={`cursor-pointer px-3 py-1 rounded border text-sm font-bold transition select-none ${selectedTypes.includes(t) ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-gray-100 text-gray-500 border-gray-200'}`}>
                                            <input type="checkbox" className="hidden" checked={selectedTypes.includes(t)} onChange={() => toggleType(t)} />
                                            {t}
                                        </label>
                                    ))}
                                </div>
                            </div>

                            {/* Channels (Scrollable) */}
                            <div>
                                <label className="block text-sm font-bold text-gray-700 mb-2">チャンネル</label>
                                <div className="h-32 overflow-y-auto border border-gray-200 rounded p-2 grid grid-cols-2 gap-1 text-sm bg-gray-50">
                                    {allChannelsConfig.map(ch => {
                                        const key = getChannelKey(ch);
                                        return (
                                            <label key={`${ch.channel}_${ch.service_id}`} className="flex items-center gap-2 cursor-pointer hover:bg-gray-200 p-1 rounded">
                                                <input
                                                    type="checkbox"
                                                    checked={selectedChannels.includes(key)}
                                                    onChange={() => toggleChannel(ch)}
                                                    className="w-4 h-4 text-blue-600"
                                                />
                                                <span className="truncate" title={ch.name}>{ch.name}</span>
                                            </label>
                                        );
                                    })}
                                </div>
                                <div className="text-xs text-gray-500 mt-1 text-right">
                                    選択なし = 全チャンネル
                                </div>
                            </div>

                            {/* Genres (Scrollable) */}
                            <div>
                                <label className="block text-sm font-bold text-gray-700 mb-2">ジャンル</label>
                                <div className="h-32 overflow-y-auto border border-gray-200 rounded p-2 grid grid-cols-2 gap-1 text-sm bg-gray-50">
                                    {allGenres.map(g => (
                                        <label key={g} className="flex items-center gap-2 cursor-pointer hover:bg-gray-200 p-1 rounded">
                                            <input
                                                type="checkbox"
                                                checked={selectedGenres.includes(g)}
                                                onChange={() => toggleGenre(g)}
                                                className="w-4 h-4 text-blue-600"
                                            />
                                            <span className="truncate" title={g}>{g}</span>
                                        </label>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Action Buttons removed from here */}
                    </div>

                    {/* Right: Search Results */}
                    <div className="md:w-1/3 flex flex-col gap-4">
                        <button
                            onClick={handleSearch}
                            disabled={searching}
                            className="w-full bg-gray-800 text-white py-3 rounded-lg font-bold shadow hover:bg-gray-700 transition flex justify-center items-center gap-2"
                        >
                            <Search className="w-5 h-5" /> {searching ? '検索中...' : '番組検索'}
                        </button>

                        <div className="flex-1 bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col overflow-hidden">
                            <div className="p-3 border-b border-gray-200 bg-gray-100 font-bold text-gray-700">
                                検索結果
                            </div>
                            <div className="flex-1 overflow-y-auto p-2 space-y-2 max-h-[500px] md:max-h-none">
                                {searching ? (
                                    <div className="text-center p-10 text-gray-500">検索中...</div>
                                ) : searchResults.length === 0 ? (
                                    <div className="text-center p-10 text-gray-400 text-sm">
                                        条件を指定して「番組検索」を押してください。<br />
                                        ※現在時刻以降の番組が対象です
                                    </div>
                                ) : (
                                    searchResults.map(p => {
                                        const sd = new Date(p.start_time);
                                        const ed = new Date(p.end_time);
                                        const dayStr = JS_DOW_LABELS[sd.getDay()];
                                        return (
                                            <div key={p.id} className="p-2 border border-gray-200 rounded text-sm hover:bg-gray-50">
                                                <div className="font-bold text-blue-800 line-clamp-2">{p.title}</div>
                                                <div className="text-xs text-gray-500 mt-1">
                                                    {format(sd, 'MM/dd')} ({dayStr}) {format(sd, 'HH:mm')} - {format(ed, 'HH:mm')}
                                                </div>
                                                <div className="text-xs font-bold text-gray-600 mt-1">{p.service_name || p.channel}</div>
                                            </div>
                                        );
                                    })
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="p-4 border-t border-gray-200 bg-gray-50 flex justify-end gap-3">
                    <button
                        onClick={onClose}
                        className="px-6 py-2 rounded-lg text-gray-600 hover:bg-gray-200 font-bold transition"
                    >
                        キャンセル
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className={`${saving ? 'bg-opacity-70' : ''} px-8 py-2 rounded-lg bg-blue-600 text-white font-bold hover:bg-blue-700 shadow flex items-center gap-2`}
                    >
                        <Save className="w-5 h-5" /> {saving ? '保存中...' : '自動予約登録'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default AutoReservationSettingsModal;
