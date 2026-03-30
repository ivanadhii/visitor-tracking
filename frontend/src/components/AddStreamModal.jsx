import { useState } from 'react'
import { X } from 'lucide-react'

export default function AddStreamModal({ onAdd, onClose }) {
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!url.trim()) return
    setError('')
    setLoading(true)
    try {
      await onAdd(url.trim(), name.trim() || `Camera ${Date.now()}`)
    } catch (err) {
      setError('Failed to add stream. Check the URL and try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-md shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-bold text-lg">Add RTSP Stream</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div>
            <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">
              Camera Name
            </label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Front Door, Lobby, Gate 1"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-green-500 placeholder-gray-600 transition-colors"
            />
          </div>

          {/* URL */}
          <div>
            <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">
              RTSP URL <span className="text-red-400">*</span>
            </label>
            <input
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="rtsp://user:pass@192.168.1.100:554/stream1"
              required
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-green-500 placeholder-gray-600 font-mono transition-colors"
            />
            <p className="mt-1.5 text-xs text-gray-600">
              Supports RTSP streams from IP cameras, NVRs, and RTSP servers
            </p>
          </div>

          {error && (
            <p className="text-xs text-red-400 bg-red-400/10 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 rounded-lg text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !url.trim()}
              className="flex-1 py-2 rounded-lg text-sm font-semibold bg-green-500 hover:bg-green-400 active:bg-green-600 text-black disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Starting…' : 'Add Stream'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
