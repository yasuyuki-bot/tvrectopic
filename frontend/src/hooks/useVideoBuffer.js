import { useState, useEffect } from 'react';

export const useVideoBuffer = (videoRef) => {
    const [bufferState, setBufferState] = useState({
        secondsAhead: 0,
        percentage: 0,
        bufferedRanges: []
    });

    useEffect(() => {
        const updateBuffer = () => {
            const video = videoRef.current;
            if (!video) return;

            const buffered = video.buffered;
            const duration = video.duration;
            const currentTime = video.currentTime;

            let ahead = 0;
            let ranges = [];

            if (buffered && buffered.length > 0) {
                // For MSE (Media Source Extensions) and fragmented MP4s, 
                // the buffer is often split into multiple disjoint ranges.
                // We need to sum up all buffered time from the current playhead onwards.
                for (let i = 0; i < buffered.length; i++) {
                    const start = buffered.start(i);
                    const end = buffered.end(i);
                    ranges.push({ start, end });

                    // If the current time is before this range, add the whole range length
                    if (currentTime < start) {
                        ahead += (end - start);
                    } 
                    // If the current time is inside this range, add the remaining portion
                    else if (currentTime >= start && currentTime <= end) {
                        ahead += (end - currentTime);
                    }
                    // Add a small tolerance (1.0s) for very slight gaps in MSE playback
                    else if (currentTime > end && currentTime - end < 1.0) {
                        // ignore, we've passed this chunk but barely
                    }
                }
            }

            // Diagnostic logging (kept commented for future troubleshooting)
            // if (!buffered || buffered.length === 0) {
            //     console.warn("[VideoBuffer] No buffered ranges found.");
            // } else {
            //     console.log("[VideoBuffer] CurrentTime:", currentTime.toFixed(2), "BufferedRanges:", JSON.stringify(ranges), "Ahead:", ahead.toFixed(2));
            // }

            setBufferState({
                secondsAhead: ahead,
                percentage: duration > 0 ? (ahead / duration) * 100 : 0,
                bufferedRanges: ranges
            });
        };

        // Use a small interval to check if the ref is populated if not already
        let checkCount = 0;
        let videoNode = null;
        let timer = null;

        const attach = () => {
            videoNode = videoRef.current;
            if (videoNode) {
                // videoNode.addEventListener('progress', updateBuffer); // Usually included in other events
                videoNode.addEventListener('progress', updateBuffer);
                videoNode.addEventListener('timeupdate', updateBuffer);
                videoNode.addEventListener('loadedmetadata', updateBuffer);
                updateBuffer(); // Initial check
                return true;
            }
            return false;
        };

        if (!attach()) {
            timer = setInterval(() => {
                checkCount++;
                if (attach() || checkCount > 50) { // Try for 5 seconds
                    if (timer) clearInterval(timer);
                }
            }, 100);
        }

        return () => {
            if (timer) clearInterval(timer);
            if (videoNode) {
                videoNode.removeEventListener('progress', updateBuffer);
                videoNode.removeEventListener('timeupdate', updateBuffer);
                videoNode.removeEventListener('loadedmetadata', updateBuffer);
            }
        };
    }, [videoRef]);

    return bufferState;
};
