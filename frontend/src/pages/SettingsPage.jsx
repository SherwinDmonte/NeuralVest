// Settings (Phase 12B): appearance, account and system status (from the real health endpoints).
import { CheckCircle, Database, Desktop, Moon, Robot, Sun, User, WarningCircle } from '@phosphor-icons/react'
import { useAuth } from '../auth/AuthContext'
import { useTheme } from '../theme/ThemeContext'
import { Button, Card, Meta, PageHeader, Skeleton } from '../components/ui'
import ProfilePicture from '../components/ProfilePicture'
import { useApi } from '../hooks/useApi'
import { getDbHealth, getHealth, getLlmHealth } from '../services/api'
import { fmtDate, num } from '../utils/format'
import { usePageTitle } from '../hooks/usePageTitle'

const THEMES = [
  ['dark', 'Dark', Moon, 'Navy surfaces, made for long sessions'],
  ['light', 'Light', Sun, 'Bright surfaces for daylight'],
  ['system', 'System', Desktop, 'Follows your operating system'],
]

function Preview({ dark }) {
  return (
    <div className={`overflow-hidden rounded-xl border ${dark ? 'border-[#1e2e49] bg-[#080d18]' : 'border-[#e2e8f0] bg-[#f4f7fc]'}`} aria-hidden="true">
      <div className="flex gap-2 p-2">
        <div className={`h-16 w-6 rounded-md ${dark ? 'bg-[#0b1220]' : 'bg-white'}`} />
        <div className="flex-1 space-y-2">
          <div className={`h-4 rounded ${dark ? 'bg-[#111c30]' : 'bg-white'}`} />
          <div className={`flex h-10 items-end rounded p-1 ${dark ? 'bg-[#111c30]' : 'bg-white'}`}>
            <div className="h-1 w-full rounded bg-[linear-gradient(90deg,#16c7b7,#438bff,#9b6bff)]" />
          </div>
        </div>
      </div>
    </div>
  )
}

function Row({ label, children }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line py-2 last:border-0">
      <span className="caption-2 text-ink-secondary">{label}</span>
      <span className="text-right figure caption-2 text-ink">{children}</span>
    </div>
  )
}

function Ok({ ok, children }) {
  return (
    <span className="inline-flex items-center gap-1">
      {ok ? <CheckCircle size={14} weight="fill" className="text-good" aria-hidden="true" /> : <WarningCircle size={14} weight="fill" className="text-critical" aria-hidden="true" />}
      {children}
    </span>
  )
}

export default function SettingsPage() {
  usePageTitle('Settings')
  const { user, logout } = useAuth()
  const { choice, setChoice } = useTheme()
  const api = useApi(getHealth, [], { key: 'health', ttl: 60000 })
  const db = useApi(getDbHealth, [], { key: 'health-db', ttl: 60000 })
  const llm = useApi(getLlmHealth, [], { key: 'health-llm', ttl: 60000 })

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Settings" title="Settings and system status" description="Appearance is saved in this browser. Account details come from your NeuralVest account." />

      <Card title="Appearance" subtitle="Choose a theme. It changes every page, chart and menu." icon={Sun}>
        <div className="grid gap-4 sm:grid-cols-3" role="radiogroup" aria-label="Theme">
          {THEMES.map(([v, label, Icon, desc]) => (
            <button key={v} type="button" role="radio" aria-checked={choice === v} onClick={() => setChoice(v)}
                    className={`rounded-2xl border p-3 text-left transition-[border-color,transform,box-shadow] duration-300 ease-nv hover:-translate-y-0.5 ${choice === v ? 'border-accent shadow-[0_0_0_3px_color-mix(in_srgb,var(--nv-accent)_20%,transparent)]' : 'border-line hover:border-line-strong'}`}>
              <Preview dark={v === 'dark' || (v === 'system' && !window.matchMedia('(prefers-color-scheme: light)').matches)} />
              <div className="mt-3 flex items-center gap-2 body-5 text-ink"><Icon size={16} aria-hidden="true" />{label}</div>
              <p className="caption-5 text-ink-muted">{desc}</p>
            </button>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Account" icon={User}>
          <div className="mb-4"><ProfilePicture /></div>
          <Row label="Name">{user?.name}</Row>
          <Row label="Email">{user?.email}</Row>
          <Row label="Member since">{fmtDate(user?.created_at)}</Row>
          <Row label="Session">kept until this tab closes</Row>
          <Button variant="secondary" size="sm" className="mt-4" onClick={logout}>Log out</Button>
        </Card>

        <Card title="System status" subtitle="Checked when this page opened" icon={Database}>
          {(db.loading || llm.loading) && !db.data && <div className="space-y-2"><Skeleton className="h-5" /><Skeleton className="h-5" /><Skeleton className="h-5" /></div>}
          {api.data && <Row label="API">{api.data.status} · version {api.data.version}</Row>}
          {db.data && (
            <>
              <Row label="Database"><Ok ok={db.data.connected}>{db.data.connected ? `connected · ${Math.round(db.data.latency_ms)} ms` : 'unavailable'}</Ok></Row>
              {db.data.storage?.used_pct != null && <Row label="Storage used">{num(db.data.storage.used_pct, 1)}% of the free tier</Row>}
            </>
          )}
          {llm.data && (
            <>
              <Row label="Local AI (Ollama)"><Ok ok={llm.data.available}>{llm.data.available ? 'running' : 'not reachable'}</Ok></Row>
              <Row label="Model in use now">{llm.data.would_use || 'templates only'}</Row>
              <Row label="Free memory">{num(llm.data.free_ram_mb, 0)} MB (the larger model needs {num(llm.data.min_free_ram_mb_for_primary, 0)} MB)</Row>
              <Row label="Installed models">{llm.data.installed_models.join(', ') || 'none'}</Row>
            </>
          )}
          <Meta className="mt-3 block">The larger model is used only when enough memory is free; otherwise the smaller one answers.</Meta>
        </Card>
      </div>

      <Card title="About these numbers" icon={Robot}>
        <p className="body-6 text-ink-secondary">
          Prices and statements come from Yahoo Finance through the unofficial yfinance library, end of day. News comes
          from public RSS feeds. The local model only writes explanations; every figure is computed in Python and checked
          before a report is saved. NeuralVest is an educational project and not investment advice.
        </p>
      </Card>
    </div>
  )
}
