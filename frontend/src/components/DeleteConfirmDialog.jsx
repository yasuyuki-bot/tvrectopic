import React from 'react';
import { Trash2, FileVideo, ListX, X } from 'lucide-react';

const DeleteConfirmDialog = ({ program, isOpen, onClose, onConfirm }) => {
    if (!isOpen || !program) return null;

    return (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
            <div className="bg-white rounded-xl shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in duration-200">

                {/* Header */}
                <div className="bg-gray-50 px-6 py-4 border-b border-gray-100 flex justify-between items-center">
                    <h3 className="font-bold text-lg text-gray-800 flex items-center gap-2">
                        <Trash2 className="w-5 h-5 text-red-500" />
                        削除の確認
                    </h3>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6">
                    <p className="text-gray-600 mb-2">以下の番組を削除しますか？</p>
                    <div className="bg-gray-50 p-3 rounded-lg border border-gray-200 mb-6">
                        <p className="font-bold text-gray-800 line-clamp-2">{program.title}</p>
                        <p className="text-xs text-gray-700 mt-1">{program.service_name || program.channel}</p>
                    </div>

                    <p className="text-sm text-gray-500 mb-4">
                        削除方法を選択してください:
                    </p>

                    <div className="flex flex-col gap-3">
                        {/* Option 1: Delete Everything */}
                        <button
                            onClick={() => onConfirm(true)}
                            className="flex items-center gap-3 p-4 rounded-lg border-2 border-red-100 hover:border-red-500 hover:bg-red-50 transition group text-left"
                        >
                            <div className="bg-red-100 p-2 rounded-full text-red-600 group-hover:scale-110 transition">
                                <Trash2 className="w-5 h-5" />
                            </div>
                            <div>
                                <span className="block font-bold text-gray-900 group-hover:text-red-700">ファイルも削除する</span>
                                <span className="text-xs text-gray-500">録画データ(TS/MP4)とリストの両方を削除します</span>
                            </div>
                        </button>

                        {/* Option 2: Keep File */}
                        <button
                            onClick={() => onConfirm(false)}
                            className="flex items-center gap-3 p-4 rounded-lg border-2 border-gray-100 hover:border-blue-500 hover:bg-blue-50 transition group text-left"
                        >
                            <div className="bg-blue-100 p-2 rounded-full text-blue-600 group-hover:scale-110 transition">
                                <ListX className="w-5 h-5" />
                            </div>
                            <div>
                                <span className="block font-bold text-gray-900 group-hover:text-blue-700">ファイルは残す</span>
                                <span className="text-xs text-gray-500">リストからのみ削除し、録画データは保持します</span>
                            </div>
                        </button>
                    </div>
                </div>

                {/* Footer */}
                <div className="bg-gray-50 px-6 py-3 border-t border-gray-100 flex justify-end">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-gray-600 hover:bg-gray-200 rounded-lg transition text-sm font-medium"
                    >
                        キャンセル
                    </button>
                </div>
            </div>
        </div>
    );
};

export default DeleteConfirmDialog;
