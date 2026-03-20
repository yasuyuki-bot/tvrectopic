import React from 'react';
import axios from 'axios';

const SettingsPlaybackTab = ({ settings, setSettings }) => {
    return (
        <>
            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-green-500 pl-3">1. トピック再生オフセット</h3>
                <p className="text-sm text-gray-500 mb-4">
                    トピック再生開始時に、指定した秒数だけ再生位置を調整します。<br />
                    （マイナスで手前から、プラスで後ろから再生開始）
                </p>
                <div className="flex items-center gap-3 bg-gray-50 p-4 rounded-xl border border-gray-200 max-w-xs">
                    <input
                        type="number"
                        className="w-24 px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 outline-none font-bold text-lg"
                        value={settings.topic_offset_sec || 0}
                        onChange={(e) => setSettings({ ...settings, topic_offset_sec: parseInt(e.target.value) || 0 })}
                    />
                    <span className="text-gray-600 font-bold">秒のオフセット</span>
                </div>
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-green-500 pl-3">2. レジューム再生</h3>
                <p className="text-sm text-gray-500 mb-4">
                    録画済み番組を再生する際、前回停止した位置から再開します。<br />
                    （トピック検索からの再生時は適用されません。また、ブラウザ単位で保存されるため、デバイス間では同期されません）
                </p>
                <div className="flex flex-col gap-3">
                    <label className="flex items-center gap-3 cursor-pointer p-4 bg-gray-50 rounded-xl border border-gray-200 hover:bg-green-50 transition group max-w-sm">
                        <input
                            type="checkbox"
                            checked={settings.video_resume_enabled ?? true}
                            onChange={(e) => setSettings({ ...settings, video_resume_enabled: e.target.checked })}
                            className="w-6 h-6 text-green-600 rounded-lg focus:ring-green-500 shadow-sm"
                        />
                        <span className="font-bold text-gray-800 group-hover:text-green-900 transition font-medium">レジューム機能を有効にする</span>
                    </label>

                    <label className={`flex items-center gap-3 p-4 rounded-xl border transition group max-w-sm ${settings.video_resume_enabled ? 'bg-gray-50 border-gray-200 cursor-pointer hover:bg-green-50' : 'bg-gray-100 border-gray-100 opacity-50 cursor-not-allowed'}`}>
                        <input
                            type="checkbox"
                            disabled={!settings.video_resume_enabled}
                            checked={settings.video_resume_sync_enabled ?? false}
                            onChange={(e) => setSettings({ ...settings, video_resume_sync_enabled: e.target.checked })}
                            className="w-6 h-6 text-green-600 rounded-lg focus:ring-green-500 shadow-sm"
                        />
                        <div className="flex flex-col">
                            <span className="font-bold text-gray-800 group-hover:text-green-900 transition font-medium">デバイス間で同期する</span>
                            <span className="text-[10px] text-gray-500">※再生位置をサーバーに保存し、他のデバイスと共有します。</span>
                        </div>
                    </label>
                </div>
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-green-500 pl-3">3. FFmpegコマンドオプション</h3>
                <p className="text-sm text-gray-500 mb-4 leading-relaxed">
                    トランスコード再生時に使用するFFmpegの出力オプションです。MPEG-2 TS等の再生時に使用されます。<br />
                    <span className="text-xs text-gray-400">環境に合わせて調整してください。</span>
                </p>
                <div className="bg-gray-100 p-3 rounded text-xs text-gray-600 space-y-2 mb-3">
                    <p><strong>内部実行コマンド構成:</strong><br />
                        <code>ffmpeg [基本設定/解析向上] [ハードウェア初期化] [入力オプション] [Seek -ss] [Pacing] [追っかけ再生用] -i [入力/Stdin] [継続再生/GOP等] [Mapping/Filters] [出力オプション] -f mpegts -</code></p>
                    <p><strong>GPU利用時のオプション順序について:</strong><br />
                        入力欄のオプションは自動的に解析・分割されます。<code>-hwaccel</code>, <code>-c:v ..._qsv</code>（デコード等）は<strong>入力（-i の前）</strong>に、
                        <code>-c:v ..._nvenc</code>（エンコード）や <code>-vf</code>（フィルタ）は<strong>出力（-i の後）</strong>に配置されます。</p>
                    <div className="mt-2 border-t border-gray-300 pt-2 grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <p className="font-bold mb-1 text-blue-700 underline">録画再生時に自動挿入:</p>
                            <p className="mb-1 text-[9px] text-gray-500">※システムが自動的にコマンドを構成します</p>
                            <ul className="list-disc pl-4 space-y-1 text-[10px]">
                                <li><code>-probesize 15M / -analyzeduration 5M</code> : 解析強化</li>
                                <li><code>-fflags +genpts+igndts+discardcorrupt</code> : タイムスタンプ正規化</li>
                                <li><code>-re</code> : 等速転送（低速回線時などに適用）</li>
                                <li><code>-f mpegts -follow 1</code> : 追っかけ再生（録画中のみ）</li>
                                <li><code>-ss [秒]</code> : 入力シーク（高速アクセス）</li>
                                <li><code>-g 60 -avoid_negative_ts make_zero</code> : GOP正規化</li>
                                <li><code>-map 0:v / -map 0:a</code> : ストリーム選択</li>
                            </ul>
                        </div>
                        <div>
                            <p className="font-bold mb-1 text-red-700 underline">ライブ視聴時に自動挿入:</p>
                            <p className="mb-1 text-[9px] text-gray-500">※超低遅延および配信安定化のために挿入されます</p>
                            <ul className="list-disc pl-4 space-y-1 text-[10px]">
                                <li><code>-probesize 1M / -analyzeduration 1M</code> : 解析バッファ最小化</li>
                                <li><code>-fflags +genpts+discardcorrupt+nobuffer</code> : 遅延防止フラグ</li>
                                <li><code>-err_detect ignore_err</code> : 転送エラー無視</li>
                                <li><code>-map 0:p:SID:v:0 / -map 0:p:SID:a:n</code> : サービス抽出</li>
                                <li><code>-ac 2</code> : ステレオ2ch化</li>
                                <li><code>-loglevel error</code> : ログ出力抑制</li>
                            </ul>
                        </div>
                    </div>
                </div>
                <div className="space-y-3">
                    <textarea
                        className="w-full h-32 px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 outline-none font-mono text-sm shadow-inner bg-gray-50/30"
                        value={settings.ffmpeg_options || ""}
                        onChange={(e) => setSettings({ ...settings, ffmpeg_options: e.target.value })}
                        placeholder="-vf hwupload_cuda,yadif_cuda -c:v h264_nvenc ..."
                    />
                    <button
                        onClick={async () => {
                            try {
                                const res = await axios.get('/api/settings/ffmpeg-presets');
                                setSettings({ ...settings, ffmpeg_options: res.data.playback.cpu });
                            } catch (e) { alert("プリセットの取得に失敗しました"); }
                        }}
                        className="text-xs text-blue-600 hover:text-blue-800 underline transition"
                    >
                        デフォルト設定（CPU）をロード
                    </button>
                    <button
                        onClick={async () => {
                            try {
                                const res = await axios.get('/api/settings/ffmpeg-presets');
                                setSettings({ ...settings, ffmpeg_options: res.data.playback.nvenc });
                            } catch (e) { alert("プリセットの取得に失敗しました"); }
                        }}
                        className="text-xs text-blue-600 hover:text-blue-800 underline transition ml-4"
                    >
                        デフォルト設定（NVENC）をロード
                    </button>
                    <button
                        onClick={async () => {
                            try {
                                const res = await axios.get('/api/settings/ffmpeg-presets');
                                setSettings({ ...settings, ffmpeg_options: res.data.playback.qsv });
                            } catch (e) { alert("プリセットの取得に失敗しました"); }
                        }}
                        className="text-xs text-blue-600 hover:text-blue-800 underline transition ml-4"
                    >
                        デフォルト設定（QSV）をロード
                    </button>
                </div>
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-green-500 pl-3">4. アダプティブ・ストリーミング</h3>
                <p className="text-sm text-gray-500 mb-4">
                    再生開始やシーク時のレスポンスを向上させつつ、過剰なバッファリングを防ぎます。<br />
                    <span className="text-red-500 font-bold">※再生が頻繁に止まる、または不安定な場合はOFFにしてください。</span>
                </p>
                <label className="flex flex-col gap-3 p-4 bg-gray-50 rounded-xl border border-gray-200 hover:bg-green-50 transition group max-w-lg cursor-pointer">
                    <div className="flex items-center gap-3">
                        <input
                            type="checkbox"
                            checked={settings.adaptive_streaming_enabled ?? true}
                            onChange={(e) => setSettings({ ...settings, adaptive_streaming_enabled: e.target.checked })}
                            className="w-6 h-6 text-green-600 rounded-lg focus:ring-green-500 shadow-sm"
                        />
                        <span className="font-bold text-gray-800 group-hover:text-green-900 transition font-medium">アダプティブ・ストリーミングを有効にする</span>
                    </div>
                    <div className="pl-9 text-xs text-gray-500 space-y-1">
                        <p><strong>OFF時:</strong> FFmpegの <code>-re</code> オプションにより常に等速で転送します。</p>
                        <p><strong>ON時:</strong> ブラウザのバッファ（⚡︎）量に応じて、下記のように転送量をアクティブに制御します。</p>
                        <ul className="list-disc pl-4 space-y-0.5 mt-1 text-[11px]">
                            <li><strong>25秒以上:</strong> 5Mbps（バッファ維持）</li>
                            <li><strong>15秒以上:</strong> 20Mbps（定常転送）</li>
                            <li><strong>3秒以上:</strong> 40Mbps（リカバリー転送）</li>
                            <li><strong>3秒以下 / 初期10MB:</strong> 無制限（最高速バースト）</li>
                        </ul>
                    </div>
                </label>
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-green-500 pl-3">5. ライブ視聴用 QSVデバイスパス</h3>
                <p className="text-sm text-gray-500 mb-4">
                    ライブ視聴（QSV）で使用するデバイスパスを指定します。<br />
                    <span className="text-xs text-gray-400">デフォルト: <code>/dev/dri/renderD128</code> (空欄の場合)</span>
                </p>
                <input
                    type="text"
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 outline-none font-mono text-sm shadow-sm"
                    value={settings.qsv_device_path || ""}
                    onChange={(e) => setSettings({ ...settings, qsv_device_path: e.target.value })}
                    placeholder="/dev/dri/renderD128"
                />
            </section>
        </>
    );
};

export default SettingsPlaybackTab;
