import React from 'react';
import { Loader, RefreshCw } from 'lucide-react';

const SettingsLogTab = ({ logFiles, selectedLogFile, setSelectedLogFile, logs, logsLoading, handleReloadLog }) => {
    return (
        <div className="flex flex-col h-full min-h-[500px]">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-4 gap-4">
                <h3 className="text-lg font-bold text-gray-700 border-l-4 border-orange-500 pl-3">バックエンドログビューア</h3>
                <div className="flex items-center gap-3 w-full md:w-auto">
                    <select
                        className="flex-1 md:w-64 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 outline-none font-mono text-sm bg-white shadow-sm"
                        value={selectedLogFile}
                        onChange={(e) => setSelectedLogFile(e.target.value)}
                        disabled={logsLoading}
                    >
                        <option value="" disabled>ログファイルを選択</option>
                        {logFiles.map(f => (
                            <option key={f} value={f}>{f}</option>
                        ))}
                    </select>
                    <button
                        onClick={handleReloadLog}
                        disabled={logsLoading || !selectedLogFile}
                        className="flex items-center gap-2 px-4 py-2 bg-orange-50 text-orange-700 rounded-lg shadow-sm hover:bg-orange-100 transition font-bold text-sm shrink-0 disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 ${logsLoading ? 'animate-spin' : ''}`} />
                        更新
                    </button>
                </div>
            </div>

            <div className="flex-1 bg-gray-900 rounded-xl shadow-inner border border-gray-300 p-4 overflow-y-auto max-h-[600px] font-mono text-xs md:text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                {logsLoading && logs.length === 0 ? (
                    <div className="flex items-center justify-center py-10 text-gray-500">
                        <Loader className="w-6 h-6 animate-spin mr-2" /> 読み込み中...
                    </div>
                ) : logs.length === 0 ? (
                    <div className="text-gray-500 italic text-center py-10">ファイルが空、または読み込みに失敗しました</div>
                ) : (
                    logs.map((line, i) => (
                        <div key={i} className="break-all border-b border-gray-800 pb-1 mb-1 hover:bg-gray-800 px-1 rounded">{line}</div>
                    ))
                )}
            </div>
        </div>
    );
};

export default SettingsLogTab;
