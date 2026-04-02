import { Trash2, Video, Eye, EyeOff } from 'lucide-react'

export default function StreamSidebar({ streams, selectedId, onSelect, onDelete, onToggleDetection }) {
  const connected = streams.filter(s => s.connected).length

  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">

      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800 shrink-0">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
            Kamera
          </p>
          <span className="text-xs text-gray-600">
            <span className="text-green-500 font-medium">{connected}</span>
            /{streams.length}
          </span>
        </div>
      </div>

      {/* Stream list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {streams.length === 0 && (
          <div className="text-center py-10 text-gray-700">
            <Video size={28} className="mx-auto mb-2 opacity-30" />
            <p className="text-xs">Belum ada stream</p>
          </div>
        )}

        {streams.map(stream => {
          const active = stream.stats?.active_count ?? 0
          const isSelected = stream.id === selectedId
          const detectionOn = stream.detection !== false

          return (
            <button
              key={stream.id}
              onClick={() => onSelect(stream.id)}
              className={`w-full text-left px-3 py-2.5 rounded-lg text-sm group flex items-start justify-between gap-1 transition-colors ${
                isSelected
                  ? 'bg-gray-700/80 text-white ring-1 ring-gray-600'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
              }`}
            >
              <div className="min-w-0 flex-1">
                {/* Name row */}
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    stream.connected ? 'bg-green-400' : 'bg-gray-600'
                  }`} />
                  <span className="font-medium text-xs truncate leading-tight">
                    {stream.name}
                  </span>
                </div>
                {/* Status row */}
                <div className="pl-3 text-xs text-gray-600 leading-tight">
                  {!detectionOn ? (
                    <span>AI off</span>
                  ) : stream.connected ? (
                    <span>
                      <span className="text-green-500">{active}</span> aktif
                    </span>
                  ) : (
                    <span className="text-yellow-700">
                      {stream.error ?? 'menghubungkan…'}
                    </span>
                  )}
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition mt-0.5">
                <button
                  onClick={e => { e.stopPropagation(); onToggleDetection(stream.id, !detectionOn) }}
                  className={`p-0.5 rounded transition ${
                    detectionOn
                      ? 'text-green-500/70 hover:text-yellow-400'
                      : 'text-gray-600 hover:text-green-400'
                  }`}
                  title={detectionOn ? 'Matikan deteksi' : 'Aktifkan deteksi'}
                >
                  {detectionOn ? <Eye size={12} /> : <EyeOff size={12} />}
                </button>
                <button
                  onClick={e => { e.stopPropagation(); onDelete(stream.id) }}
                  className="p-0.5 rounded text-gray-600 hover:text-red-400 transition"
                  title="Hapus stream"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </button>
          )
        })}
      </div>
    </aside>
  )
}
