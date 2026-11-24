// Watchlist (Phase 12B, task 12B.4.6): up to 20 stocks saved to your account, each with its last
// close, day change and a 60 day sparkline from GET /market/quotes (computed in Python).
import { useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { ChartLineUp, Newspaper, Star, Trash } from '@phosphor-icons/react'
import { Sparkline } from '../components/charts'
import { Modal } from '../components/motion'
import SymbolPicker from '../components/SymbolPicker'
import { Button, Card, Change, EmptyState, ErrorState, Meta, PageHeader, Skeleton } from '../components/ui'
import { useNotifications } from '../feedback/Notifications'
import { useApi } from '../hooks/useApi'
import { useWatchlist } from '../hooks/useWatchlist'
import { getQuotes } from '../services/api'
import { fmtDate, num, shortSymbol } from '../utils/format'
import { usePageTitle } from '../hooks/usePageTitle'

export default function WatchlistPage() {
  usePageTitle('Watchlist')
  const { symbols, loading, saving, error, save } = useWatchlist()
  const { notify } = useNotifications()
  const [confirm, setConfirm] = useState(false)
  const key = symbols.join(',')
  const quotes = useApi(() => getQuotes(symbols), [key], { key: `quotes-${key}`, enabled: symbols.length > 0 })
  const bySymbol = Object.fromEntries((quotes.data?.items || []).map((q) => [q.symbol, q]))

  const add = async (next) => {
    const added = next.filter((s) => !symbols.includes(s))
    await save([...added, ...symbols].slice(0, 20))
    if (added.length) notify({ tone: 'good', title: `Added ${added.map(shortSymbol).join(', ')} to your watchlist` })
  }
  const remove = async (s) => {
    await save(symbols.filter((x) => x !== s))
    notify({ tone: 'info', title: `Removed ${shortSymbol(s)} from your watchlist` })
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Watchlist" title="Stocks you follow" description="Saved to your account, up to 20 stocks. Prices are end of day from Yahoo Finance."
                  actions={symbols.length > 0 && <Button variant="secondary" size="sm" onClick={() => setConfirm(true)}><Trash size={16} aria-hidden="true" /> Clear all</Button>} />
      <Card>
        <SymbolPicker value={[]} onChange={add} max={20} label="Add stocks" placeholder="Search a symbol or company name, then press Enter" />
        <div className="mt-2 flex items-center justify-between gap-3">
          <Meta>{symbols.length} of 20 · {saving ? 'saving' : 'saved to your account'}</Meta>
          {error && <span role="alert" className="caption-5 text-critical">{error}</span>}
        </div>
      </Card>

      {!loading && !symbols.length && (
        <EmptyState icon={Star} title="Your watchlist is empty">Add stocks above, or use Add to watchlist on a stock&apos;s analysis. Their latest news then appears on the overview.</EmptyState>
      )}
      {quotes.error && <ErrorState message={quotes.error} />}

      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <AnimatePresence initial={false}>
          {symbols.map((s) => {
            const q = bySymbol[s]
            return (
              <motion.li key={s} layout initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }}
                         transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                         className="group relative overflow-hidden rounded-2xl border border-line bg-surface p-4 shadow-card transition-[border-color] duration-300 ease-nv hover:border-line-strong">
                <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-brand opacity-0 transition-opacity duration-300 ease-nv group-hover:opacity-80" aria-hidden="true" />
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="title-2 text-ink">{shortSymbol(s)}</p>
                    <Meta>{s}</Meta>
                  </div>
                  {q ? <Change value={q.change_pct} /> : quotes.loading ? <Skeleton className="h-6 w-16" /> : <Meta>no price</Meta>}
                </div>
                <div className="mt-3 flex items-end justify-between gap-4">
                  <div>
                    <div className="figure-1 text-ink">{q ? num(q.last_close) : quotes.loading ? <Skeleton className="h-8 w-28" /> : 'n/a'}</div>
                    {q && <Meta>{fmtDate(q.date)} close</Meta>}
                    {!q && quotes.data?.unavailable?.[s] && <p className="caption-5 text-warning">{quotes.data.unavailable[s]}</p>}
                  </div>
                  <div className="w-32">{q && <Sparkline data={q.series} height={48} up={q.change_pct >= 0} />}</div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-3">
                  <Button size="xs" variant="secondary" to={`/app/analysis?symbol=${encodeURIComponent(s)}`}><ChartLineUp size={14} aria-hidden="true" /> Analyze</Button>
                  <Button size="xs" variant="ghost" to={`/app/news?symbol=${encodeURIComponent(s)}`}><Newspaper size={14} aria-hidden="true" /> News</Button>
                  <Button size="xs" variant="ghost" className="ml-auto" onClick={() => remove(s)} aria-label={`Remove ${s}`}><Trash size={14} aria-hidden="true" /> Remove</Button>
                </div>
              </motion.li>
            )
          })}
        </AnimatePresence>
      </ul>

      <Modal open={confirm} onClose={() => setConfirm(false)} title="Clear the watchlist?">
        <div className="space-y-4 p-4">
          <p className="body-6 text-ink-secondary">This removes all {symbols.length} stocks from your watchlist. Reports and news are not affected.</p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setConfirm(false)}>Cancel</Button>
            <Button variant="danger" size="sm" onClick={async () => { setConfirm(false); await save([]); notify({ tone: 'info', title: 'Watchlist cleared' }) }}>Clear all</Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
