// Stock picker: type a symbol or company name, pick from GET /stocks/search, or press Enter to
// add what you typed (the API validates it). Chips show the chosen stocks.
import { useEffect, useId, useRef, useState } from 'react'
import { MagnifyingGlass, X } from '@phosphor-icons/react'
import { searchStocks } from '../services/api'
import { shortSymbol } from '../utils/format'

export default function SymbolPicker({ value, onChange, max = 10, label = 'Stocks', placeholder = 'Search', single = false, hint }) {
  const [q, setQ] = useState('')
  const [items, setItems] = useState([])
  const [active, setActive] = useState(0)
  const [open, setOpen] = useState(false)
  const id = useId()
  const timer = useRef(null)

  useEffect(() => {
    clearTimeout(timer.current)
    const text = q.trim()
    if (!text) {
      setItems([])
      return undefined
    }
    timer.current = setTimeout(() => {
      searchStocks(text, 8)
        .then((r) => {
          const list = r.items.map((i) => ({ symbol: i.symbol, name: i.company_name }))
          if (r.normalized && !list.some((i) => i.symbol === r.normalized)) list.push({ symbol: r.normalized, name: null, typed: true })
          setItems(list)
          setActive(0)
        })
        .catch(() => setItems([]))
    }, 200)
    return () => clearTimeout(timer.current)
  }, [q])

  const add = (symbol) => {
    if (!symbol) return
    const next = single ? [symbol] : value.includes(symbol) ? value : [...value, symbol].slice(0, max)
    onChange(next)
    setQ('')
    setItems([])
    setOpen(false)
  }

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((a) => Math.min(a + 1, items.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter') {
      if (!q.trim()) return
      e.preventDefault()
      add(items[active]?.symbol || q.trim().toUpperCase())
    } else if (e.key === 'Escape') {
      setOpen(false)
    } else if (e.key === 'Backspace' && !q && value.length && !single) {
      onChange(value.slice(0, -1))
    }
  }

  const full = !single && value.length >= max
  return (
    <div className="relative">
      <label htmlFor={id} className="mb-1 block title-4 text-ink-secondary">{label}</label>
      <div className="flex min-h-10 flex-wrap items-center gap-2 rounded-lg border border-line bg-raised px-3 py-1 transition-colors duration-300 ease-nv focus-within:border-accent hover:border-line-strong">
        <MagnifyingGlass size={16} className="text-ink-muted" aria-hidden="true" />
        {value.map((s) => (
          <span key={s} className="inline-flex items-center gap-1 rounded-md border border-line bg-surface py-0.5 pl-2 pr-1 caption-4 text-ink">
            {shortSymbol(s)}<span className="text-ink-muted">{s.slice(shortSymbol(s).length)}</span>
            <button type="button" onClick={() => onChange(value.filter((v) => v !== s))}
                    className="rounded p-0.5 text-ink-muted transition-colors duration-300 ease-nv hover:bg-raised hover:text-ink" aria-label={`Remove ${s}`}>
              <X size={12} aria-hidden="true" />
            </button>
          </span>
        ))}
        <input
          id={id}
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true) }}
          onKeyDown={onKeyDown}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          disabled={full}
          placeholder={full ? `Up to ${max} stocks` : value.length && !single ? 'Add another' : placeholder}
          role="combobox"
          aria-expanded={open && items.length > 0}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          aria-describedby={hint ? `${id}-hint` : undefined}
          className="min-w-24 flex-1 bg-transparent py-1 body-6 text-ink outline-none placeholder:text-ink-muted"
          autoComplete="off"
          maxLength={50}
        />
      </div>
      {hint && <p id={`${id}-hint`} className="mt-1 caption-5 text-ink-muted">{hint}</p>}
      {open && items.length > 0 && (
        <ul id={`${id}-list`} role="listbox" className="absolute inset-x-0 top-full z-20 mt-2 max-h-72 overflow-auto rounded-xl border border-line bg-raised p-1 shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
          {items.map((it, i) => (
            <li key={it.symbol} role="option" aria-selected={i === active}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => add(it.symbol)}
                onMouseEnter={() => setActive(i)}
                className={`flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition-colors duration-300 ease-nv ${i === active ? 'bg-raised-2' : ''}`}
              >
                <span className="figure caption-2 text-ink">{it.symbol}</span>
                <span className="truncate caption-5 text-ink-muted">{it.name || (it.typed ? 'Analyse this symbol' : 'Name appears after the first analysis')}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
