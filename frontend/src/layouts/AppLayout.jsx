import { Activity } from 'lucide-react'
import { Outlet } from 'react-router-dom'
import { Disclaimer } from '../components/ui'

export default function AppLayout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-page/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <Activity className="h-6 w-6 text-accent" aria-hidden="true" />
            <span className="text-lg font-semibold tracking-tight">NeuralVest</span>
            <span className="hidden text-xs text-ink-muted sm:inline">AI-powered financial intelligence</span>
          </div>
          <span className="rounded-full border border-line px-2 py-0.5 text-[11px] text-ink-muted">MVP · Phase 8</span>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8">
        <Disclaimer />
      </footer>
    </div>
  )
}
