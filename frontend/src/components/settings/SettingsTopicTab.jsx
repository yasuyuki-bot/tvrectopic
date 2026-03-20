import React from 'react';
import axios from 'axios';
import { Plus, Trash2 } from 'lucide-react';

const SettingsTopicTab = ({ settings, setSettings, topicScanStatus, setTopicScanStatus }) => {
    return (
        <>
            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-purple-500 pl-3">1. 録画ファイルのトピック更新</h3>
                <p className="text-sm text-gray-500 mb-4">
                    録画済みフォルダをスキャンし、新しいトピックを生成します。<br />
                    <span className="text-red-500 font-bold">※再スキャン（トピックの再生成）を行う場合は、対象ファイルの .srt ファイルを削除してから開始してください。</span>
                </p>
                {topicScanStatus.scanning ? (
                    <div className="w-full bg-gray-100 rounded-xl p-4 border border-gray-200 shadow-inner">
                        <div className="mb-3 flex justify-between text-sm font-bold text-purple-800">
                            <span>{topicScanStatus.status}</span>
                            <span className="font-mono">{topicScanStatus.processed} / {topicScanStatus.total}</span>
                        </div>
                        <div className="w-full bg-white rounded-full h-3 mb-3 overflow-hidden border border-purple-100">
                            <div
                                className="bg-purple-600 h-full rounded-full transition-all duration-500 flex items-center justify-end"
                                style={{ width: `${topicScanStatus.total > 0 ? (topicScanStatus.processed / topicScanStatus.total) * 100 : 0}%` }}
                            >
                                <div className="w-1 h-3 bg-white/20"></div>
                            </div>
                        </div>
                        {topicScanStatus.current && (
                            <p className="text-[10px] text-gray-500 truncate font-mono bg-white/50 px-2 py-1 rounded">
                                {topicScanStatus.current}
                            </p>
                        )}
                    </div>
                ) : (
                    <div className="flex flex-col md:flex-row items-stretch gap-3">
                        <div className="flex-1 space-y-1">
                            <label className="text-[10px] font-bold text-gray-400 uppercase ml-1">Gemini Model</label>
                            <input
                                type="text"
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none text-sm font-mono shadow-sm"
                                placeholder="gemini-2.5-flash"
                                value={settings.gemini_model_name || "gemini-2.5-flash"}
                                onChange={(e) => setSettings({ ...settings, gemini_model_name: e.target.value })}
                            />
                            <label className="text-[10px] font-bold text-gray-400 uppercase ml-1 mt-2 block">バッチサイズ (ファイル数)</label>
                            <p className="text-[10px] text-gray-500 mb-1 ml-1">
                                複数のファイルを1つのリクエストにまとめて送信し、APIの呼び出し回数を節約します。
                            </p>
                            <input
                                type="number"
                                min="1"
                                max="20"
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none text-sm font-mono shadow-sm"
                                value={settings.topic_batch_size || 4}
                                onChange={(e) => setSettings({ ...settings, topic_batch_size: parseInt(e.target.value) || 1 })}
                            />
                        </div>
                        <div className="flex items-center gap-4 self-end">
                            <button
                                onClick={async () => {
                                    if (!settings.gemini_api_key) {
                                        alert("Gemini API キーを設定してください。");
                                        return;
                                    }
                                    if (!settings.topic_scan_folders || settings.topic_scan_folders.length === 0 || !settings.topic_scan_folders[0].path) {
                                        alert("スキャン対象フォルダを設定してください。");
                                        return;
                                    }
                                    try {
                                        const apiBase = '/api';
                                        const res = await axios.post(`${apiBase}/scan`, {
                                            model_name: settings.gemini_model_name || "gemini-2.5-flash",
                                            batch_size: settings.topic_batch_size || 4,
                                            api_key: settings.gemini_api_key
                                        });
                                        if (res.data.status === 'started' || res.data.status === 'running') {
                                            setTopicScanStatus(prev => ({ ...prev, scanning: true, status: "Starting..." }));
                                        }
                                    } catch (e) {
                                        alert("スキャンに失敗しました");
                                    }
                                }}
                                className="bg-purple-600 text-white px-8 py-2 rounded-lg shadow-lg hover:bg-purple-700 transition font-bold h-[42px]"
                            >
                                トピックスキャン開始
                            </button>
                        </div>
                    </div>
                )}
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-purple-500 pl-3">2. Gemini API キー</h3>
                <p className="text-sm text-gray-500 mb-3">
                    Google AI Studioで作成したAPIキーを入力してください。
                </p>
                <input
                    type="password"
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 outline-none font-mono text-sm shadow-sm"
                    placeholder="AIzaSy..."
                    value={settings.gemini_api_key || ""}
                    onChange={(e) => setSettings({ ...settings, gemini_api_key: e.target.value })}
                />
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-purple-500 pl-3">3. スキャン対象フォルダ</h3>
                <p className="text-sm text-gray-500 mb-4">
                    トピック生成の対象とするフォルダを指定します。
                </p>
                <div className="space-y-3 mb-4">
                    {(settings.topic_scan_folders || []).map((folder, idx) => (
                        <div key={idx} className="flex flex-col md:flex-row md:items-center gap-3 p-3 bg-gray-50 border border-gray-200 rounded-xl shadow-sm transition hover:border-purple-200">
                            <input
                                type="text"
                                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-purple-500"
                                placeholder="C:\TVRecordings"
                                value={folder.path}
                                onChange={(e) => {
                                    const newFolders = [...(settings.topic_scan_folders || [])];
                                    newFolders[idx] = { ...folder, path: e.target.value };
                                    setSettings({ ...settings, topic_scan_folders: newFolders });
                                }}
                            />
                            <div className="flex items-center gap-3">
                                <label className="flex items-center gap-2 text-sm text-gray-700 bg-white px-3 py-2 rounded-lg border border-gray-200 whitespace-nowrap cursor-pointer hover:bg-gray-50 transition">
                                    <input
                                        type="checkbox"
                                        checked={folder.recursive || false}
                                        onChange={(e) => {
                                            const newFolders = [...(settings.topic_scan_folders || [])];
                                            newFolders[idx] = { ...folder, recursive: e.target.checked };
                                            setSettings({ ...settings, topic_scan_folders: newFolders });
                                        }}
                                        className="w-4 h-4 text-purple-600 rounded"
                                    />
                                    サブフォルダを含む
                                </label>
                                <button
                                    onClick={() => {
                                        const newFolders = [...(settings.topic_scan_folders || [])];
                                        newFolders.splice(idx, 1);
                                        setSettings({ ...settings, topic_scan_folders: newFolders });
                                    }}
                                    className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition"
                                >
                                    <Trash2 className="w-5 h-5" />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
                <button
                    onClick={() => {
                        const newFolders = [...(settings.topic_scan_folders || [])];
                        newFolders.push({ path: "", recursive: false });
                        setSettings({ ...settings, topic_scan_folders: newFolders });
                    }}
                    className="flex items-center gap-1.5 px-4 py-2 bg-purple-50 text-purple-600 rounded-lg hover:bg-purple-100 transition font-bold text-sm"
                >
                    <Plus className="w-4 h-4" /> フォルダを追加
                </button>
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-purple-500 pl-3">4. 自動更新スケジュール (トピック)</h3>
                <p className="text-sm text-gray-500 mb-4">
                    指定した時刻に自動的にトピック生成を行います。
                </p>
                <div className="space-y-6 mb-4">
                    {(settings.topic_schedules || []).map((sched, index) => (
                        <div key={index} className="flex flex-col gap-4 p-5 bg-gray-50 rounded-xl border border-gray-200 shadow-sm transition hover:border-purple-200">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <span className="font-bold text-gray-600 text-sm">時刻:</span>
                                    <input
                                        type="time"
                                        className="px-3 py-1.5 border border-gray-300 rounded-lg font-mono focus:ring-2 focus:ring-purple-500"
                                        value={sched.time || "03:00"}
                                        onChange={(e) => {
                                            const newScheds = [...(settings.topic_schedules || [])];
                                            newScheds[index] = { ...newScheds[index], time: e.target.value };
                                            setSettings({ ...settings, topic_schedules: newScheds });
                                        }}
                                    />
                                </div>
                                <button
                                    onClick={() => {
                                        const newScheds = [...(settings.topic_schedules || [])];
                                        newScheds.splice(index, 1);
                                        setSettings({ ...settings, topic_schedules: newScheds });
                                    }}
                                    className="p-2 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                                >
                                    <Trash2 className="w-5 h-5" />
                                </button>
                            </div>
                            <div className="flex flex-col gap-2">
                                <span className="font-bold text-gray-600 text-sm">曜日:</span>
                                <div className="flex flex-wrap gap-2">
                                    {['月', '火', '水', '木', '金', '土', '日'].map((day, dIndex) => (
                                        <label key={day} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border cursor-pointer transition select-none ${sched.days?.includes(dIndex) ? 'bg-purple-600 border-purple-700 text-white shadow-sm' : 'bg-white border-gray-200 text-gray-500 hover:bg-gray-50'}`}>
                                            <input
                                                type="checkbox"
                                                className="hidden"
                                                checked={(sched.days || []).includes(dIndex)}
                                                onChange={(e) => {
                                                    const newScheds = [...(settings.topic_schedules || [])];
                                                    const currentDays = newScheds[index].days || [];
                                                    if (e.target.checked) {
                                                        newScheds[index].days = [...currentDays, dIndex].sort();
                                                    } else {
                                                        newScheds[index].days = currentDays.filter(d => d !== dIndex);
                                                    }
                                                    setSettings({ ...settings, topic_schedules: newScheds });
                                                }}
                                            />
                                            <span className="text-xs font-bold">{day}</span>
                                        </label>
                                    ))}
                                </div>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <span className="font-bold text-gray-600 text-[10px] uppercase">バッチサイズ</span>
                                    <input
                                        type="number"
                                        className="w-full p-2 border border-gray-300 rounded-lg font-mono focus:ring-2 focus:ring-purple-500"
                                        value={sched.batch_size || 4}
                                        onChange={(e) => {
                                            const newScheds = [...(settings.topic_schedules || [])];
                                            newScheds[index].batch_size = parseInt(e.target.value) || 4;
                                            setSettings({ ...settings, topic_schedules: newScheds });
                                        }}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <span className="font-bold text-gray-600 text-[10px] uppercase">使用モデル</span>
                                    <input
                                        type="text"
                                        className="w-full p-2 border border-gray-300 rounded-lg font-mono focus:ring-2 focus:ring-purple-500"
                                        value={sched.model || "gemini-2.5-flash"}
                                        onChange={(e) => {
                                            const newScheds = [...(settings.topic_schedules || [])];
                                            newScheds[index].model = e.target.value;
                                            setSettings({ ...settings, topic_schedules: newScheds });
                                        }}
                                    />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
                <button
                    onClick={() => {
                        const newScheds = [...(settings.topic_schedules || [])];
                        // Use the current model name from settings or backend default
                        const defaultModel = settings.gemini_model_name || "gemini-2.5-flash";
                        newScheds.push({ time: "03:00", days: [0, 1, 2, 3, 4, 5, 6], batch_size: 4, model: defaultModel });
                        setSettings({ ...settings, topic_schedules: newScheds });
                    }}
                    className="flex items-center gap-1.5 px-4 py-2 bg-purple-50 text-purple-600 rounded-lg hover:bg-purple-100 transition font-bold text-sm"
                >
                    <Plus className="w-4 h-4" /> スケジュールを追加
                </button>
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-purple-500 pl-3">5. 生成プロンプト編集</h3>
                <p className="text-sm text-gray-500 mb-3">
                    トピック生成に使用するプロンプトを編集できます。<br />
                    <code>{`{transcripts}`}</code> は字幕テキストに置換されます。
                </p>
                <textarea
                    className="w-full h-80 px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 outline-none font-mono text-sm shadow-inner bg-gray-50/30"
                    value={settings.topic_prompt || ""}
                    onChange={(e) => setSettings({ ...settings, topic_prompt: e.target.value })}
                />
                <button
                    onClick={async () => {
                        try {
                            const res = await axios.get('/api/settings/defaults');
                            const defaultPrompt = res.data.topic_prompt;
                            setSettings({ ...settings, topic_prompt: defaultPrompt });
                        } catch (e) {
                            alert("デフォルトプロンプトの取得に失敗しました");
                        }
                    }}
                    className="text-xs text-blue-600 hover:text-blue-800 underline mt-2 inline-block transition"
                >
                    デフォルトプロンプトをロード
                </button>
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-purple-500 pl-3">6. MP4自動変換設定</h3>
                <div className="space-y-6">
                    <label className="flex items-start gap-3 cursor-pointer p-4 bg-gray-50 rounded-xl border border-gray-200 hover:bg-purple-50 transition group">
                        <input
                            type="checkbox"
                            checked={settings.auto_mp4_convert || false}
                            onChange={(e) => setSettings({ ...settings, auto_mp4_convert: e.target.checked })}
                            className="w-6 h-6 text-purple-600 rounded-lg focus:ring-purple-500 mt-1"
                        />
                        <div className="flex flex-col">
                            <span className="font-bold text-gray-800 group-hover:text-purple-900 transition font-medium">トピック生成後にMP4へ変換する</span>
                            <span className="text-xs text-gray-500 mt-1">GPUを使用して高速にMP4へ変換します。再生の互換性が向上します。</span>
                        </div>
                    </label>

                    {settings.auto_mp4_convert && (
                        <div className="ml-8 space-y-6 p-5 bg-white rounded-xl border-2 border-purple-100 shadow-sm animate-in fade-in slide-in-from-top-2">
                            <label className="flex items-center gap-3 cursor-pointer select-none">
                                <input
                                    type="checkbox"
                                    checked={settings.delete_ts_after_convert || false}
                                    onChange={(e) => setSettings({ ...settings, delete_ts_after_convert: e.target.checked })}
                                    className="w-5 h-5 text-red-600 rounded-lg focus:ring-red-500 shadow-sm"
                                />
                                <span className="text-red-600 font-bold text-sm">変換後にTSファイルを削除する</span>
                            </label>

                            <div className="space-y-2">
                                <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest block ml-1">FFmpeg変換オプション</label>
                                <input
                                    type="text"
                                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 outline-none font-mono text-xs shadow-inner bg-gray-50/50"
                                    value={settings.mp4_convert_options || "-hwaccel cuda -hwaccel_output_format cuda -vf yadif_cuda -c:v h264_nvenc -preset p4 -rc vbr -cq 22 -qmin 18 -qmax 28 -profile:v high -spatial-aq 1 -temporal-aq 1 -c:a aac"}
                                    onChange={(e) => setSettings({ ...settings, mp4_convert_options: e.target.value })}
                                    placeholder="-hwaccel cuda -hwaccel_output_format cuda -vf yadif_cuda -c:v h264_nvenc -preset p4 -rc vbr -cq 22 -qmin 18 -qmax 28 -profile:v high -spatial-aq 1 -temporal-aq 1 -c:a aac"
                                />
                                <button
                                    onClick={async () => {
                                        try {
                                            const res = await axios.get('/api/settings/ffmpeg-presets');
                                            setSettings({ ...settings, mp4_convert_options: res.data.mp4.cpu });
                                        } catch (e) { alert("プリセットの取得に失敗しました"); }
                                    }}
                                    className="text-[10px] text-blue-600 hover:text-blue-800 underline mt-1 transition inline-block"
                                >
                                    デフォルト設定（CPU）をロード
                                </button>
                                <button
                                    onClick={async () => {
                                        try {
                                            const res = await axios.get('/api/settings/ffmpeg-presets');
                                            setSettings({ ...settings, mp4_convert_options: res.data.mp4.nvenc });
                                        } catch (e) { alert("プリセットの取得に失敗しました"); }
                                    }}
                                    className="text-[10px] text-blue-600 hover:text-blue-800 underline mt-1 ml-4 transition inline-block"
                                >
                                    デフォルト設定（NVENC）をロード
                                </button>
                                <button
                                    onClick={async () => {
                                        try {
                                            const res = await axios.get('/api/settings/ffmpeg-presets');
                                            setSettings({ ...settings, mp4_convert_options: res.data.mp4.qsv });
                                        } catch (e) { alert("プリセットの取得に失敗しました"); }
                                    }}
                                    className="text-[10px] text-blue-600 hover:text-blue-800 underline mt-1 ml-4 transition inline-block"
                                >
                                    デフォルト設定（QSV）をロード
                                </button>

                                <div className="mt-4 p-3 bg-purple-50 rounded-lg text-[10px] text-purple-700 leading-relaxed border border-purple-100">
                                    <p className="font-bold mb-1">内部実行コマンド構成:</p>
                                    <code className="block mb-2">ffmpeg -y [入力オプション] -i [TSパス] [出力オプション] [MP4パス]</code>
                                    <p className="font-bold mb-1">システムが内部で付与するオプション:</p>
                                    <ul className="list-disc pl-4 space-y-0.5">
                                        <li><code>-y</code>: 出力ファイルを上書き確認なしで保存</li>
                                    </ul>
                                    <p className="mt-2 text-[9px] text-purple-600 opacity-80">※<code>-hwaccel</code> 等のハードウェア設定は、上記の「FFmpeg変換オプション」プリセットに含まれています。</p>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </section>
        </>
    );
};

export default SettingsTopicTab;
