// Axios client for the NeuralVest API. The base URL comes from frontend/.env
// (VITE_API_BASE_URL); the default matches the local FastAPI server.
//
// Token storage (task 12.2.2): the access token lives in sessionStorage. It survives a page
// reload but is cleared when the browser tab closes, and it is never written to a cookie, so
// there is no CSRF exposure. The interceptor adds "Authorization: Bearer <token>" to every
// request; a 401 clears the token and tells the app to show the login page.
import axios from 'axios'

const TOKEN_KEY = 'nv.token'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 30000,
})

export const tokenStore = {
  get() {
    try {
      return sessionStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token) {
    try {
      if (token) sessionStorage.setItem(TOKEN_KEY, token)
      else sessionStorage.removeItem(TOKEN_KEY)
    } catch {
      /* private mode: the session still works until reload */
    }
  },
}

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn
}

api.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const code = err?.response?.data?.error?.code
    const isLogin = err?.config?.url?.startsWith('/auth/login')
    if (err?.response?.status === 401 && !isLogin && ['not_authenticated', 'invalid_token', 'token_expired'].includes(code)) {
      tokenStore.set(null)
      onUnauthorized(code)
    }
    return Promise.reject(err)
  },
)

// Turn any failure into one readable message (the API always sends {error: {...}}).
export function errorMessage(err) {
  const apiError = err?.response?.data?.error
  if (apiError) {
    if (apiError.code === 'validation_error' && Array.isArray(apiError.details) && apiError.details[0]) {
      const d = apiError.details[0]
      const field = d.location?.[d.location.length - 1]
      const msg = d.message.replace(/^Value error, /, '')
      return typeof field === 'string' && !['body', 'query'].includes(field) ? `${field.replaceAll('_', ' ')}: ${msg}` : msg
    }
    return apiError.message
  }
  if (err?.code === 'ERR_NETWORK') return 'Cannot reach the NeuralVest API. Start the backend on port 8000 and try again.'
  if (err?.code === 'ECONNABORTED') return 'The request timed out. Try again.'
  return 'Something went wrong. Try again.'
}

const data = (r) => r.data

// ----- auth
export const register = (body) => api.post('/auth/register', body).then(data)
export const login = (body) => api.post('/auth/login', body).then(data)
export const getMe = () => api.get('/auth/me').then(data)
export const getWatchlist = () => api.get('/auth/me/watchlist').then(data)
export const putWatchlist = (symbols) => api.put('/auth/me/watchlist', { symbols }).then(data)

// ----- analysis
// `portfolio` (optional): { investmentAmount, riskPreference } for 2+ stocks -> Portfolio Optimization
export const startAnalysis = (symbols, includeGdelt = false, portfolio = null) =>
  api
    .post('/analysis/start', {
      symbols,
      include_gdelt: includeGdelt,
      ...(portfolio ? { investment_amount: portfolio.investmentAmount, risk_preference: portfolio.riskPreference } : {}),
    })
    .then(data)
export const getAnalysisStatus = (requestId) => api.get(`/analysis/${requestId}/status`).then(data)
export const getAnalysisResult = (requestId) => api.get(`/analysis/${requestId}`).then(data)
export const rerunAnalysis = (requestId) => api.post(`/analysis/${requestId}/rerun`).then(data)

// ----- stocks and news
const sym = (s) => encodeURIComponent(s)
export const getIndicators = (symbol, period = '1y') => api.get(`/stocks/${sym(symbol)}/indicators`, { params: { period } }).then(data)
export const searchStocks = (q, limit = 8) => api.get('/stocks/search', { params: { q, limit } }).then(data)
export const getNews = (symbol, params = {}) => api.get(`/news/${sym(symbol)}`, { params }).then(data)
export const getNewsSentiment = (symbol, days = 14) => api.get(`/news/${sym(symbol)}/sentiment`, { params: { days } }).then(data)

// ----- portfolio and risk (computed on request; several seconds)
export const optimizePortfolio = (body) => api.post('/portfolio/optimize', body, { timeout: 120000 }).then(data)
export const analyzeRisk = (body) => api.post('/risk/analyze', body, { timeout: 120000 }).then(data)

// ----- reports
export const listReports = (params = {}) => api.get('/reports', { params }).then(data)
export const getReport = (reportId) => api.get(`/reports/${reportId}`).then(data)

// The PDF is downloaded with the token (a plain link would not send it), then saved.
export async function downloadReportPdf(reportId) {
  let r
  try {
    r = await api.get(`/reports/${reportId}/pdf`, { responseType: 'blob', timeout: 60000 })
  } catch (err) {
    // With responseType "blob" an error body is a Blob too: read it so errorMessage() works.
    if (err?.response?.data instanceof Blob) {
      try {
        err.response.data = JSON.parse(await err.response.data.text())
      } catch {
        /* not JSON: keep the generic message */
      }
    }
    throw err
  }
  const match = /filename="([^"]+)"/.exec(r.headers['content-disposition'] || '')
  const url = URL.createObjectURL(r.data)
  const a = document.createElement('a')
  a.href = url
  a.download = match ? match[1] : `neuralvest_report_${reportId}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default api
