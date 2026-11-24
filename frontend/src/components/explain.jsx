// The two kinds of text on every result card: readings computed by NeuralVest's rules
// (always correct) and the AI explanation (checked, but its wording can be wrong).
import { Calculator, Robot } from '@phosphor-icons/react'
import { sentence } from './ui'

export function Readings({ items, title = 'Key readings, computed by NeuralVest rules' }) {
  const list = (items || []).filter(Boolean)
  if (!list.length) return null
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 caption-4 text-ink-muted">
        <Calculator size={16} aria-hidden="true" />
        {title}
      </div>
      <ul className="list-disc space-y-1 pl-5 body-6 text-ink">
        {list.map((r) => <li key={r}>{sentence(r)}</li>)}
      </ul>
    </div>
  )
}

export function AiNote({ llm, text, note }) {
  if (!text) return null
  const fromLlm = llm?.source === 'llm'
  return (
    <div className="rounded-xl border border-line bg-raised/50 p-4">
      <div className="mb-2 flex items-center gap-2 caption-4 text-ink-muted">
        <Robot size={16} aria-hidden="true" />
        {fromLlm ? `AI explanation by the local ${llm.model} model` : 'Explanation written without the AI model'}
      </div>
      <p className="body-6 text-ink-secondary">{text}</p>
      {fromLlm && (
        <p className="mt-2 caption-5 text-ink-muted">
          {note || 'Numbers in this text are checked against the calculations. If the wording disagrees with the key readings, the readings are correct.'}
        </p>
      )}
    </div>
  )
}
