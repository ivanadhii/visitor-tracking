import { Trash2, Video, Eye, EyeOff } from 'lucide-react'

export default function StreamSidebar({ streams, selectedId, onSelect, onDelete, onToggleDetection }) {
  return (
    <aside className="w-52 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
      <div className="px-4 py-3 border-b border-gray-800">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
          Streams ({streams.length})
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {streams.length === 0 && (
          <div className="text-center py-8 text-gray-600">
            <Video size={24} className="mx-auto mb-2 opacity-40" />
            <p className="text-xs">No streams yet</p>
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
              className={`w-full text-left px-3 py-2.5 rounded-lg text-sm group flex items-start justify-between transition-colors ${
                isSelected
                  ? 'bg-gray-700/80 text-white ring-1 ring-gray-600'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
              }`}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <div
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      stream.connected ? 'bg-green-400' : 'bg-gray-600'
                    }`}
                  />
                  <span className="font-medium truncate">{stream.name}</span>
                </div>
                <div className="pl-3 text-xs text-gray-500">
                  {!detectionOn ? (
                    <span className="text-gray-600">detection off</span>
                  ) : stream.connected ? (
                    <span>
                      <span className="text-green-500">{active}</span> active
                    </span>
                  ) : (
                    <span className="text-yellow-600/70">
                      {stream.error ?? 'connecting…'}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-0.5 ml-1 shrink-0 opacity-0 group-hover:opacity-100 transition">
                <button
                  onClick={e => {
                    e.stopPropagation()
                    onToggleDetection(stream.id, !detectionOn)
                  }}
                  className={`p-0.5 transition ${
                    detectionOn
                      ? 'text-green-500 hover:text-yellow-400'
                      : 'text-gray-600 hover:text-green-400'
                  }`}
                  title={detectionOn ? 'Turn off detection' : 'Turn on detection'}
                >
                  {detectionOn ? <Eye size={13} /> : <EyeOff size={13} />}
                </button>
                <button
                  onClick={e => {
                    e.stopPropagation()
                    onDelete(stream.id)
                  }}
                  className="text-gray-600 hover:text-red-400 p-0.5 transition"
                  title="Remove stream"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </button>
          )
        })}
      </div>
    </aside>
  )
}
