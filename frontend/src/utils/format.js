// Number and date formatting (Indian locale). Kept out of component files so React's
// fast refresh keeps working.
export const num = (v, digits = 2) =>
  v == null ? '—' : Number(v).toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export const inr = (v, digits = 2) => (v == null ? '—' : `₹${num(v, digits)}`)

export const pct = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${num(v)}%`)

export const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'
