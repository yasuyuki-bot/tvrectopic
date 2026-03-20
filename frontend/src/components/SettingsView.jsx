import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Save, Plus, Trash2, Settings, Loader, Trash, RefreshCw, FileText, Calendar, Video, Clock, Bot } from 'lucide-react';

import SettingsEpgTab from './settings/SettingsEpgTab';
import SettingsRecordingTab from './settings/SettingsRecordingTab';
import SettingsTopicTab from './settings/SettingsTopicTab';
import SettingsPlaybackTab from './settings/SettingsPlaybackTab';
import SettingsLogTab from './settings/SettingsLogTab';


const SettingsView = ({ onSave, mode, setMode }) => {
    const [loading, setLoading] = useState(true);
    const [settings, setSettings] = useState({
        epg_duration: {},
        update_times: [],
        font_size: "medium",
        topic_offset_sec: 0,
        filename_format: "",
        ffmpeg_options: "",
        topic_prompt: "",
        topic_schedules: [],
        topic_scan_folders: [],
        gemini_model_name: "",
        auto_mp4_convert: false,
        delete_ts_after_convert: false,
        mp4_convert_options: "",
        video_resume_enabled: true,
        epg_retention_days: 7,
        recdvb_voltage: false,
        recording_command: "recdvb",
        recdvb_path: "/usr/local/bin/recdvb",
        epgdump_path: "/usr/local/bin/epgdump",
    });
    const [channels, setChannels] = useState([]);
    const [saving, setSaving] = useState(false);
    const [activeTab, setActiveTab] = useState('epg');
    const [scanStatus, setScanStatus] = useState({ scanning: false, progress: 0, current_channel: "", results: [] });
    // Topic Scan Status
    const [topicScanStatus, setTopicScanStatus] = useState({ scanning: false, total: 0, processed: 0, status: "idle", current: "" });

    // Log Viewer State
    const [logFiles, setLogFiles] = useState([]);
    const [selectedLogFile, setSelectedLogFile] = useState("");
    const [logs, setLogs] = useState([]);
    const [logsLoading, setLogsLoading] = useState(false);

    // Polling for scan status
    useEffect(() => {
        let interval;
        if (scanStatus.scanning) {
            interval = setInterval(async () => {
                try {
                    const apiBase = '/api';
                    const res = await axios.get(`${apiBase}/settings/scan-status`);
                    setScanStatus(res.data);

                    // If finished, reload channels
                    if (!res.data.scanning && res.data.progress === 100) {
                        const chansRes = await axios.get(`${apiBase}/channels`);
                        const chans = chansRes.data.map(c => ({ ...c, visible: c.visible !== false }));
                        setChannels(chans);
                    }
                } catch (e) {
                    console.error("Poll error", e);
                }
            }, 1000);
        }
        return () => clearInterval(interval);
    }, [scanStatus.scanning]);

    // Polling for Topic Scan Status
    useEffect(() => {
        let interval;
        if (topicScanStatus.scanning) {
            interval = setInterval(async () => {
                try {
                    const apiBase = '/api';
                    const res = await axios.get(`${apiBase}/scan/progress`);
                    setTopicScanStatus(res.data);
                    if (res.data.status === "Complete" || (!res.data.scanning && res.data.total > 0)) {
                        if (res.data.status === "Complete") {
                            setTimeout(() => setTopicScanStatus(prev => ({ ...prev, scanning: false })), 3000);
                        }
                    }
                } catch (e) {
                    console.error("Topic Poll error", e);
                }
            }, 1000);
        }
        return () => clearInterval(interval);
    }, [topicScanStatus.scanning]);

    const handleScan = async () => {
        if (!confirm("地上波チャンネルスキャンを開始しますか？\n現在設定されている地上波チャンネルは上書きされます。")) return;
        try {
            const apiBase = '/api';
            await axios.post(`${apiBase}/settings/scan-channels`);
            setScanStatus({ ...scanStatus, scanning: true, progress: 0, results: [] });
        } catch (e) {
            alert("スキャン開始に失敗しました");
        }
    };

    const [epgStatus, setEpgStatus] = useState({ running: false, progress: 0, current_channel: "" });
    const epgPollRef = useRef(null);

    useEffect(() => {
        if (activeTab === 'epg') {
            const poll = async () => {
                try {
                    const res = await axios.get(`/api/epg/status`);
                    setEpgStatus(res.data);
                } catch (e) { }
            };
            poll(); // Initial
            epgPollRef.current = setInterval(poll, 2000);
        } else {
            if (epgPollRef.current) clearInterval(epgPollRef.current);
        }
        return () => { if (epgPollRef.current) clearInterval(epgPollRef.current); };
    }, [activeTab]);

    // Log Fetching logic
    useEffect(() => {
        if (activeTab === 'log') {
            const fetchLogs = async () => {
                try {
                    setLogsLoading(true);
                    const resFiles = await axios.get('/api/logs/files');
                    setLogFiles(resFiles.data);

                    let targetFile = selectedLogFile;
                    if (!targetFile && resFiles.data.length > 0) {
                        targetFile = resFiles.data.includes("epg_update.log") ? "epg_update.log" : resFiles.data[0];
                        setSelectedLogFile(targetFile);
                    }

                    if (targetFile) {
                        const resContent = await axios.get(`/api/logs/content?filename=${encodeURIComponent(targetFile)}`);
                        setLogs(resContent.data || []);
                    }
                } catch (e) {
                    console.error("Failed to load logs", e);
                } finally {
                    setLogsLoading(false);
                }
            };
            fetchLogs();
        }
    }, [activeTab, selectedLogFile]);

    const handleReloadLog = async () => {
        if (!selectedLogFile) return;
        try {
            setLogsLoading(true);
            const resContent = await axios.get(`/api/logs/content?filename=${encodeURIComponent(selectedLogFile)}`);
            setLogs(resContent.data || []);
        } catch (e) {
            console.error("Failed to reload logs", e);
        } finally {
            setLogsLoading(false);
        }
    };

    useEffect(() => {
        const fetchData = async () => {
            try {
                const apiBase = '/api';
                const [setsRes, chansRes] = await Promise.all([
                    axios.get(`${apiBase}/settings`),
                    axios.get(`${apiBase}/channels`)
                ]);
                console.log("Settings Response:", setsRes.data);
                console.log("Channels Response:", chansRes.data);

                // Merge with existing defaults in state
                setSettings(prev => ({ ...prev, ...(setsRes.data || {}) }));

                // Ensure channels is a list (Robustness check)
                const rawChans = Array.isArray(chansRes.data) ? chansRes.data : [];
                if (!Array.isArray(chansRes.data)) {
                    console.error("Channels API returned non-array data:", chansRes.data);
                }

                // Ensure channels have visible prop (default true if missing)
                const chans = rawChans.map(c => ({ ...c, visible: c.visible !== false }));
                console.log("Processed Channels for state:", chans.length, chans.slice(0, 3));
                setChannels(chans);
            } catch (e) {
                console.error("Failed to load settings Details:", e);
                const errorDetail = e.response?.data?.detail;
                const errorMessage = typeof errorDetail === 'string' ? errorDetail : (e.response?.data?.message || e.message);
                alert("設定の読み込みに失敗しました: " + errorMessage);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const handleSave = async (silent = false) => {
        setSaving(true);
        try {
            const apiBase = '/api';

            // 1. Save Settings
            await axios.post(`${apiBase}/settings`, settings);

            // 2. Save Channels Config
            const channelsConfig = channels.map(c => ({
                service_id: c.service_id,
                network_id: c.network_id || c.onid,
                channel: c.channel,
                type: c.type,
                visible: c.visible
            }));
            await axios.post(`${apiBase}/channels/config`, channelsConfig);

            if (!silent) alert("保存しました");
            onSave(settings); // Pass back new settings
            return true;
        } catch (e) {
            console.error("Save failed", e);
            if (!silent) alert("保存に失敗しました");
            return false;
        } finally {
            setSaving(false);
        }
    };

    const handleTimeAdd = () => {
        setSettings({ ...settings, update_times: [...settings.update_times, "00:00"] });
    };

    const handleTimeChange = (idx, val) => {
        const newTimes = [...settings.update_times];
        newTimes[idx] = val;
        setSettings({ ...settings, update_times: newTimes });
    };

    const handleTimeRemove = (idx) => {
        const newTimes = settings.update_times.filter((_, i) => i !== idx);
        setSettings({ ...settings, update_times: newTimes });
    };

    const toggleChannel = (idx) => {
        const newChannels = [...channels];
        newChannels[idx].visible = !newChannels[idx].visible;
        setChannels(newChannels);
    };

    const handleDeleteChannel = async (idx, channelId) => {
        if (!confirm("このチャンネルを削除しますか？\n(削除後、EPG番組表からも消去されます)")) return;
        try {
            await axios.delete(`/api/channels/${channelId}`);
            const newChannels = channels.filter((_, i) => i !== idx);
            setChannels(newChannels);
            alert("削除しました");
            // Also save current settings to reflect change immediately if necessary
            handleSave(true);
        } catch (e) {
            console.error("Delete failed", e);
            alert("削除に失敗しました");
        }
    };

    if (loading) return (
        <div className="h-full flex items-center justify-center bg-white">
            <Loader className="w-8 h-8 animate-spin text-blue-600" />
        </div>
    );

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
                    onClick={() => handleSave(false)}
                    disabled={saving}
                    className={`flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-bold shadow hover:bg-blue-700 transition shrink-0 ${saving ? 'opacity-50' : ''}`}
                >
                    <Save className="w-3.5 h-3.5" /> {saving ? '...' : '保存'}
                </button>
            </div>

            {/* Header */}
            <div className="p-3 md:p-4 border-b border-gray-200 bg-white shadow-sm flex flex-col md:flex-row items-center justify-between gap-4 landscape-hide">
                <div className="flex items-center gap-2 self-start md:self-auto">
                    <Settings className="w-5 h-5 md:w-6 md:h-6 text-gray-600" />
                    <h2 className="text-lg md:text-xl font-bold text-gray-800">設定</h2>
                </div>
                <button
                    onClick={() => handleSave(false)}
                    disabled={saving}
                    className={`w-full md:w-auto flex items-center justify-center gap-2 px-6 py-2 rounded-lg bg-blue-600 text-white font-bold hover:bg-blue-700 shadow-sm transition ${saving ? 'opacity-50' : ''}`}
                >
                    <Save className="w-5 h-5" />
                    {saving ? '保存中...' : '設定を保存'}
                </button>
            </div>


            {/* Content Tabs */}
            <div className="flex border-b border-gray-200 px-2 md:px-6 bg-white shrink-0 overflow-hidden">

                <button
                    className={`py-4 px-6 font-bold transition border-b-2 -mb-px ${activeTab === 'epg' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                    onClick={() => setActiveTab('epg')}
                >
                    EPG
                </button>
                <button
                    className={`py-4 px-6 font-bold transition border-b-2 -mb-px ${activeTab === 'recording' ? 'border-red-600 text-red-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                    onClick={() => setActiveTab('recording')}
                >
                    録画設定
                </button>
                <button
                    className={`py-4 px-6 font-bold transition border-b-2 -mb-px ${activeTab === 'topic' ? 'border-purple-600 text-purple-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                    onClick={() => setActiveTab('topic')}
                >
                    トピック
                </button>
                <button
                    className={`py-4 px-6 font-bold transition border-b-2 -mb-px ${activeTab === 'playback' ? 'border-green-600 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                    onClick={() => setActiveTab('playback')}
                >
                    再生
                </button>
                <button
                    className={`py-4 px-6 font-bold transition border-b-2 -mb-px ${activeTab === 'log' ? 'border-orange-600 text-orange-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                    onClick={() => setActiveTab('log')}
                >
                    ログ
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-3 md:p-6">
                <div className="max-w-4xl mx-auto space-y-8 md:space-y-12 bg-white p-4 md:p-8 rounded-xl shadow-sm border border-gray-200 mb-20 md:mb-6">

                    {activeTab === 'epg' && (
                        <SettingsEpgTab
                            settings={settings}
                            setSettings={setSettings}
                            epgStatus={epgStatus}
                            scanStatus={scanStatus}
                            channels={channels}
                            setChannels={setChannels}
                            handleSave={handleSave}
                            handleScan={handleScan}
                            handleTimeAdd={handleTimeAdd}
                            handleTimeChange={handleTimeChange}
                            handleTimeRemove={handleTimeRemove}
                            toggleChannel={toggleChannel}
                            handleDeleteChannel={handleDeleteChannel}
                        />
                    )}

                    {activeTab === 'recording' && (
                        <SettingsRecordingTab
                            settings={settings}
                            setSettings={setSettings}
                        />
                    )}

                    {activeTab === 'topic' && (
                        <SettingsTopicTab
                            settings={settings}
                            setSettings={setSettings}
                            topicScanStatus={topicScanStatus}
                            setTopicScanStatus={setTopicScanStatus}
                        />
                    )}

                    {activeTab === 'playback' && (
                        <SettingsPlaybackTab
                            settings={settings}
                            setSettings={setSettings}
                        />
                    )}

                    {activeTab === 'log' && (
                        <SettingsLogTab
                            logFiles={logFiles}
                            selectedLogFile={selectedLogFile}
                            setSelectedLogFile={setSelectedLogFile}
                            logs={logs}
                            logsLoading={logsLoading}
                            handleReloadLog={handleReloadLog}
                        />
                    )}
                </div>
            </div>
        </div >
    );
};

export default SettingsView;
