import React from 'react';

const SettingsRecordingTab = ({ settings, setSettings }) => {
    return (
        <>
            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-red-500 pl-3">1. 保存先フォルダ</h3>
                <p className="text-sm text-gray-500 mb-3">録画したファイルを保存するフォルダ（絶対パス）を指定します。</p>
                <input
                    type="text"
                    className="w-full px-4 py-3.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 outline-none font-mono text-sm shadow-sm"
                    value={settings.recording_folder || ""}
                    onChange={(e) => setSettings({ ...settings, recording_folder: e.target.value })}
                />
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-red-500 pl-3">2. ファイル名形式</h3>
                <p className="text-sm text-gray-500 mb-3 leading-relaxed">
                    使用可能な変数: <code>{'{Title}'}</code>, <code>{'{Date}'}</code>, <code>{'{Time}'}</code>, <code>{'{EndDate}'}</code>, <code>{'{EndTime}'}</code>, <code>{'{Channel}'}</code>, <code>{'{SID}'}</code>, <code>{'{ServiceName}'}</code><br />
                    <span className="text-xs">例: <code>{'{Title}_{Date}_{Time}_{ServiceName}.ts'}</code></span>
                </p>
                <input
                    type="text"
                    className="w-full px-4 py-3.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 outline-none font-mono text-sm shadow-sm"
                    value={settings.filename_format || "{Title}_{Date}_{Time}_{Channel}.ts"}
                    onChange={(e) => setSettings({ ...settings, filename_format: e.target.value })}
                />
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-red-500 pl-3">3. recdvb 電圧給電 (LNB 15V)</h3>
                <p className="text-sm text-gray-500 mb-4 leading-relaxed">
                    BS/CSアンテナへ給電が必要な環境の場合、有効にしてください。録画コマンドに <code>--lnb 15</code> を追加します。
                </p>
                <label className="flex items-center gap-3 cursor-pointer p-4 bg-gray-50 rounded-xl border border-gray-200 hover:bg-red-50 transition group max-w-sm">
                    <input
                        type="checkbox"
                        checked={settings.recdvb_voltage || false}
                        onChange={(e) => setSettings({ ...settings, recdvb_voltage: e.target.checked })}
                        className="w-6 h-6 text-red-600 rounded-lg focus:ring-red-500 shadow-sm"
                    />
                    <span className="font-bold text-gray-800 group-hover:text-red-900 transition">電圧給電を有効にする</span>
                </label>
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-red-500 pl-3">4. 録画開始マージン (秒)</h3>
                <p className="text-sm text-gray-500 mb-3 leading-relaxed">
                    予約時刻の何秒前から録画を開始するか設定します（デフォルト2秒）。<br />
                    <span className="text-red-600 font-bold">※短くしすぎると冒頭が切れる可能性がありますが、長くしすぎると前の番組との競合（チューナー不足）の原因になります。</span>
                </p>
                <div className="flex items-center gap-2">
                    <input
                        type="number"
                        min="0"
                        max="60"
                        className="w-24 px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 outline-none font-bold text-lg text-center shadow-sm"
                        value={settings.recording_start_margin ?? 2}
                        onChange={(e) => setSettings({ ...settings, recording_start_margin: parseInt(e.target.value) || 0 })}
                    />
                    <span className="font-bold text-gray-600">秒</span>
                </div>
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-red-500 pl-3">5. 連続録画時の終了マージン (秒)</h3>
                <p className="text-sm text-gray-500 mb-3 leading-relaxed">
                    ある録画の終了時刻と次の録画の開始時刻が同じ場合、前の録画の終了時刻をこの秒数だけ早めます（チューナーの切り替え時間を確保するため）。<br />
                    デフォルト3秒。0の場合はマージンを適用しません。
                </p>
                <div className="flex items-center gap-2">
                    <input
                        type="number"
                        min="0"
                        max="30"
                        className="w-24 px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 outline-none font-bold text-lg text-center shadow-sm"
                        value={settings.recording_margin_end ?? 3}
                        onChange={(e) => setSettings({ ...settings, recording_margin_end: parseInt(e.target.value) || 0 })}
                    />
                    <span className="font-bold text-gray-600">秒</span>
                </div>
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-red-500 pl-3">6. 録画システム・実行ファイルパス</h3>
                <div className="space-y-4">
                    <div>
                        <p className="text-sm text-gray-500 mb-2">使用する録画システムを選択してください。</p>
                        <select
                            className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 outline-none font-medium bg-white shadow-sm"
                            value={settings.recording_command || "recdvb"}
                            onChange={(e) => {
                                const newCmd = e.target.value;
                                const curPath = settings.recdvb_path || "";
                                let newPath = curPath;
                                if (newCmd === "recpt1" && (curPath === "/usr/local/bin/recdvb" || curPath === "")) {
                                    newPath = "/usr/local/bin/recpt1";
                                } else if (newCmd === "recdvb" && (curPath === "/usr/local/bin/recpt1" || curPath === "")) {
                                    newPath = "/usr/local/bin/recdvb";
                                }
                                setSettings({ ...settings, recording_command: newCmd, recdvb_path: newPath });
                            }}
                        >
                            <option value="recdvb">recdvb</option>
                            <option value="recpt1">recpt1</option>
                        </select>
                    </div>
                    <div>
                        <p className="text-sm text-gray-500 mb-2">録画コマンド（バイナリ）の絶対パスを指定します。</p>
                        <input
                            type="text"
                            className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 outline-none font-mono text-sm shadow-sm"
                            value={settings.recdvb_path || ""}
                            onChange={(e) => setSettings({ ...settings, recdvb_path: e.target.value })}
                            placeholder={settings.recording_command === "recpt1" ? "/usr/local/bin/recpt1" : "/usr/local/bin/recdvb"}
                        />
                    </div>
                    <div>
                        <p className="text-sm text-gray-500 mb-2">epgdump の絶対パスを指定します。</p>
                        <input
                            type="text"
                            className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 outline-none font-mono text-sm shadow-sm"
                            value={settings.epgdump_path || ""}
                            onChange={(e) => setSettings({ ...settings, epgdump_path: e.target.value })}
                            placeholder="/usr/local/bin/epgdump"
                        />
                    </div>
                </div>
            </section>

            <section>
                <h3 className="text-lg font-bold text-gray-700 mb-4 border-l-4 border-red-500 pl-3">7. SSH 接続設定</h3>
                <p className="text-sm text-gray-500 mb-4 leading-relaxed">
                    録画コマンドや epgdump をリモートサーバー（Linux等）で実行する場合、接続情報を設定してください。<br />
                    ホスト名が入力されている場合のみ、SSH 経由での実行が有効になります。
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <p className="text-xs text-gray-500 mb-1 ml-1">SSH ホスト (ホスト名 または IPアドレス)</p>
                        <input
                            type="text"
                            className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 outline-none font-mono text-sm shadow-sm"
                            value={settings.ssh_host || ""}
                            onChange={(e) => setSettings({ ...settings, ssh_host: e.target.value })}
                            placeholder="例: 192.168.1.100"
                        />
                    </div>
                    <div>
                        <p className="text-xs text-gray-500 mb-1 ml-1">SSH ユーザー</p>
                        <input
                            type="text"
                            className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 outline-none font-mono text-sm shadow-sm"
                            value={settings.ssh_user || ""}
                            onChange={(e) => setSettings({ ...settings, ssh_user: e.target.value })}
                            placeholder="user"
                        />
                    </div>
                    <div className="md:col-span-2">
                        <p className="text-xs text-gray-500 mb-1 ml-1">SSH パスワード</p>
                        <input
                            type="password"
                            className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 outline-none font-mono text-sm shadow-sm"
                            value={settings.ssh_pass || ""}
                            onChange={(e) => setSettings({ ...settings, ssh_pass: e.target.value })}
                            placeholder=" dejar vacio si no hay password"
                        />
                    </div>
                </div>
            </section>
        </>
    );
};

export default SettingsRecordingTab;
