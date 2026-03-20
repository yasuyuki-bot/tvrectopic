import React, { useEffect, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Tv, X, Copy, Check, Info } from 'lucide-react';

/**
 * Constants and Utilities
 */
const FLAGS_URL = "chrome://flags/#unsafely-treat-insecure-origin-as-secure";
const CURRENT_ORIGIN = window.location.origin;

/**
 * Helper: Copy text to clipboard with fallback for non-secure contexts
 */
const copyToClipboard = async (text) => {
    if (navigator.clipboard) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            console.error("Clipboard API failed, trying fallback", err);
        }
    }
    
    // Fallback: Legacy execCommand('copy')
    try {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-9999px";
        textArea.style.top = "0";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        return successful;
    } catch (err) {
        console.error("Legacy copy failed", err);
        return false;
    }
};

/**
 * Internal Component: Setup Guide Modal
 * Shown when Cast SDK is blocked or unavailable
 */
const SetupGuideModal = ({ isOpen, onClose }) => {
    const [copiedType, setCopiedType] = useState(null); // 'flags' | 'origin' | null

    const handleCopy = useCallback(async (text, type) => {
        const success = await copyToClipboard(text);
        if (success) {
            setCopiedType(type);
            setTimeout(() => setCopiedType(null), 2000);
        }
    }, []);

    if (!isOpen) return null;

    return createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={onClose}>
            <div className="bg-white rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh] animate-in fade-in zoom-in duration-200" onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className="bg-gray-900 px-6 py-4 flex items-center justify-between text-white shrink-0">
                    <h2 className="text-lg font-bold flex items-center gap-2">
                        <Tv className="w-5 h-5 text-blue-400" />
                        Google Cast セットアップガイド
                    </h2>
                    <button onClick={onClose} className="hover:bg-white/10 p-1 rounded-full transition">
                        <X className="w-6 h-6" />
                    </button>
                </div>
                
                {/* Scrollable Content */}
                <div className="p-6 space-y-6 overflow-y-auto flex-1 custom-scrollbar text-gray-800">
                    <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-lg">
                        <div className="flex gap-3">
                            <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                            <p className="text-sm text-blue-800 leading-relaxed font-medium">
                                Chrome や Edge で <strong>http</strong> 通信（非HTTPS）環境からキャストするには、以下のブラウザ設定が必要です。
                            </p>
                        </div>
                    </div>

                    <div className="space-y-6">
                        {/* Step 1 */}
                        <div className="space-y-2">
                            <h3 className="font-bold flex items-center gap-2">
                                <span className="w-5 h-5 bg-blue-500 text-white rounded-full flex items-center justify-center text-[10px] font-mono">1</span>
                                試験運用機能を呼び出す
                            </h3>
                            <p className="text-xs text-gray-500 italic">ブラウザのアドレスバーに貼り付けて実行してください</p>
                            <div className="flex items-center gap-2 bg-gray-100 p-2.5 rounded-lg border border-gray-200 group">
                                <code className="text-[11px] break-all flex-1 text-blue-700 font-mono font-bold select-all">{FLAGS_URL}</code>
                                <button onClick={() => handleCopy(FLAGS_URL, 'flags')} className="p-1.5 hover:bg-gray-200 rounded-md transition text-gray-500 hover:text-blue-600 bg-white shadow-sm border border-gray-200 shrink-0">
                                    {copiedType === 'flags' ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
                                </button>
                            </div>
                        </div>

                        {/* Step 2 */}
                        <div className="space-y-2">
                            <h3 className="font-bold flex items-center gap-2">
                                <span className="w-5 h-5 bg-blue-500 text-white rounded-full flex items-center justify-center text-[10px] font-mono">2</span>
                                接続先 (Origin) を許可
                            </h3>
                            <p className="text-xs text-gray-500 italic">表示された項目のテキストボックスに、以下の値を貼り付けてください</p>
                            <div className="flex items-center gap-2 bg-gray-100 p-2.5 rounded-lg border border-gray-200 group">
                                <code className="text-[11px] break-all flex-1 text-green-700 font-mono font-bold select-all">{CURRENT_ORIGIN}</code>
                                <button onClick={() => handleCopy(CURRENT_ORIGIN, 'origin')} className="p-1.5 hover:bg-gray-200 rounded-md transition text-gray-500 hover:text-green-600 bg-white shadow-sm border border-gray-200 shrink-0">
                                    {copiedType === 'origin' ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
                                </button>
                            </div>
                        </div>

                        {/* Step 3 */}
                        <div className="space-y-3">
                            <h3 className="font-bold flex items-center gap-2">
                                <span className="w-5 h-5 bg-blue-500 text-white rounded-full flex items-center justify-center text-[10px] font-mono">3</span>
                                設定を有効にして再起動
                            </h3>
                            <div className="pl-7 space-y-3">
                                <p className="text-sm leading-relaxed">
                                    右側のメニューを <strong>Enabled</strong> に変更します。
                                </p>
                                <div className="bg-orange-100/50 border border-orange-200 rounded-lg p-3">
                                    <p className="text-xs text-orange-800 font-medium">
                                        最後に右下の <strong>Relaunch</strong> ボタンを押してブラウザを再起動すると、テレビのアイコンが表示されます。
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="p-4 bg-gray-50 border-t flex justify-end shrink-0">
                    <button onClick={onClose} className="px-8 py-2.5 bg-gray-900 text-white rounded-xl font-bold hover:bg-gray-800 transition shadow-lg active:scale-95">
                        了解
                    </button>
                </div>
            </div>
        </div>,
        document.body
    );
};

/**
 * Main Component: CastButton
 */
const CastButton = ({ isCasting, onIntentToCast }) => {
    const [showGuide, setShowGuide] = useState(false);
    const [isSdkAvailable, setIsSdkAvailable] = useState(false);

    useEffect(() => {
        let isDisposed = false;

        const initializeCastApi = () => {
            if (isDisposed) return;
            try {
                if (!window.cast?.framework) {
                    console.log("CastButton: SDK framework not ready yet");
                    return false;
                }
                const castContext = window.cast.framework.CastContext.getInstance();
                
                // CRITICAL: setOptions must be called before requestSession
                console.log("CastButton: Initializing CastContext options...");
                castContext.setOptions({
                    receiverApplicationId: window.chrome.cast.media.DEFAULT_MEDIA_RECEIVER_APP_ID,
                    autoJoinPolicy: window.chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED,
                    resumeSavedSession: true
                });
                
                setIsSdkAvailable(true);
                return true;
            } catch (e) {
                console.error("CastButton: Cast API Initialization Failed", e);
                return false;
            }
        };

        // 1. Check if already available
        if (window.cast?.framework) {
            initializeCastApi();
        }

        // 2. Set up global callback (standard way Cast SDK notifies availability)
        const prevCallback = window.__onGCastApiAvailable;
        window.__onGCastApiAvailable = (isAvailable) => {
            console.log("CastButton: __onGCastApiAvailable called, isAvailable =", isAvailable);
            if (prevCallback) prevCallback(isAvailable);
            if (isAvailable) {
                initializeCastApi();
            }
        };

        // 3. Fallback polling (sometimes callback isn't triggered correctly in SPAs)
        const interval = setInterval(() => {
            if (window.cast?.framework) {
                if (initializeCastApi()) {
                    clearInterval(interval);
                }
            }
        }, 1000);

        return () => {
            isDisposed = true;
            clearInterval(interval);
        };
    }, []);

    const handleManualClick = useCallback(async () => {
        if (onIntentToCast) onIntentToCast();
        console.log("CastButton: Clicked. isSdkAvailable =", isSdkAvailable);
        
        if (isSdkAvailable) {
            try {
                const context = window.cast.framework.CastContext.getInstance();
                console.log("CastButton: Requesting session...");
                // requestSession() returns a Promise<chrome.cast.error.Error?>
                const error = await context.requestSession();
                if (error) {
                    console.warn("CastButton: requestSession returned error:", error);
                } else {
                    console.log("CastButton: requestSession successful (or dialog opened)");
                }
            } catch (e) {
                console.error("CastButton: session request failed", e);
            }
            return;
        }
        
        console.log("CastButton: SDK not available, showing setup guide");
        setShowGuide(true);
    }, [isSdkAvailable]);

    return (
        <>
            <div className="flex items-center justify-center mx-1 md:mx-2 group relative">
                <button 
                    className="w-8 h-8 flex items-center justify-center hover:bg-white/10 rounded-full transition cursor-pointer relative" 
                    onClick={handleManualClick}
                    title={isSdkAvailable ? "Google Cast" : "Cast セットアップが必要"}
                >
                    <Tv className={`w-5 h-5 transition-colors ${
                        isSdkAvailable 
                            ? (isCasting ? 'text-blue-500 fill-blue-500' : 'text-white/50 group-hover:text-white') 
                            : 'text-orange-400 group-hover:text-orange-300'
                    }`} />
                    
                    {!isSdkAvailable && (
                        <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-orange-500 rounded-full border border-gray-900 animate-pulse" />
                    )}
                    
                    {isSdkAvailable && (
                        <div className="absolute inset-0 pointer-events-none opacity-0">
                            {/* Keep launcher for status/background logic but let parent button handle clicks */}
                            <google-cast-launcher
                                style={{
                                    display: 'block',
                                    width: '100%',
                                    height: '100%'
                                }}
                            />
                        </div>
                    )}
                </button>
                
                <span className="absolute -top-10 left-1/2 -translate-x-1/2 bg-black/80 text-white text-[10px] px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition whitespace-nowrap pointer-events-none z-50 shadow-xl">
                    {isSdkAvailable ? 'Google Cast' : 'セットアップが必要'}
                </span>
            </div>

            <SetupGuideModal 
                isOpen={showGuide} 
                onClose={() => setShowGuide(false)} 
            />
        </>
    );
};

export default CastButton;

