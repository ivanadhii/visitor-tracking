import { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import { WifiOff, ScanEye } from 'lucide-react'
import PersonList from './PersonList'
import SystemStats from './SystemStats'

const EMPTY_STATS = { active_count: 0, total_seen: 0, tracks: [] }

export default function CommandCenter({ streamId, token }) {
  const videoRef = useRef(null)
  const hlsRef = useRef(null)
  const wsRef = useRef(null)
  const [stats, setStats] = useState(EMPTY_STATS)
  const [hlsReady, setHlsReady] = useState(false)

  // ── HLS player ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!streamId) {
      setHlsReady(false)
      setStats(EMPTY_STATS)
      return
    }

    const src = `/hls/${streamId}/index.m3u8`
    const video = videoRef.current

    // Destroy previous instance
    if (hlsRef.current) {
      hlsRef.current.destroy()
      hlsRef.current = null
    }
    setHlsReady(false)

    if (Hls.isSupported()) {
      const hls = new Hls({
        liveSyncDurationCount: 3,
        liveMaxLatencyDurationCount: 5,
        lowLatencyMode: false,
      })
      hls.loadSource(src)
      hls.attachMedia(video)
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        video.play().catch(() => {})
        setHlsReady(true)
      })
      hls.on(Hls.Events.ERROR, (_, data) => {
        if (data.fatal) {
          // Auto-retry after fatal error (stream not ready yet)
          setTimeout(() => {
            hls.loadSource(src)
            hls.startLoad()
          }, 3000)
        }
      })
      hlsRef.current = hls
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari native HLS
      video.src = src
      video.addEventListener('loadedmetadata', () => {
        video.play().catch(() => {})
        setHlsReady(true)
      })
    }

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy()
        hlsRef.current = null
      }
    }
  }, [streamId])

  // ── WebSocket — stats only ──────────────────────────────────────────────────
  useEffect(() => {
    if (!streamId) return

    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const query = token ? `?token=${token}` : ''
    let ws
    let retryTimer

    const connect = () => {
      ws = new WebSocket(`${proto}://${location.host}/ws/stream/${streamId}${query}`)
      ws.onmessage = e => {
        const d = JSON.parse(e.data)
        if (d.stats) setStats(d.stats)
      }
      ws.onclose = () => {
        retryTimer = setTimeout(connect, 3000)
      }
      wsRef.current = ws
    }

    connect()
    return () => {
      clearTimeout(retryTimer)
      ws?.close()
    }
  }, [streamId, token])

  if (!streamId) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-700 bg-gray-950">
        <div className="text-center">
          <ScanEye size={48} className="mx-auto mb-3 opacity-20" />
          <p className="text-sm text-gray-500">Pilih stream untuk mulai monitoring</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-1 overflow-hidden">

      {/* ── Video feed ── */}
      <div className="flex-1 bg-gray-950 flex flex-col min-w-0">
        {/* Status bar */}
        <div className="h-9 bg-gray-900 border-b border-gray-800 flex items-center px-4 gap-2 shrink-0">
          <div className="flex items-center gap-1.5">
            {hlsReady ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                <span className="text-xs font-semibold text-green-400 tracking-wide">LIVE</span>
              </>
            ) : (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
                <span className="text-xs font-semibold text-yellow-500 tracking-wide">CONNECTING</span>
              </>
            )}
          </div>
          <div className="ml-auto flex items-center gap-3 text-xs text-gray-500">
            <span>
              <span className="text-white font-semibold tabular-nums">{stats.active_count}</span>
              {' '}in frame
            </span>
            <span>
              <span className="text-blue-400 font-semibold tabular-nums">{stats.total_seen ?? 0}</span>
              {' '}total
            </span>
          </div>
        </div>

        {/* Video */}
        <div className="flex-1 relative flex items-center justify-center overflow-hidden bg-gray-950">
          <video
            ref={videoRef}
            className="max-w-full max-h-full object-contain"
            muted
            playsInline
            autoPlay
          />
          {!hlsReady && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-950">
              <div className="text-center">
                <WifiOff size={32} className="mx-auto mb-2 text-gray-700" />
                <p className="text-gray-600 text-xs animate-pulse">Menghubungkan ke stream…</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Right panel ── */}
      <div className="w-72 bg-gray-900 border-l border-gray-800 flex flex-col shrink-0">

        {/* Detection stats */}
        <div className="p-4 border-b border-gray-800 shrink-0">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">
            Deteksi
          </p>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-gray-800/80 rounded-xl p-3 text-center">
              <div className="text-3xl font-bold text-green-400 tabular-nums leading-none mb-1">
                {stats.active_count}
              </div>
              <div className="text-xs text-gray-500">Aktif</div>
            </div>
            <div className="bg-gray-800/80 rounded-xl p-3 text-center">
              <div className="text-3xl font-bold text-blue-400 tabular-nums leading-none mb-1">
                {stats.total_seen ?? 0}
              </div>
              <div className="text-xs text-gray-500">Total</div>
            </div>
          </div>
        </div>

        {/* Person list */}
        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
          <div className="px-4 pt-3 pb-1 shrink-0">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
              Riwayat
            </p>
          </div>
          <PersonList tracks={stats.tracks ?? []} />
        </div>

        {/* Server resources */}
        <div className="border-t border-gray-800 shrink-0">
          <div className="px-4 pt-3 pb-1">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
              Server
            </p>
          </div>
          <SystemStats token={token} />
        </div>

      </div>
    </div>
  )
}
