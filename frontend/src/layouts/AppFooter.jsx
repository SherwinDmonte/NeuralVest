// Footer of the signed-in app (Phase 12B): one row with the notice and the legal links.
import { Link } from 'react-router-dom'

const linkCls = 'transition-colors duration-300 ease-nv hover:text-ink'

export default function AppFooter() {
  return (
    <footer className="mt-8 border-t border-line">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-3 px-4 py-6 caption-5 text-ink-muted sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <p>© {new Date().getFullYear()} NeuralVest · Educational project, not investment advice</p>
        <nav aria-label="Legal" className="flex gap-4">
          <Link to="/privacy" className={linkCls}>Privacy</Link>
          <Link to="/terms" className={linkCls}>Terms</Link>
        </nav>
      </div>
    </footer>
  )
}
