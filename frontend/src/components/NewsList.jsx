// News analysed by the Financial News Agent. The original headline (linked to the source) is
// always shown above the AI summary, so readers can check the model's wording.
import { ArrowSquareOut, Newspaper } from '@phosphor-icons/react'
import { Card, EmptyState, Meta, ToneBadge } from './ui'
import { AiNote } from './explain'
import { fmtDate, safeUrl, shortSymbol } from '../utils/format'

export function ArticleList({ articles }) {
  return (
    <ul className="divide-y divide-line">
      {articles.map((a) => {
        const href = safeUrl(a.article_url)
        return (
          <li key={a.url_hash} className="py-4 first:pt-0 last:pb-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              {href ? (
                <a href={href} target="_blank" rel="noopener noreferrer"
                   className="group inline-flex max-w-full items-start gap-1 rounded body-5 text-ink transition-colors duration-300 ease-nv hover:text-accent-ink">
                  <span>{a.headline}</span>
                  <ArrowSquareOut size={14} className="mt-1 shrink-0 text-ink-muted group-hover:text-accent-ink" aria-hidden="true" />
                  <span className="sr-only">(opens the original article in a new tab)</span>
                </a>
              ) : (
                <span className="body-5 text-ink">{a.headline}</span>
              )}
              <ToneBadge value={a.sentiment} />
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
              {a.symbol && <span className="rounded-md bg-accent/10 px-1.5 figure caption-5 text-accent-ink">{shortSymbol(a.symbol)}</span>}
              <Meta>{a.publisher}</Meta>
              <Meta>{fmtDate(a.publication_date)}</Meta>
              <Meta>{a.category?.replaceAll('_', ' ')}</Meta>
              <Meta>{a.relevance} relevance</Meta>
            </div>
            {a.summary && a.summary !== a.headline && (
              <p className="mt-2 body-6 text-ink-secondary">
                <span className="mr-1 caption-4 text-ink-muted">AI summary</span>
                {a.summary}
              </p>
            )}
          </li>
        )
      })}
    </ul>
  )
}

export default function NewsList({ news }) {
  if (!news) return null
  const articles = news.articles || []
  return (
    <Card
      title="Financial news"
      subtitle={`Last ${news.lookback_days} days · ${news.articles_analyzed} analysed of ${news.articles_collected} found`}
      actions={<ToneBadge value={news.overall_sentiment} label={`${(news.overall_sentiment || '').replaceAll('_', ' ')} sentiment`} />}
    >
      <div className="space-y-6">
        <AiNote llm={{ source: news.digest_source === 'llm' ? 'llm' : 'template', model: news.llm?.model || 'Qwen3' }} text={news.digest}
                note="The digest summarises the headlines below. Read the original articles before relying on it." />
        {articles.length === 0 ? (
          <EmptyState icon={Newspaper} title="No recent articles">
            None of the configured news sources mentioned this company in the last {news.lookback_days} days.
          </EmptyState>
        ) : (
          <ArticleList articles={articles} />
        )}
        <p className="caption-5 text-ink-muted">{news.disclaimer}</p>
      </div>
    </Card>
  )
}
