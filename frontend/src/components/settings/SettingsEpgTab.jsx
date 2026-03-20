import React from 'react';
import axios from 'axios';
import { Plus, Trash2 } from 'lucide-react';

const SettingsEpgTab = ({
    settings,
    setSettings,
    epgStatus,
    scanStatus,
    channels,
    setChannels,
    handleSave,
    handleScan,
    handleTimeAdd,
    handleTimeChange,
    handleTimeRemove,
    toggleChannel,
    handleDeleteChannel
}) => {
    return (
        <>
            {/* 1. EPG Update */}
            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-blue-500 pl-3">1. EPG手動更新</h3>
                <p className="text-sm text-gray-500 mb-3">
                    すぐにEPGデータを更新します。
                </p>
                {!epgStatus.running ? (
                    <button
                        onClick={async () => {
                            if (confirm("EPGを更新しますか？\n(入力中の設定は自動的に保存されます)")) {
                                // Auto-save silently before updating
                                const saved = await handleSave(true);
                                if (!saved) return;

                                try {
                                    await axios.post(`/api/epg/update`);
                                }
                                catch (e) { alert("更新に失敗しました"); }
                            }
                        }}
                        className="bg-blue-600 text-white px-5 py-2.5 rounded-lg shadow hover:bg-blue-700 transition font-bold"
                    >
                        更新開始
                    </button>
                ) : (
                    <div className="bg-blue-50 p-4 rounded-xl border border-blue-100 animate-pulse">
                        <div className="flex justify-between items-center mb-2">
                            <span className="font-bold text-blue-800">更新中...</span>
                            <div className="flex items-center gap-3">
                                <button
                                    onClick={async () => {
                                        if (confirm("EPG更新を中断しますか？\n(現在実行中のチャンネルの処理が終わり次第停止します)")) {
                                            try {
                                                await axios.post(`/api/epg/cancel`);
                                            } catch (e) { alert("キャンセルに失敗しました"); }
                                        }
                                    }}
                                    className="text-[11px] bg-red-100 text-red-600 px-2.5 py-1 rounded-full hover:bg-red-200 transition font-bold border border-red-200 animate-none"
                                >
                                    キャンセル
                                </button>
                                <span className="text-blue-600 font-mono">{epgStatus.progress}%</span>
                            </div>
                        </div>
                        <div className="w-full bg-blue-200 rounded-full h-2.5 mb-2 overflow-hidden">
                            <div className="bg-blue-600 h-2.5 rounded-full transition-all duration-500" style={{ width: `${epgStatus.progress}%` }}></div>
                        </div>
                        <p className="text-sm text-blue-600">処理中: {epgStatus.current_channel}</p>
                    </div>
                )}
            </section>

            {/* 2. Tuner Counts */}
            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-blue-500 pl-3">2. チューナー数設定</h3>
                <p className="text-sm text-gray-500 mb-3">使用可能な物理チューナー数を設定してください。</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-blue-50/50 p-4 rounded-xl border border-blue-100 flex flex-col">
                        <label className="text-xs font-bold text-blue-700 mb-2 uppercase tracking-wide">地デジ (GR)</label>
                        <input
                            type="number"
                            min="0"
                            className="w-full px-3 py-2 text-center border border-blue-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-bold text-xl"
                            value={settings.tuner_count_gr ?? 2}
                            onChange={(e) => setSettings({ ...settings, tuner_count_gr: parseInt(e.target.value) || 0 })}
                        />
                    </div>
                    <div className="bg-red-50/50 p-4 rounded-xl border border-red-100 flex flex-col">
                        <label className="text-xs font-bold text-red-700 mb-2 uppercase tracking-wide">BS/CS</label>
                        <input
                            type="number"
                            min="0"
                            className="w-full px-3 py-2 text-center border border-red-200 rounded-lg focus:ring-2 focus:ring-red-500 outline-none font-bold text-xl"
                            value={settings.tuner_count_bs_cs ?? 2}
                            onChange={(e) => setSettings({ ...settings, tuner_count_bs_cs: parseInt(e.target.value) || 0 })}
                        />
                    </div>
                    <div className="bg-purple-50/50 p-4 rounded-xl border border-purple-100 flex flex-col">
                        <label className="text-xs font-bold text-purple-700 mb-2 uppercase tracking-wide">共用 (Reserved)</label>
                        <input
                            type="number"
                            min="0"
                            className="w-full px-3 py-2 text-center border border-purple-200 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none font-bold text-xl"
                            value={settings.tuner_count_shared ?? 0}
                            onChange={(e) => setSettings({ ...settings, tuner_count_shared: parseInt(e.target.value) || 0 })}
                        />
                    </div>
                </div>
            </section>

            {/* 3. Terrestrial Channel Scan */}
            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-blue-500 pl-3">3. 地上波チャンネルスキャン</h3>
                <p className="text-sm text-gray-500 mb-3">地上波チャンネルをスキャンして自動設定します。</p>

                <div className="space-y-4">
                    {!scanStatus.scanning ? (
                        <button
                            onClick={handleScan}
                            className="bg-blue-600 text-white px-5 py-2.5 rounded-lg shadow hover:bg-blue-700 transition font-bold"
                        >
                            スキャン開始
                        </button>
                    ) : (
                        <div className="bg-blue-50 p-4 rounded-xl border border-blue-100 animate-pulse">
                            <div className="flex justify-between mb-2">
                                <span className="font-bold text-blue-800">スキャン中...</span>
                                <span className="text-blue-600 font-mono">{scanStatus.progress}%</span>
                            </div>
                            <div className="w-full bg-blue-200 rounded-full h-2.5 mb-2 overflow-hidden">
                                <div className="bg-blue-600 h-2.5 rounded-full transition-all duration-500" style={{ width: `${scanStatus.progress}%` }}></div>
                            </div>
                            <p className="text-sm text-blue-600">現在: {scanStatus.current_channel}ch</p>
                        </div>
                    )}

                    {/* Results Preview (Live) */}
                    {scanStatus.results && scanStatus.results.length > 0 && (
                        <div className="mt-4 border border-gray-200 rounded-xl overflow-hidden bg-gray-50 p-3 shadow-inner max-h-60 overflow-y-auto">
                            <h4 className="text-xs font-bold text-gray-500 mb-3 uppercase tracking-wider">検出されたチャンネル</h4>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                                {scanStatus.results.map((r, i) => (
                                    <div key={i} className="flex justify-between items-center bg-white p-2.5 rounded-lg shadow-sm text-sm border border-gray-100">
                                        <span className="font-bold text-gray-800 truncate mr-2">{r.service_name}</span>
                                        <span className="text-blue-600 font-mono text-xs bg-blue-50 px-1.5 py-0.5 rounded uppercase">{r.channel}ch</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </section>

            {/* 4. EPG Duration */}
            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-blue-500 pl-3">4. EPG取得時間（秒）</h3>
                <div className="flex flex-wrap gap-6">
                    {['GR', 'BS', 'CS'].map(type => (
                        <div key={type} className="flex flex-col">
                            <label className="text-xs font-bold text-gray-500 mb-1.5 uppercase tracking-wide">{type}</label>
                            <input
                                type="number"
                                className="w-28 px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                                value={settings.epg_duration?.[type] || 0}
                                onChange={(e) => setSettings({
                                    ...settings,
                                    epg_duration: { ...(settings.epg_duration || {}), [type]: parseInt(e.target.value) || 0 }
                                })}
                            />
                        </div>
                    ))}
                </div>
            </section>

            {/* 5. Update Times */}
            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-blue-500 pl-3">5. EPG更新時刻</h3>
                <div className="flex flex-wrap gap-4">
                    {(settings.update_times || []).map((time, idx) => (
                        <div key={idx} className="flex items-center gap-2 bg-gray-50 p-2.5 rounded-lg border border-gray-200">
                            <input
                                type="time"
                                className="px-2 py-1 border border-gray-300 rounded-md font-mono outline-none focus:ring-2 focus:ring-blue-500"
                                value={time}
                                onChange={(e) => handleTimeChange(idx, e.target.value)}
                            />
                            <button onClick={() => handleTimeRemove(idx)} className="text-red-400 hover:text-red-600 p-1 transition">
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                    ))}
                    <button onClick={handleTimeAdd} className="flex items-center gap-1.5 px-4 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition font-bold text-sm">
                        <Plus className="w-4 h-4" /> 時刻を追加
                    </button>
                </div>
            </section>

            {/* 6. EPG Retention */}
            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-blue-500 pl-3">6. 過去番組の保存期間 (日)</h3>
                <p className="text-sm text-gray-500 mb-3">
                    指定した日数より前の過去番組表データを自動的に削除します。<br />
                    0 に設定すると無制限に保持します（最大 30日）。
                </p>
                <div className="flex items-center gap-2">
                    <input
                        type="number"
                        min="0"
                        max="30"
                        className="w-24 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                        value={settings.epg_retention_days ?? 7}
                        onChange={(e) => setSettings({ ...settings, epg_retention_days: parseInt(e.target.value) || 0 })}
                    />
                    <span className="text-gray-600 font-bold">日分</span>
                </div>
            </section>

            {/* 7. Font Size */}
            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-blue-500 pl-3">7. 番組表の表示設定</h3>
                <div className="max-w-xs space-y-2">
                    <label className="text-xs font-bold text-gray-500 uppercase tracking-wider block">フォントサイズ</label>
                    <select
                        className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none bg-white font-medium"
                        value={settings.font_size}
                        onChange={(e) => setSettings({ ...settings, font_size: e.target.value })}
                    >
                        <option value="small">小 (Small)</option>
                        <option value="medium">中 (Medium - Default)</option>
                        <option value="large">大 (Large)</option>
                        <option value="xlarge">特大 (Extra Large)</option>
                    </select>
                </div>
            </section>

            {/* 8. Channel Map */}
            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-blue-500 pl-3">8. チャンネルマップ ({channels.length}件)</h3>
                <p className="text-sm text-gray-500 mb-4">チェックを外したチャンネルは番組表（EPG）に表示されません。</p>
                <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm max-h-[600px] overflow-y-auto overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="text-[11px] text-gray-500 uppercase bg-gray-50 sticky top-0 font-bold border-b border-gray-200">
                            <tr>
                                <th className="px-4 py-3 w-16 text-center">表示</th>
                                <th className="px-4 py-3">Type</th>
                                <th className="px-4 py-3">チャンネル名</th>
                                <th className="px-4 py-3">Ch</th>
                                <th className="px-4 py-3">Slot</th>
                                <th className="px-4 py-3">Service ID</th>
                                <th className="px-4 py-3 w-16 text-center">削除</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100 font-medium">
                            {channels.map((ch, idx) => (
                                <tr key={`${ch.type}-${ch.service_id}-${idx}`} className="hover:bg-gray-50 transition-colors">
                                    <td className="px-4 py-3 text-center">
                                        <input
                                            type="checkbox"
                                            checked={ch.visible}
                                            onChange={() => toggleChannel(idx)}
                                            className="w-5 h-5 text-blue-600 rounded-lg border-gray-300 focus:ring-blue-500 cursor-pointer"
                                        />
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className={`px-2 py-0.5 rounded-full text-[10px] uppercase font-bold border ${ch.type === 'GR' ? 'bg-green-50 text-green-700 border-green-200' : ch.type === 'BS' ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-purple-50 text-purple-700 border-purple-200'}`}>
                                            {ch.type}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 font-bold text-gray-900">{ch.name || ch.service_name}</td>
                                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{ch.TP || ch.channel || ch.channel_id || (ch.type !== 'GR' ? '-' : '')}</td>
                                    <td className="px-4 py-3 text-gray-400 font-mono text-xs">{ch.slot ?? '-'}</td>
                                    <td className="px-4 py-3 font-mono text-xs text-gray-400">{ch.service_id || ch.sid}</td>
                                    <td className="px-4 py-3 text-center">
                                        <button
                                            onClick={() => handleDeleteChannel(idx, ch.id)}
                                            className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                                            title="チャンネルを削除"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </>
    );
};

export default SettingsEpgTab;
