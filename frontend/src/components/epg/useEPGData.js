import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { startOfDay } from 'date-fns';

export const useEPGData = (currentDate, selectedType, settingsUpdateTrigger) => {
    const [epgData, setEpgData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [reservations, setReservations] = useState([]);
    const [recordedPrograms, setRecordedPrograms] = useState([]);
    const [channelsConfig, setChannelsConfig] = useState([]);
    const [dateRange, setDateRange] = useState({ min: null, max: null });

    // Fetch Channels
    const fetchChannels = async () => {
        try {
            const apiBase = `http://${window.location.hostname}:8000`;
            const cRes = await axios.get(`${apiBase}/api/channels`);
            if (Array.isArray(cRes.data)) {
                setChannelsConfig(cRes.data);
            }
        } catch (err) {
            console.error("Failed to fetch channels", err);
        }
    };

    // Fetch Date Range
    const fetchDateRange = async () => {
        try {
            const apiBase = `http://${window.location.hostname}:8000`;
            const res = await axios.get(`${apiBase}/api/epg/range`);
            if (res.data.min && res.data.max) {
                setDateRange({
                    min: startOfDay(new Date(res.data.min)),
                    max: startOfDay(new Date(res.data.max))
                });
            }
        } catch (err) {
            console.error("Failed to fetch EPG range", err);
        }
    };

    // Fetch Reservations
    const fetchReservations = async () => {
        try {
            const res = await axios.get(`http://${window.location.hostname}:8000/api/reservations`);
            setReservations(res.data);
        } catch (err) { console.error("Failed to fetch reservations", err); }
    };

    // Fetch Recorded Programs
    const fetchRecorded = async () => {
        try {
            const res = await axios.get(`http://${window.location.hostname}:8000/api/recorded`);
            setRecordedPrograms(res.data);
        } catch (err) { console.error("Failed to fetch recorded", err); }
    };

    // Fetch EPG Data
    const fetchEPG = async (signal) => {
        setLoading(true);
        try {
            const apiBase = `http://${window.location.hostname}:8000`;
            const start = Math.floor(startOfDay(currentDate).getTime() / 1000);
            const end = start + 86400;

            const [epgPrimary, resRes, recRes] = await Promise.all([
                axios.get(`${apiBase}/api/epg`, { params: { start, end, type: selectedType }, signal }),
                axios.get(`${apiBase}/api/reservations`, { signal }),
                axios.get(`${apiBase}/api/recorded`, { signal })
            ]);

            const normalize = (progs) => progs.map(p => ({
                ...p,
                start_time_dt: new Date(p.start_time),
                end_time_dt: new Date(p.end_time)
            }));

            setEpgData(normalize(epgPrimary.data));
            setReservations(resRes.data);
            setRecordedPrograms(recRes.data);
            setLoading(false);

            const neededTypes = ['GR', 'BS', 'CS'].filter(t => t !== selectedType);
            const otherPromises = neededTypes.map(t =>
                axios.get(`${apiBase}/api/epg`, { params: { start, end, type: t }, signal })
            );

            const otherResults = await Promise.all(otherPromises);
            const newPrograms = otherResults.flatMap(r => normalize(r.data));

            setEpgData(prev => {
                const existingIds = new Set(prev.map(p => p.id));
                const uniqueNew = [];
                const seenInNew = new Set();

                newPrograms.forEach(p => {
                    if (!existingIds.has(p.id) && !seenInNew.has(p.id)) {
                        existingIds.add(p.id);
                        seenInNew.add(p.id);
                        uniqueNew.push(p);
                    }
                });
                return [...prev, ...uniqueNew];
            });

        } catch (err) {
            if (!axios.isCancel(err)) {
                console.error("Failed to fetch EPG", err);
                setLoading(false);
            }
        }
    };

    useEffect(() => {
        fetchChannels();
        fetchDateRange();
    }, [settingsUpdateTrigger]);

    useEffect(() => {
        const controller = new AbortController();
        fetchEPG(controller.signal);
        return () => controller.abort();
    }, [currentDate, settingsUpdateTrigger]);

    // Optimize Reservation/Recorded Lookups
    const { requestMap, recordedMap } = useMemo(() => {
        const rMap = new Map();
        const recMap = new Map();

        if (reservations) {
            reservations.forEach(r => {
                if (r.program_id) rMap.set(r.program_id, r);
                const key = `${r.service_id}-${new Date(r.start_time).getTime()}`;
                if (!rMap.has(key)) rMap.set(key, r);
            });
        }

        if (recordedPrograms) {
            recordedPrograms.forEach(r => {
                if (r.event_id && r.service_id) {
                    recMap.set(`${r.event_id}-${r.service_id}`, r);
                }
            });
        }
        return { requestMap: rMap, recordedMap: recMap };
    }, [reservations, recordedPrograms]);

    // Optimize Programs High-Level Structuring
    const { programsByServiceId, programsByChannel } = useMemo(() => {
        const bySid = {};
        const byCh = {};

        epgData.forEach(p => {
            if (p.service_id) {
                if (!bySid[p.service_id]) bySid[p.service_id] = [];
                bySid[p.service_id].push(p);
            }
            if (p.channel) {
                if (!byCh[p.channel]) byCh[p.channel] = [];
                byCh[p.channel].push(p);
            }
        });
        return { programsByServiceId: bySid, programsByChannel: byCh };
    }, [epgData]);

    return {
        epgData, setEpgData,
        loading, setLoading,
        reservations, setReservations,
        recordedPrograms, setRecordedPrograms,
        channelsConfig, fetchChannels,
        dateRange, fetchDateRange,
        fetchEPG, fetchReservations, fetchRecorded,
        requestMap, recordedMap,
        programsByServiceId, programsByChannel
    };
};
