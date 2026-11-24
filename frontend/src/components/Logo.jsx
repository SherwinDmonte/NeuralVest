// The wordmark: product name in the interface family plus the flat mark (same as the favicon).
import { Link } from 'react-router-dom'

export function Mark({ size = 24 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#272727" />
      <path d="M7 21.5 12.5 15l4.5 4 8-9" stroke="#EDEDED" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="25" cy="10" r="2.5" fill="#3987E5" />
    </svg>
  )
}

export function Logo({ to = '/' }) {
  return (
    <Link to={to} className="inline-flex items-center gap-2 rounded-lg text-ink">
      <Mark />
      <span className="title-3">NeuralVest</span>
    </Link>
  )
}
