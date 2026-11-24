// Everything the signed-in app needs, loaded lazily after login (so the landing page never
// downloads motion, Recharts or the app providers).
import { NotificationsProvider } from '../feedback/Notifications'
import { WatchlistProvider } from '../hooks/useWatchlist'
import { AnalysisProvider } from '../analysis/AnalysisContext'
import AppShell from './AppShell'

export default function AppRoot() {
  return (
    <NotificationsProvider>
      <WatchlistProvider>
        <AnalysisProvider>
          <AppShell />
        </AnalysisProvider>
      </WatchlistProvider>
    </NotificationsProvider>
  )
}
