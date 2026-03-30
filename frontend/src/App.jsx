import { useState, useEffect, useCallback } from 'react'
import StreamSidebar from './components/StreamSidebar'
import CommandCenter from './components/CommandCenter'
import AddStreamModal from './components/AddStreamModal'

export default function App() {
  const [streams, setStreams] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [showModal, setShowModal] = useState(false)

  const fetchStreams = useCallback(async () => {
    try {
      const res = await fetch('/api/streams')
      const data = await res.json()
      setStreams(data)
      // Auto-select first stream if none selected
      setSelectedId(prev => (!prev && data.length > 0 ? data[0].id : prev))
    } catch (e) {
      console.error('Failed to fetch streams:', e)
    }
  }, [])

  useEffect(() => {
    fetchStreams()
    const t = setInterval(fetchStreams, 5000)
    return () => clearInterval(t)
  }, [fetchStreams])

  async function handleAdd(url, name) {
    const res = await fetch('/api/streams', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, name }),
    })
    const data = await res.json()
    setShowModal(false)
    setSelectedId(data.id)
    fetchStreams()
  }

  async function handleDelete(id) {
    await fetch(`/api/streams/${id}`, { method: 'DELETE' })
    setSelectedId(prev => (prev === id ? null : prev))
    fetchStreams()
  }

  return (
    <div className="flex h-screen bg-gray-950 text-white overflow-hidden flex-col">
      {/* Header */}
      <header className="h-12 bg-gray-900 border-b border-gray-800 flex items-center px-5 shrink-0 z-10">
        <div className="flex items-center gap-2.5">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="font-bold text-base tracking-tight">VisionTrack</span>
          <span className="text-gray-600 text-xs ml-1">RTSP · Person Tracking</span>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="ml-auto text-sm bg-green-500 hover:bg-green-400 active:bg-green-600 text-black font-semibold px-3 py-1.5 rounded-md transition-colors"
        >
          + Add Stream
        </button>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        <StreamSidebar
          streams={streams}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onDelete={handleDelete}
        />
        <CommandCenter streamId={selectedId} />
      </div>

      {showModal && (
        <AddStreamModal onAdd={handleAdd} onClose={() => setShowModal(false)} />
      )}
    </div>
  )
}
