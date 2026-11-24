// Sidebar status: the API, MongoDB and the local AI model, from the real health endpoints
// (refreshed every 60 s while the page is open).
import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { getDbHealth, getLlmHealth } from '../services/api'

function Dot({ ok, label }) {
  const cls = ok == null ? 'bg-ink-muted' : ok ? 'bg-good shadow-[0_0_8px_var(--nv-good)]' : 'bg-critical'
  return <span className={`h-2 w-2 shrink-0 rounded-full ${cls}`} aria-label={label} />
}

export function useSystemStatus() {
  const db = useApi(getDbHealth, [], { key: 'health-db', ttl: 60000 })
  const llm = useApi(getLlmHealth, [], { key: 'health-llm', ttl: 60000 })
  return { db, llm }
}

export default function SystemStatus({ collapsed }) {
  const { db, llm } = useSystemStatus()
  const dbOk = db.data ? Boolean(db.data.connected) : db.error ? false : null
  const llmOk = llm.data ? Boolean(llm.data.available) : llm.error ? false : null
  const model = llm.data?.would_use
  if (collapsed) {
    return (
      <Link to="/app/settings" title={`Database ${dbOk ? 'connected' : 'unavailable'} · AI model ${llmOk ? model : 'unavailable'}`}
            className="mx-auto flex w-10 flex-col items-center gap-1 rounded-xl border border-line bg-surface/60 py-2">
        <Dot ok={dbOk} label={`Database ${dbOk ? 'connected' : 'unavailable'}`} />
        <Dot ok={llmOk} label={`AI model ${llmOk ? 'available' : 'unavailable'}`} />
      </Link>
    )
  }
  return (
    <Link to="/app/settings" className="block rounded-xl border border-line bg-surface/60 p-3 transition-colors duration-300 ease-nv hover:border-line-strong">
      <p className="mb-2 caption-3 text-ink-muted">System status</p>
      <div className="space-y-1.5 caption-4 text-ink-secondary">
        <div className="flex items-center gap-2"><Dot ok={dbOk} label="" /><span className="flex-1">Database</span><span className="text-ink-muted">{dbOk == null ? 'checking' : dbOk ? `${Math.round(db.data.latency_ms)} ms` : 'offline'}</span></div>
        <div className="flex items-center gap-2"><Dot ok={llmOk} label="" /><span className="flex-1">AI model</span><span className="truncate figure text-ink-muted">{llmOk == null ? 'checking' : llmOk ? model || 'no model' : 'offline'}</span></div>
      </div>
    </Link>
  )
}
