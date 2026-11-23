// PLACEHOLDER (Phase 1): a minimal page that only verifies React + Vite + Tailwind + Lucide work.
// It is replaced by the real dashboard in Phase 6.
import { Activity } from 'lucide-react'

export default function App() {
  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-md w-full rounded-2xl border border-white/10 bg-navy-900 p-8 shadow-xl">
        <div className="flex items-center gap-3">
          <Activity className="h-7 w-7 text-accent" aria-hidden="true" />
          <h1 className="text-2xl font-semibold tracking-tight">NeuralVest</h1>
        </div>
        <p className="mt-3 text-slate-400">
          Development environment check: React, Vite, Tailwind CSS and Lucide icons are working.
        </p>
        <p className="mt-6 text-xs text-slate-500">Phase 1 placeholder page</p>
      </div>
    </main>
  )
}
