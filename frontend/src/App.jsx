import { Link, Route, Routes } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import DashboardPage from './pages/DashboardPage'
import { EmptyState } from './components/ui'

function NotFound() {
  return (
    <EmptyState>
      Page not found. <Link to="/" className="text-accent underline">Back to the dashboard</Link>
    </EmptyState>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
