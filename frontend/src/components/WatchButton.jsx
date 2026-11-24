// Add or remove a stock from the user's watchlist (task 12.4.4).
import { Star } from '@phosphor-icons/react'
import { Button } from './ui'
import { useWatchlist } from '../hooks/useWatchlist'

export default function WatchButton({ symbol }) {
  const { symbols, toggle, saving } = useWatchlist()
  if (!symbol) return null
  const watching = symbols.includes(symbol)
  return (
    <Button variant="secondary" size="sm" onClick={() => toggle(symbol)} disabled={saving} aria-pressed={watching}>
      <Star size={16} weight={watching ? 'fill' : 'regular'} className={watching ? 'text-warning' : ''} aria-hidden="true" />
      {watching ? 'On your watchlist' : 'Add to watchlist'}
    </Button>
  )
}
