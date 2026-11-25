// Financial News (task 12.3.5): stored articles for a stock with sentiment filters, the
// sentiment breakdown and links to the original sources.
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CaretLeft, CaretRight, Newspaper } from '@phosphor-icons/react'
import { ArticleList } from '../components/NewsList'
import { SentimentBar } from '../components/charts'
import SymbolPicker from '../components/SymbolPicker'
import { Button, Card, CardSkeleton, EmptyState, ErrorState, Input, Meta, PageHeader, Select, Skeleton, ToneBadge } from '../components/ui'
import { AnimatedTabs } from '../components/motion'
import { errorMessage, getNews, getNewsSentiment } from '../services/api'
import { fmtDateTime } from '../utils/format'
import { usePageTitle } from '../hooks/usePageTitle'

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'positive', label: 'Positive' },
  { value: 'negative', label: 'Negative' },
  { value: 'neutral', label: 'Neutral' },
  { value: 'uncertain', label: 'Uncertain' },
]
const PAGE_SIZE = 20

export default function NewsPage() {
  usePageTitle('Financial news')
  const [params, setParams] = useSearchParams()
  const symbol = params.get('symbol') || ''
  const [sentiment, setSentiment] = useState('')
  const [page, setPage] = useState(1)
  const [days, setDays] = useState(14)
  const [q, setQ] = useState('')
  const [publisher, setPublisher] = useState('')
  const [news, setNews] = useState({ data: null, error: null, loading: false })
  const [summary, setSummary] = useState(null)

  useEffect(() => {
    if (!symbol) return undefined
    let alive = true
    setNews((s) => ({ ...s, loading: true, error: null }))
    getNews(symbol, { page, page_size: PAGE_SIZE, ...(sentiment ? { sentiment } : {}) })
      .then((data) => alive && setNews({ data, error: null, loading: false }))
      .catch((err) => alive && setNews({ data: null, error: errorMessage(err), loading: false }))
    return () => { alive = false }
  }, [symbol, sentiment, page])

  useEffect(() => {
    if (!symbol) return undefined
    let alive = true
    setSummary(null)
    getNewsSentiment(symbol, days).then((d) => alive && setSummary(d)).catch(() => alive && setSummary({ error: true }))
    return () => { alive = false }
  }, [symbol, days])

  const pages = news.data ? Math.max(1, Math.ceil(news.data.total / PAGE_SIZE)) : 1

  return (
    <div className="space-y-6">
      <PageHeader title="What the news says" description="Articles collected by the Financial News agent, newest first, with the sentiment a local AI model gave each one." />
      <Card>
        <SymbolPicker value={symbol ? [symbol] : []} single label="Stock" placeholder="Search a symbol or company name"
                      onChange={(v) => { setParams(v[0] ? { symbol: v[0] } : {}); setPage(1) }} />
      </Card>

      {!symbol && (
        <EmptyState icon={Newspaper} title="Choose a stock">
          News is stored when a stock is analysed. Pick one you have analysed, or run an analysis first to collect its last 14 days of news.
        </EmptyState>
      )}

      {symbol && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <AnimatedTabs size="sm" label="Filter by sentiment" tabs={FILTERS} value={sentiment} onChange={(v) => { setSentiment(v); setPage(1) }} />
              {news.data && <Meta>{news.data.total} articles</Meta>}
            </div>
            {news.data && news.data.items.length > 0 && (
              <div className="grid gap-3 sm:grid-cols-[1fr_200px]">
                <Input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search headlines on this page" aria-label="Search headlines on this page" />
                <Select value={publisher} onChange={(e) => setPublisher(e.target.value)} aria-label="Publisher">
                  <option value="">All publishers</option>
                  {[...new Set(news.data.items.map((a) => a.publisher))].sort().map((pb) => <option key={pb} value={pb}>{pb}</option>)}
                </Select>
              </div>
            )}
            {news.loading && <CardSkeleton rows={6} />}
            {news.error && <ErrorState message={news.error} />}
            {news.data && !news.loading && (
              news.data.items.length ? (
                <Card>
                  {(() => {
                    const t = q.trim().toLowerCase()
                    const shown = news.data.items.filter((a) => (!publisher || a.publisher === publisher) && (!t || `${a.headline} ${a.summary || ''} ${a.publisher}`.toLowerCase().includes(t)))
                    return shown.length ? <ArticleList articles={shown} /> : <p className="body-6 text-ink-muted">No article on this page matches. Clear the search or the publisher.</p>
                  })()}
                  {pages > 1 && (
                    <nav aria-label="Pages" className="mt-6 flex items-center justify-between gap-3 border-t border-line pt-4">
                      <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                        <CaretLeft size={16} aria-hidden="true" /> Newer
                      </Button>
                      <Meta>page {page} of {pages}</Meta>
                      <Button size="sm" variant="secondary" disabled={!news.data.has_next} onClick={() => setPage((p) => p + 1)}>
                        Older <CaretRight size={16} aria-hidden="true" />
                      </Button>
                    </nav>
                  )}
                </Card>
              ) : (
                <EmptyState icon={Newspaper} title={sentiment ? `No ${sentiment} articles` : 'No stored articles'}>
                  {sentiment ? 'Try another filter.' : `Analyse ${symbol} to collect its recent news.`}
                </EmptyState>
              )
            )}
            {news.data && <p className="caption-5 text-ink-muted">{news.data.disclaimer}</p>}
          </div>

          <Card title="Sentiment" subtitle="Published in the selected period"
                actions={
                  <Select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Period" className="w-auto">
                    {[7, 14, 30, 90].map((d) => <option key={d} value={d}>Last {d} days</option>)}
                  </Select>
                }>
            {!summary && <div className="space-y-3"><Skeleton className="h-4 w-full" /><Skeleton className="h-3 w-2/3" /></div>}
            {summary?.error && <ErrorState message="The sentiment summary could not be loaded." />}
            {summary && !summary.error && (
              <div className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="caption-2 text-ink-secondary">Overall</span>
                  <ToneBadge value={summary.overall_sentiment} />
                </div>
                {summary.articles ? <SentimentBar breakdown={summary.breakdown} /> : <p className="body-6 text-ink-muted">{summary.note}</p>}
                <p className="caption-5 text-ink-muted">Rule: {summary.rule}.</p>
                {summary.latest_article_at && <Meta className="block">latest article {fmtDateTime(summary.latest_article_at)}</Meta>}
                <p className="caption-5 text-ink-muted">{summary.disclaimer}</p>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
