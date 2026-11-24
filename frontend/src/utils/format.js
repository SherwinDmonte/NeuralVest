// Number and date formatting (Indian locale). Kept out of component files so React's
// fast refresh keeps working.
export const num = (v, digits = 2) =>
  v == null ? 'n/a' : Number(v).toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export const inr = (v, digits = 2) => (v == null ? 'n/a' : `₹${num(v, digits)}`)

export const pct = (v) => (v == null ? 'n/a' : `${v > 0 ? '+' : ''}${num(v)}%`)

export const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'n/a'

// Only absolute http(s) links are rendered (the API validates them too, task 11.3.3).
export const safeUrl = (url) => (typeof url === 'string' && /^https?:\/\//i.test(url) ? url : null)

// Short symbol for compact labels: RELIANCE.NS -> RELIANCE
export const shortSymbol = (s) => (s || '').replace(/\.(NS|BO)$/, '')

export const fmtDateTime = (iso) =>
  iso ? new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'n/a'
