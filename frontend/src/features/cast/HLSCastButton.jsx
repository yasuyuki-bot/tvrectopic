import React, { useEffect, useState, useCallback } from 'react';
import { Tv } from 'lucide-react';

const HLSCastButton = ({ isCasting, onIntentToCast }) => {
    const [isSdkAvailable, setIsSdkAvailable] = useState(false);

    useEffect(() => {
        let isDisposed = false;

        const initializeCastApi = () => {
            if (isDisposed) return;
            try {
                if (!window.cast?.framework) return false;
                const castContext = window.cast.framework.CastContext.getInstance();
                
                // Initialize if not done
                castContext.setOptions({
                    receiverApplicationId: window.chrome.cast.media.DEFAULT_MEDIA_RECEIVER_APP_ID,
                    autoJoinPolicy: window.chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED,
                    resumeSavedSession: true
                });
                
                setIsSdkAvailable(true);
                return true;
            } catch (e) {
                console.error("HLSCastButton: Cast API Init Failed", e);
                return false;
            }
        };

        if (window.cast?.framework) initializeCastApi();

        const prevCallback = window.__onGCastApiAvailable;
        window.__onGCastApiAvailable = (isAvailable) => {
            if (prevCallback) prevCallback(isAvailable);
            if (isAvailable) initializeCastApi();
        };

        const interval = setInterval(() => {
            if (window.cast?.framework && initializeCastApi()) {
                clearInterval(interval);
            }
        }, 1000);

        return () => {
            isDisposed = true;
            clearInterval(interval);
        };
    }, []);

    const handleManualClick = useCallback(async () => {
        if (!isSdkAvailable) {
            alert("Google Castの準備ができていません。ブラウザのセキュリティ設定等を確認してください。");
            return;
        }

        if (onIntentToCast) {
            onIntentToCast();
        }

        try {
            const context = window.cast.framework.CastContext.getInstance();
            const session = context.getCurrentSession();
            if (session && isCasting) {
                // If already casting, maybe we want to disconnect?
                // The main listener in WebPlayer will handle UI disconnect
                context.endCurrentSession(true);
            } else {
                await context.requestSession();
            }
        } catch (e) {
            console.error("HLSCastButton: session request failed", e);
        }
    }, [isSdkAvailable, isCasting, onIntentToCast]);

    return (
        <div className="flex items-center justify-center mx-1 md:mx-2 group relative">
            <button 
                className="w-8 h-8 flex items-center justify-center hover:bg-white/10 rounded-full transition cursor-pointer relative" 
                onClick={handleManualClick}
                title="HLS Cast (Mpeg2ts)"
            >
                <Tv className={`w-5 h-5 transition-colors ${
                    isCasting 
                        ? 'text-green-500 fill-green-500' 
                        : (isSdkAvailable ? 'text-green-400 group-hover:text-green-300' : 'text-orange-400')
                }`} />
                
                {isSdkAvailable && (
                    <div className="absolute top-0 right-0 w-3 h-3 bg-black flex items-center justify-center rounded-full border border-gray-900">
                        <span className="text-[6px] text-green-500 font-bold">HLS</span>
                    </div>
                )}
                
                {!isSdkAvailable && (
                    <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-orange-500 rounded-full border border-gray-900 animate-pulse" />
                )}
            </button>
            <span className="absolute -top-10 left-1/2 -translate-x-1/2 bg-black/80 text-white text-[10px] px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition whitespace-nowrap pointer-events-none z-50 shadow-xl">
                {isSdkAvailable ? 'HLS Cast' : 'セットアップが必要'}
            </span>
        </div>
    );
};

export default HLSCastButton;
