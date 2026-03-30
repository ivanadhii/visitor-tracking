import { Users } from 'lucide-react'

function fmtTime(ts) {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function fmtDuration(first, last) {
  const s = Math.max(0, Math.floor(last - first))
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}

function PersonCard({ track }) {
  return (
    <div
      className={`rounded-lg p-2.5 transition-colors ${
        track.active
          ? 'bg-gray-800 ring-1 ring-green-500/30'
          : 'bg-gray-800/40 ring-1 ring-gray-700/40'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-sm truncate">{track.tag}</span>
        <span
          className={`shrink-0 text-xs px-1.5 py-0.5 rounded-full font-medium ${
            track.active
              ? 'bg-green-500/15 text-green-400'
              : 'bg-gray-700 text-gray-500'
          }`}
        >
          {track.active ? '● Active' : '○ Gone'}
        </span>
      </div>

      <div className="mt-1.5 flex items-center gap-1.5 text-xs text-gray-500 flex-wrap">
        <span title="First seen">{fmtTime(track.first_seen)}</span>
        <span className="text-gray-700">·</span>
        <span title="Duration">{fmtDuration(track.first_seen, track.last_seen)}</span>
        {track.active && track.confidence > 0 && (
          <>
            <span className="text-gray-700">·</span>
            <span className="text-green-600/80">
              {(track.confidence * 100).toFixed(0)}%
            </span>
          </>
        )}
      </div>
    </div>
  )
}

export default function PersonList({ tracks }) {
  const active = tracks.filter(t => t.active)
  const past = tracks.filter(t => !t.active)

  if (tracks.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-600 p-4">
        <Users size={32} className="mb-2 opacity-30" />
        <p className="text-sm">No detections yet</p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
      {active.length > 0 && (
        <>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest py-1">
            Active ({active.length})
          </p>
          {active.map(t => (
            <PersonCard key={t.track_id} track={t} />
          ))}
        </>
      )}

      {past.length > 0 && (
        <>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest py-1 mt-2">
            Past ({past.length})
          </p>
          {past.map(t => (
            <PersonCard key={t.track_id} track={t} />
          ))}
        </>
      )}
    </div>
  )
}
