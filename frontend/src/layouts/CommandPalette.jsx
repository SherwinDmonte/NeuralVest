// Command palette (Ctrl+K): search stocks (GET /stocks/search) and jump to pages. Arrow keys
// move, Enter opens, Esc closes.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, ChartLineUp, MagnifyingGlass } from '@phosphor-icons/react'
import { Modal } from '../components/motion'
import { searchStocks } from '../services/api'
import { NAV, SECONDARY } from './nav'

export default function CommandPalette({ open, onClose }) {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [stocks, setStocks] = useState([])
  const [active, setActive] = useState(0)
  const input = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    setQ('')
    setStocks([])
    setActive(0)
    const t = setTimeout(() => input.current?.focus(), 60)
    return () => clearTimeout(t)
  }, [open])

  useEffect(() => {
    const text = q.trim()
    if (!text) { setStocks([]); return undefined }
    const t = setTimeout(() => {
      searchStocks(text, 6).then((r) => {
        const list = r.items.map((i) => ({ symbol: i.symbol, name: i.company_name }))
        if (r.normalized && !list.some((i) => i.symbol === r.normalized)) list.push({ symbol: r.normalized, name: null })
        setStocks(list)
      }).catch(() => setStocks([]))
    }, 180)
    return () => clearTimeout(t)
  }, [q])

  const pages = useMemo(() => {
    const text = q.trim().toLowerCase()
    return [...NAV, ...SECONDARY].filter((p) => !text || p.label.toLowerCase().includes(text) || p.description.toLowerCase().includes(text))
  }, [q])

  const items = [
    ...stocks.map((s) => ({ key: `s-${s.symbol}`, kind: 'stock', label: s.symbol, hint: s.name || 'Analyse this symbol', go: () => navigate(`/app/analysis?symbol=${encodeURIComponent(s.symbol)}`) })),
    ...pages.map((p) => ({ key: `p-${p.to}`, kind: 'page', label: p.label, hint: p.description, Icon: p.Icon, go: () => navigate(p.to) })),
  ]

  const choose = (item) => {
    if (!item) return
    item.go()
    onClose()
  }

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); choose(items[active]) }
  }

  return (
    <Modal open={open} onClose={onClose} title={null}>
      <div className="flex items-center gap-3 border-b border-line px-4">
        <MagnifyingGlass size={18} className="text-ink-muted" aria-hidden="true" />
        <input ref={input} value={q} onChange={(e) => { setQ(e.target.value); setActive(0) }} onKeyDown={onKeyDown}
               placeholder="Search a stock (RELIANCE, 500325) or a page" aria-label="Search stocks and pages"
               className="h-14 flex-1 bg-transparent body-3 text-ink outline-none placeholder:text-ink-muted" />
        <kbd className="rounded-md border border-line bg-raised px-1.5 figure caption-5 text-ink-muted">Esc</kbd>
      </div>
      <ul className="max-h-[60vh] overflow-y-auto p-2" role="listbox" aria-label="Results">
        {stocks.length > 0 && <li className="px-3 pb-1 pt-2 caption-3 text-ink-muted">Stocks</li>}
        {items.map((it, i) => (
          <li key={it.key} role="option" aria-selected={i === active}>
            {it.kind === 'page' && i === stocks.length && <p className="px-3 pb-1 pt-2 caption-3 text-ink-muted">Pages</p>}
            <button type="button" onMouseEnter={() => setActive(i)} onClick={() => choose(it)}
                    className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition-colors duration-200 ease-nv ${i === active ? 'bg-raised' : ''}`}>
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-line bg-surface text-accent-ink">
                {it.kind === 'stock' ? <ChartLineUp size={16} aria-hidden="true" /> : <it.Icon size={16} aria-hidden="true" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className={`block body-5 text-ink ${it.kind === 'stock' ? 'figure' : ''}`}>{it.label}</span>
                <span className="block truncate caption-5 text-ink-muted">{it.hint}</span>
              </span>
              {i === active && <ArrowRight size={16} className="text-ink-muted" aria-hidden="true" />}
            </button>
          </li>
        ))}
      </ul>
    </Modal>
  )
}
