import { useEffect, useRef, useState } from 'react'
import { Eye, Wifi, WifiOff } from 'lucide-react'
import PersonList from './PersonList'

const EMPTY_STATS = { active_count: 0, total_seen: 0, tracks: [] }

export default function CommandCenter({ streamId }) {
  const imgRef = useRef(null)
  const wsRef = useRef(null)
  const [stats, setStats] = useState(EMPTY_STATS)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    if (!streamId) {
      setStats(EMPTY_STATS)
      setConnected(false)
      return
    }

    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws/stream/${streamId}`)

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)

    ws.onmessage = e => {
      const d = JSON.parse(e.data)
      if (imgRef.current && d.frame) {
        imgRef.current.src = `data:image/jpeg;base64,${d.frame}`
      }
      if (d.stats) setStats(d.stats)
    }

    wsRef.current = ws
    return () => ws.close()
  }, [streamId])

  if (!streamId) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-600">
        <div className="text-center">
          <Eye size={48} className="mx-auto mb-3 opacity-20" />
          <p className="text-sm">Select a stream to monitor</p>
          <p className="text-xs text-gray-700 mt-1">
            Add an RTSP stream using the button above
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* ── Video feed ── */}
      <div className="flex-1 bg-black flex flex-col min-w-0">
        {/* Status bar */}
        <div className="h-8 bg-gray-900 border-b border-gray-800 flex items-center px-3 gap-2 shrink-0">
          {connected ? (
            <>
              <Wifi size={13} className="text-green-400" />
              <span className="text-xs text-green-400 font-semibold">LIVE</span>
            </>
          ) : (
            <>
              <WifiOff size={13} className="text-yellow-500" />
              <span className="text-xs text-yellow-500">Connecting…</span>
            </>
          )}
          <span className="ml-auto text-xs text-gray-600">
            {stats.active_count} person{stats.active_count !== 1 ? 's' : ''} in frame
          </span>
        </div>

        {/* Frame */}
        <div className="flex-1 flex items-center justify-center overflow-hidden bg-gray-950">
          <img
            ref={imgRef}
            className="max-w-full max-h-full object-contain"
            alt="Live stream"
          />
          {!connected && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <p className="text-gray-600 text-sm animate-pulse">Waiting for frames…</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Right panel: Command Center ── */}
      <div className="w-72 bg-gray-900 border-l border-gray-800 flex flex-col shrink-0">
        {/* Stats */}
        <div className="p-4 border-b border-gray-800 shrink-0">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">
            Command Center
          </h2>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-gray-800 rounded-xl p-3 text-center">
              <div className="text-3xl font-bold text-green-400 tabular-nums">
                {stats.active_count}
              </div>
              <div className="text-xs text-gray-500 mt-1">Active Now</div>
            </div>
            <div className="bg-gray-800 rounded-xl p-3 text-center">
              <div className="text-3xl font-bold text-blue-400 tabular-nums">
                {stats.total_seen}
              </div>
              <div className="text-xs text-gray-500 mt-1">Total Detected</div>
            </div>
          </div>
        </div>

        {/* Person list */}
        <PersonList tracks={stats.tracks ?? []} />
      </div>
    </div>
  )
}
