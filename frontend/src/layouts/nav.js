// Navigation model shared by the sidebar, the top bar title and the command palette.
import {
  ChartLineUp,
  ChartPieSlice,
  FileText,
  Gauge,
  GearSix,
  Globe,
  Newspaper,
  Question,
  ShieldWarning,
  Star,
  TreeStructure,
} from '@phosphor-icons/react'

export const NAV = [
  { to: '/app', label: 'Overview', Icon: Gauge, end: true, description: 'Market overview, watchlist and your latest activity' },
  { to: '/app/market', label: 'Market intelligence', Icon: Globe, description: 'NIFTY 50, SENSEX and the 30 curated stocks' },
  { to: '/app/analysis', label: 'Stock analysis', Icon: ChartLineUp, description: 'Run the five agents on one or more stocks' },
  { to: '/app/news', label: 'Financial news', Icon: Newspaper, description: 'Stored articles with AI sentiment' },
  { to: '/app/agents', label: 'AI agents', Icon: TreeStructure, description: 'The agent network and each step of a run' },
  { to: '/app/risk', label: 'Risk analysis', Icon: ShieldWarning, description: 'Volatility, drawdown, beta, Sharpe and correlation' },
  { to: '/app/portfolio', label: 'Portfolio optimization', Icon: ChartPieSlice, description: 'Allocation, whole shares and a backtest' },
  { to: '/app/reports', label: 'Reports', Icon: FileText, description: 'Saved reports, comparison and PDF' },
  { to: '/app/watchlist', label: 'Watchlist', Icon: Star, description: 'Stocks you follow, with end of day prices' },
]

export const SECONDARY = [
  { to: '/app/settings', label: 'Settings', Icon: GearSix, description: 'Theme, layout and system status' },
  { to: '/app/help', label: 'Help', Icon: Question, description: 'How NeuralVest works and what its numbers mean' },
]

export function titleFor(pathname) {
  const all = [...NAV, ...SECONDARY]
  if (pathname.startsWith('/app/reports/compare')) return 'Compare reports'
  if (pathname.startsWith('/app/reports/')) return 'Report'
  return (all.find((n) => (n.end ? pathname === n.to : pathname.startsWith(n.to))) || NAV[0]).label
}
