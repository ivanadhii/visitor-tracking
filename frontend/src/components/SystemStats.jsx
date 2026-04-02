import { useEffect, useState } from 'react'
import { Cpu, MemoryStick, HardDrive, Zap } from 'lucide-react'

function Bar({ percent, warn = 70, danger = 90 }) {
  const color =
    percent >= danger ? 'bg-red-500' :
    percent >= warn   ? 'bg-yellow-500' :
                        'bg-green-500'
  return (
    <div className="h-1 w-full bg-gray-700 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-500 ${color}`}
        style={{ width: `${Math.min(percent, 100)}%` }}
      />
    </div>
  )
}

function Row({ icon: Icon, label, value, percent, warn, danger }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5 text-gray-400">
          <Icon size={11} className="shrink-0" />
          <span>{label}</span>
        </div>
        <span className="text-gray-300 tabular-nums">{value}</span>
      </div>
      <Bar percent={percent} warn={warn} danger={danger} />
    </div>
  )
}

export default function SystemStats({ token }) {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    const headers = token ? { Authorization: `Bearer ${token}` } : {}

    async function fetch_stats() {
      try {
        const res = await fetch('/api/system', { headers })
        if (res.ok) setStats(await res.json())
      } catch {}
    }

    fetch_stats()
    const t = setInterval(fetch_stats, 4000)
    return () => clearInterval(t)
  }, [token])

  if (!stats) return (
    <div className="px-4 py-3 text-xs text-gray-600 animate-pulse">Loading…</div>
  )

  return (
    <div className="px-4 py-3 space-y-3">
      <Row
        icon={Cpu}
        label="CPU"
        value={`${stats.cpu}%`}
        percent={stats.cpu}
      />
      <Row
        icon={MemoryStick}
        label="RAM"
        value={`${stats.ram.used_gb} / ${stats.ram.total_gb} GB`}
        percent={stats.ram.percent}
      />
      <Row
        icon={HardDrive}
        label="Disk"
        value={`${stats.disk.used_gb} / ${stats.disk.total_gb} GB`}
        percent={stats.disk.percent}
        warn={80}
        danger={95}
      />
      {stats.gpu && (
        <>
          <Row
            icon={Zap}
            label="GPU"
            value={`${stats.gpu.util}%`}
            percent={stats.gpu.util}
          />
          <Row
            icon={Zap}
            label="VRAM"
            value={`${stats.gpu.mem_used_mb} / ${stats.gpu.mem_total_mb} MB`}
            percent={Math.round(stats.gpu.mem_used_mb / stats.gpu.mem_total_mb * 100)}
          />
          <div className="flex justify-between text-xs text-gray-600">
            <span className="truncate">{stats.gpu.name}</span>
            <span className="shrink-0 ml-2">{stats.gpu.temp_c}°C</span>
          </div>
        </>
      )}
    </div>
  )
}
