// Routes (task 12.2.3). Public: landing, login, register, privacy, terms. Everything under /app
// needs a login (RequireAuth sends visitors to /login and back afterwards).
import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { RequireAuth } from './auth/AuthContext'
import { AnalysisProvider } from './analysis/AnalysisContext'
import { WatchlistProvider } from './hooks/useWatchlist'
import { PageSkeleton } from './components/ui'
import { LoginPage, RegisterPage } from './pages/AuthPages'
import LandingPage from './pages/LandingPage'
import { NotFoundPage, PrivacyPage, TermsPage } from './pages/SitePages'

// The signed-in app (charts, Recharts) loads only after login, so the landing page stays light.
const AppShell = lazy(() => import('./layouts/AppShell'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const StockAnalysisPage = lazy(() => import('./pages/StockAnalysisPage'))
const AgentsPage = lazy(() => import('./pages/AgentsPage'))
const NewsPage = lazy(() => import('./pages/NewsPage'))
const PortfolioPage = lazy(() => import('./pages/PortfolioPage'))
const RiskPage = lazy(() => import('./pages/RiskPage'))
const ReportsPage = lazy(() => import('./pages/ReportsPage').then((m) => ({ default: m.ReportsPage })))
const ReportViewPage = lazy(() => import('./pages/ReportsPage').then((m) => ({ default: m.ReportViewPage })))
const ReportComparePage = lazy(() => import('./pages/ReportsPage').then((m) => ({ default: m.ReportComparePage })))

function Protected() {
  return (
    <RequireAuth>
      <WatchlistProvider>
        <AnalysisProvider>
          <Suspense fallback={<PageSkeleton />}>
            <AppShell />
          </Suspense>
        </AnalysisProvider>
      </WatchlistProvider>
    </RequireAuth>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/app" element={<Protected />}>
        <Route index element={<DashboardPage />} />
        <Route path="analysis" element={<StockAnalysisPage />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="news" element={<NewsPage />} />
        <Route path="portfolio" element={<PortfolioPage />} />
        <Route path="risk" element={<RiskPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="reports/compare" element={<ReportComparePage />} />
        <Route path="reports/:reportId" element={<ReportViewPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
