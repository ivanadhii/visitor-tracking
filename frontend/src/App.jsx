import { useState, useEffect, useCallback, useMemo } from 'react'
import { Brain, LogOut } from 'lucide-react'
import StreamSidebar from './components/StreamSidebar'
import CommandCenter from './components/CommandCenter'
import AddStreamModal from './components/AddStreamModal'
import LoginPage from './components/LoginPage'

function getStoredAuth() {
  try {
    return {
      token: localStorage.getItem('vt_token') || null,
      username: localStorage.getItem('vt_username') || null,
    }
  } catch {
    return { token: null, username: null }
  }
}

export default function App() {
  const [token, setToken] = useState(getStoredAuth().token)
  const [username, setUsername] = useState(getStoredAuth().username)
  const [authRequired, setAuthRequired] = useState(false)
  const [streams, setStreams] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [showModal, setShowModal] = useState(false)

  const headers = useCallback(
    (extra = {}) => ({
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...extra,
    }),
    [token]
  )

  // Check auth status on mount
  useEffect(() => {
    fetch('/api/auth/me', { headers: headers() })
      .then(r => {
        if (r.status === 401) {
          setAuthRequired(true)
          setToken(null)
          setUsername(null)
          localStorage.removeItem('vt_token')
          localStorage.removeItem('vt_username')
        } else {
          return r.json().then(d => setAuthRequired(d.auth_required))
        }
      })
      .catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const fetchStreams = useCallback(async () => {
    try {
      const res = await fetch('/api/streams', { headers: headers() })
      if (res.status === 401) {
        setAuthRequired(true)
        setToken(null)
        setUsername(null)
        localStorage.removeItem('vt_token')
        localStorage.removeItem('vt_username')
        return
      }
      const data = await res.json()
      setStreams(data)
      setSelectedId(prev => (!prev && data.length > 0 ? data[0].id : prev))
    } catch (e) {
      console.error('Failed to fetch streams:', e)
    }
  }, [headers])

  useEffect(() => {
    if (authRequired && !token) return
    fetchStreams()
    const t = setInterval(fetchStreams, 5000)
    return () => clearInterval(t)
  }, [fetchStreams, authRequired, token])

  function handleLogin(newToken, newUsername) {
    setToken(newToken)
    setUsername(newUsername)
    setAuthRequired(false)
    localStorage.setItem('vt_token', newToken)
    localStorage.setItem('vt_username', newUsername)
  }

  async function handleLogout() {
    await fetch('/api/auth/logout', {
      method: 'POST',
      headers: headers(),
    })
    setToken(null)
    setUsername(null)
    setAuthRequired(true)
    setStreams([])
    localStorage.removeItem('vt_token')
    localStorage.removeItem('vt_username')
  }

  async function handleAdd(url, name) {
    const res = await fetch('/api/streams', {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ url, name }),
    })
    const data = await res.json()
    setShowModal(false)
    setSelectedId(data.id)
    fetchStreams()
  }

  async function handleDelete(id) {
    await fetch(`/api/streams/${id}`, { method: 'DELETE', headers: headers() })
    setSelectedId(prev => (prev === id ? null : prev))
    fetchStreams()
  }

  const allDetectionOn = useMemo(
    () => streams.length > 0 && streams.every(s => s.detection !== false),
    [streams]
  )

  async function handleToggleAllDetection() {
    const next = !allDetectionOn
    setStreams(prev => prev.map(s => ({ ...s, detection: next })))
    await fetch('/api/streams', {
      method: 'PATCH',
      headers: headers(),
      body: JSON.stringify({ detection: next }),
    })
  }

  async function handleToggleDetection(id, enabled) {
    setStreams(prev =>
      prev.map(s => (s.id === id ? { ...s, detection: enabled } : s))
    )
    await fetch(`/api/streams/${id}`, {
      method: 'PATCH',
      headers: headers(),
      body: JSON.stringify({ detection: enabled }),
    })
  }

  // Show login if auth is required and no valid token
  if (authRequired && !token) {
    return <LoginPage onLogin={handleLogin} />
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

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={handleToggleAllDetection}
            disabled={streams.length === 0}
            className={`flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-md transition-colors disabled:opacity-30 disabled:cursor-not-allowed ${
              allDetectionOn
                ? 'bg-green-500/20 hover:bg-red-500/20 text-green-400 hover:text-red-400 border border-green-500/30 hover:border-red-500/30'
                : 'bg-gray-700 hover:bg-green-500/20 text-gray-400 hover:text-green-400 border border-gray-600 hover:border-green-500/30'
            }`}
            title={allDetectionOn ? 'Turn off AI detection for all streams' : 'Turn on AI detection for all streams'}
          >
            <Brain size={14} />
            {allDetectionOn ? 'AI On' : 'AI Off'}
          </button>

          <button
            onClick={() => setShowModal(true)}
            className="text-sm bg-green-500 hover:bg-green-400 active:bg-green-600 text-black font-semibold px-3 py-1.5 rounded-md transition-colors"
          >
            + Add Stream
          </button>

          {token && (
            <div className="flex items-center gap-2 pl-2 border-l border-gray-700">
              <span className="text-xs text-gray-500">{username}</span>
              <button
                onClick={handleLogout}
                className="text-gray-500 hover:text-red-400 transition-colors p-1"
                title="Logout"
              >
                <LogOut size={14} />
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        <StreamSidebar
          streams={streams}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onDelete={handleDelete}
          onToggleDetection={handleToggleDetection}
        />
        <CommandCenter streamId={selectedId} token={token} />
      </div>

      {showModal && (
        <AddStreamModal onAdd={handleAdd} onClose={() => setShowModal(false)} />
      )}
    </div>
  )
}
