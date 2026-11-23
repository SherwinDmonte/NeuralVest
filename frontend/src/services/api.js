// Axios client for the NeuralVest API. The base URL comes from frontend/.env
// (VITE_API_BASE_URL); the default matches the local FastAPI server.
import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 30000,
})

// Turn any failure into one readable message (the API always sends {error: {...}}).
export function errorMessage(err) {
  const apiError = err?.response?.data?.error
  if (apiError) {
    if (apiError.code === 'validation_error' && Array.isArray(apiError.details) && apiError.details[0]) {
      return apiError.details[0].message.replace(/^Value error, /, '')
    }
    return apiError.message
  }
  if (err?.code === 'ERR_NETWORK') return 'Cannot reach the NeuralVest API. Is the backend running on port 8000?'
  if (err?.code === 'ECONNABORTED') return 'The request timed out. Please try again.'
  return 'Something went wrong. Please try again.'
}

// `portfolio` (optional): { investmentAmount, riskPreference } for 2+ stocks -> Portfolio Optimization
export const startAnalysis = (symbols, includeGdelt = false, portfolio = null) =>
  api
    .post('/analysis/start', {
      symbols,
      include_gdelt: includeGdelt,
      ...(portfolio ? { investment_amount: portfolio.investmentAmount, risk_preference: portfolio.riskPreference } : {}),
    })
    .then((r) => r.data)

export const getAnalysisStatus = (requestId) => api.get(`/analysis/${requestId}/status`).then((r) => r.data)

export const getAnalysisResult = (requestId) => api.get(`/analysis/${requestId}`).then((r) => r.data)

export const rerunAnalysis = (requestId) => api.post(`/analysis/${requestId}/rerun`).then((r) => r.data)

export const getIndicators = (symbol, period = '1y') =>
  api.get(`/stocks/${encodeURIComponent(symbol)}/indicators`, { params: { period } }).then((r) => r.data)

export default api
