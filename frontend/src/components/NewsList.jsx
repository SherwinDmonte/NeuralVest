// News analysed by the Financial News Agent. The ORIGINAL headline (linked to the source)
// is always shown above the AI summary, so readers can check the model's wording.
import { Bot, ExternalLink } from 'lucide-react'
import { Card, Chip, EmptyState, ToneBadge } from './ui'
import { fmtDate } from '../utils/format'

const safeUrl = (url) => (typeof url === 'string' && /^https?:\/\//i.test(url) ? url : null)

export default function NewsList({ news }) {
  if (!news) return null
  const articles = news.articles || []
  return (
    <Card
      title="Financial news"
      subtitle={`Last ${news.lookback_days} days · ${news.articles_analyzed} analysed of ${news.articles_collected} found`}
      actions={<ToneBadge value={news.overall_sentiment} />}
    >
      {news.digest && (
        <div className="mb-4 rounded-lg border border-line bg-white/[0.02] p-3">
          <div className="mb-1 flex items-center gap-1.5 text-xs text-ink-muted">
            <Bot className="h-3.5 w-3.5" aria-hidden="true" />
            {news.digest_source === 'llm' ? 'AI digest' : 'Automatic digest (AI unavailable)'}
          </div>
          <p className="text-sm text-ink-secondary">{news.digest}</p>
        </div>
      )}
      {articles.length === 0 ? (
        <EmptyState>No recent articles mention this company in the configured news sources.</EmptyState>
      ) : (
        <ul className="divide-y divide-line">
          {articles.map((a) => {
            const href = safeUrl(a.article_url)
            return (
              <li key={a.url_hash} className="py-3 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  {href ? (
                    <a href={href} target="_blank" rel="noopener noreferrer"
                       className="group inline-flex max-w-full items-start gap-1 text-sm font-medium text-ink hover:text-accent">
                      <span>{a.headline}</span>
                      <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-60 group-hover:opacity-100" aria-hidden="true" />
                      <span className="sr-only">(opens original article in a new tab)</span>
                    </a>
                  ) : (
                    <span className="text-sm font-medium text-ink">{a.headline}</span>
                  )}
                  <ToneBadge value={a.sentiment} />
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-ink-muted">
                  <span>{a.publisher}</span>
                  <span aria-hidden="true">·</span>
                  <span>{fmtDate(a.publication_date)}</span>
                  <Chip>{a.category?.replaceAll('_', ' ')}</Chip>
                  <Chip>relevance: {a.relevance}</Chip>
                </div>
                {a.summary && a.summary !== a.headline && (
                  <p className="mt-1.5 text-sm text-ink-secondary">
                    <span className="mr-1 text-xs text-ink-muted">AI summary:</span>
                    {a.summary}
                  </p>
                )}
              </li>
            )
          })}
        </ul>
      )}
      <p className="mt-4 text-xs text-ink-muted">{news.disclaimer}</p>
    </Card>
  )
}
