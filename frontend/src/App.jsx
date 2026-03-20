import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { format, parseISO, addDays, subDays } from 'date-fns'
import { ja } from 'date-fns/locale'
import { ChevronLeft, ChevronRight, MonitorPlay, Clock, Settings, Bot, List, Calendar } from 'lucide-react'
import './App.css'

import WebPlayer from './components/WebPlayer'
import ErrorBoundary from './components/ErrorBoundary'
import EPGView from './components/EPGView'
import RecordedView from './components/RecordedView'
import ReservationView from './components/ReservationView'
import SettingsView from './components/SettingsView'
import AutoReservationSettingsModal from './components/AutoReservationSettingsModal'
import AutoReservationView from './components/AutoReservationView'

// Constants
const API_BASE = '/api'
const API_URL = `${API_BASE}/schedule`

function App() {
  // Mode State
  const [mode, setMode] = useState('epg') // 'epg' (default)

  // Web Player State
  const [playingProgramId, setPlayingProgramId] = useState(null)
  const [playingStartTime, setPlayingStartTime] = useState(0)
  const [playingTopics, setPlayingTopics] = useState(null)

  // Auto Reservation State
  const [autoResProgram, setAutoResProgram] = useState(null); // For creating new from program
  const [editingRule, setEditingRule] = useState(null); // For editing existing rule

  // Settings State
  const [settings, setSettings] = useState({ font_size: 'medium' });
  const [settingsUpdateTrigger, setSettingsUpdateTrigger] = useState(0); // To trigger refreshes in children


  const parseTime = (val) => {
    if (typeof val === 'number') return val;
    if (typeof val === 'string') {
      if (val.includes(':')) {
        const parts = val.split(':');
        if (parts.length === 3) return Number(parts[0]) * 3600 + Number(parts[1]) * 60 + Number(parts[2]);
        if (parts.length === 2) return Number(parts[0]) * 60 + Number(parts[1]);
      }
      return Number(val);
    }
    return 0;
  }

  const handlePlayProgram = (programId, startTime = 0, initialTopics = null) => {
    let start = parseTime(startTime);

    // Apply Topic Offset only for topics (startTime > 0)
    // RecordedView or EPG might pass numeric startTime
    const offset = settings?.topic_offset_sec || 0;
    if (start > 0 && offset > 0) {
      start = Math.max(0, start - offset);
    }

    setPlayingProgramId(programId);
    setPlayingStartTime(start);
    setPlayingTopics(initialTopics);
  };

  // Handler for EPG to open Auto Res Settings directly
  const handleOpenAutoResSettings = (program) => {
    setAutoResProgram(program);
  };

  // Fetch Settings on Mount
  useEffect(() => {
    axios.get(`${API_BASE}/settings`)
      .then(res => setSettings(res.data))
      .catch(err => console.error("Failed to fetch settings", err));
  }, []);

  return (
    <div className="min-h-screen p-1 md:p-8 pb-nav-safe flex flex-col landscape-fullscreen">

      {/* Header (Desktop Only) */}
      <header className="hidden md:flex items-center justify-between mb-6 gap-4 landscape-hide">
        {/* Left: Title */}
        <div className="flex items-center gap-2 justify-self-start">
          <img src="/logo.png" alt="logo" className="w-8 h-8 object-contain" />
          <h1 className="text-2xl font-bold text-gray-800">TVrecTopic</h1>
        </div>

        {/* Center: Tab Switcher (Desktop Only) */}
        <div className="hidden md:flex bg-gray-200 p-1 rounded-lg gap-1">
          <button
            onClick={() => setMode('epg')}
            className={`px-3 py-2 rounded-md transition font-bold text-sm ${mode === 'epg' ? 'bg-white shadow-sm text-blue-700' : 'text-gray-600 hover:text-gray-900'}`}
          >
            全番組表(EPG)
          </button>
          <button
            onClick={() => setMode('recording')}
            className={`px-3 py-2 rounded-md transition font-bold text-sm ${mode === 'recording' ? 'bg-white shadow-sm text-blue-700' : 'text-gray-600 hover:text-gray-900'}`}
          >
            録画済み
          </button>
          <button
            onClick={() => setMode('reservation')}
            className={`px-3 py-2 rounded-md transition font-bold text-sm ${mode === 'reservation' ? 'bg-white shadow-sm text-blue-700' : 'text-gray-600 hover:text-gray-900'}`}
          >
            予約一覧
          </button>
          <button
            onClick={() => setMode('autores')}
            className={`px-3 py-2 rounded-md transition font-bold text-sm flex items-center gap-1 ${mode === 'autores' ? 'bg-white shadow-sm text-blue-700' : 'text-gray-600 hover:text-gray-900'}`}
          >
            <Bot className="w-4 h-4" />
            自動予約
          </button>
          <button
            onClick={() => setMode('settings')}
            className={`px-3 py-2 rounded-md transition font-bold text-sm flex items-center gap-1 ${mode === 'settings' ? 'bg-white shadow-sm text-blue-700' : 'text-gray-600 hover:text-gray-900'}`}
          >
            <Settings className="w-4 h-4" />
            設定
          </button>
        </div>

        {/* Right: Empty for balance */}
        <div className="hidden md:block"></div>
      </header>

      {/* Content area with bottom margin for mobile nav */}
      <main className="flex-1 mb-20 md:mb-0">
        {mode === 'epg' ? (
          <div className="h-[calc(100vh-70px)] md:h-[calc(100vh-180px)] rounded-xl overflow-hidden border border-gray-100 shadow-sm bg-gray-900 landscape-fullscreen">
            <EPGView
              onPlay={handlePlayProgram}
              onOpenAutoResSettings={handleOpenAutoResSettings}
              settings={settings}
              settingsUpdateTrigger={settingsUpdateTrigger}
              mode={mode}
              setMode={setMode}
            />
          </div>
        ) : mode === 'recording' ? (
          <div className="h-[calc(100vh-70px)] md:h-auto landscape-fullscreen overflow-auto">
            <RecordedView onPlay={handlePlayProgram} mode={mode} setMode={setMode} />
          </div>
        ) : mode === 'reservation' ? (
          <div className="h-[calc(100vh-70px)] md:h-auto landscape-fullscreen overflow-auto">
            <ReservationView mode={mode} setMode={setMode} />
          </div>
        ) : mode === 'autores' ? (
          <div className="h-[calc(100vh-70px)] md:h-auto landscape-fullscreen overflow-auto">
            <AutoReservationView
              onEdit={(rule) => {
                if (rule) {
                  setEditingRule(rule);
                } else {
                  // Create New: Open modal with empty program/rule
                  setAutoResProgram({});
                }
              }}
              onRefresh={() => setSettingsUpdateTrigger(prev => prev + 1)}
              refreshTrigger={settingsUpdateTrigger}
              mode={mode}
              setMode={setMode}
            />
          </div>
        ) : mode === 'settings' ? (
          <div className="h-[calc(100vh-70px)] md:h-auto landscape-fullscreen overflow-auto">
            <SettingsView
              onSave={(newSettings) => {
                setSettings(newSettings);
                setSettingsUpdateTrigger(prev => prev + 1);
              }}
              mode={mode}
              setMode={setMode}
            />
          </div>
        ) : null}
      </main>

      {
        playingProgramId && (
          <ErrorBoundary onClose={() => setPlayingProgramId(null)}>
            <WebPlayer
              programId={playingProgramId}
              startTime={playingStartTime}
              initialTopics={playingTopics}
              settings={settings}
              onClose={() => setPlayingProgramId(null)}
              onPlayProgram={handlePlayProgram}
            />
          </ErrorBoundary>
        )
      }

      {/* Auto Reservation Settings Modal (New/Edit) */}
      {
        (autoResProgram || editingRule) && (
          <AutoReservationSettingsModal
            initialProgram={autoResProgram}
            initialRule={editingRule}
            onClose={() => {
              setAutoResProgram(null);
              setEditingRule(null);
            }}
            onSaved={() => {
              setAutoResProgram(null);
              setEditingRule(null);
              setSettingsUpdateTrigger(prev => prev + 1); // Trigger EPG refresh
            }}
          />
        )
      }

      {/* Bottom Navigation (Mobile Only) */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-md border-t border-gray-200 px-6 py-2 flex justify-between items-center z-[80] pb-safe landscape-hide">
        <button
          onClick={() => setMode('epg')}
          className={`flex flex-col items-center gap-1 ${mode === 'epg' ? 'text-blue-600' : 'text-gray-500'}`}
        >
          <Calendar className="w-6 h-6" />
          <span className="text-[10px] font-bold">番組表</span>
        </button>
        <button
          onClick={() => setMode('recording')}
          className={`flex flex-col items-center gap-1 ${mode === 'recording' ? 'text-blue-600' : 'text-gray-500'}`}
        >
          <MonitorPlay className="w-6 h-6" />
          <span className="text-[10px] font-bold">録画済</span>
        </button>
        <button
          onClick={() => setMode('reservation')}
          className={`flex flex-col items-center gap-1 ${mode === 'reservation' ? 'text-blue-600' : 'text-gray-500'}`}
        >
          <List className="w-6 h-6" />
          <span className="text-[10px] font-bold">予約</span>
        </button>
        <button
          onClick={() => setMode('autores')}
          className={`flex flex-col items-center gap-1 ${mode === 'autores' ? 'text-blue-600' : 'text-gray-500'}`}
        >
          <Bot className="w-6 h-6" />
          <span className="text-[10px] font-bold">自動録画</span>
        </button>
        <button
          onClick={() => setMode('settings')}
          className={`flex flex-col items-center gap-1 ${mode === 'settings' ? 'text-blue-600' : 'text-gray-500'}`}
        >
          <Settings className="w-6 h-6" />
          <span className="text-[10px] font-bold">設定</span>
        </button>
      </nav>
    </div>
  )
}

export default App
