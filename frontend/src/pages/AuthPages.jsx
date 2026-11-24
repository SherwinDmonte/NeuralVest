// Register and log in (task 12.2.1). Client side checks mirror the API rules; the API still
// validates everything and its message is shown if it disagrees.
import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Button, ErrorState, Field, Input } from '../components/ui'
import { Logo, Mark } from '../components/Logo'
import { Cpu, FileText, ShieldCheck } from '@phosphor-icons/react'
import { errorMessage } from '../services/api'
import { usePageTitle } from '../hooks/usePageTitle'

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const COMMON = ['password', 'password1', 'password123', '12345678', '123456789', '1234567890', 'qwerty123',
  'qwertyuiop', 'iloveyou', '11111111', 'abcdefgh', 'abc12345', 'letmein1', 'welcome1', 'admin123', 'neuralvest']

function validate(form, mode) {
  const e = {}
  if (mode === 'register' && !form.name.trim()) e.name = 'Enter your name'
  if (!form.email.trim()) e.email = 'Enter your email'
  else if (!EMAIL.test(form.email.trim())) e.email = 'Enter an email like asha@example.com'
  if (!form.password) e.password = 'Enter your password'
  else if (mode === 'register') {
    if (form.password.length < 8) e.password = 'Use at least 8 characters'
    else if (form.password.length > 128) e.password = 'Use at most 128 characters'
    else if (COMMON.includes(form.password.toLowerCase()) || new Set(form.password).size === 1) e.password = 'This password is too easy to guess. Choose another'
    else if ([form.email.toLowerCase(), form.email.split('@')[0].toLowerCase()].includes(form.password.toLowerCase())) e.password = 'Do not use your email as the password'
  }
  return e
}

const POINTS = [
  [ShieldCheck, 'Every number traced', 'Each figure in a report is matched to the agent that computed it.'],
  [Cpu, 'Runs on your computer', 'A local Qwen3 model through Ollama. No paid API.'],
  [FileText, 'Reports you keep', 'Private to your account, comparable, and downloadable as PDF.'],
]

function AuthFrame({ title, subtitle, children, footer }) {
  return (
    <div className="grid min-h-screen ambient lg:grid-cols-[1.1fr_1fr]">
      <aside className="relative hidden overflow-hidden border-r border-line p-12 lg:flex lg:flex-col">
        <div className="pointer-events-none absolute inset-0 grid-lines opacity-70 [mask-image:radial-gradient(ellipse_at_top_left,black,transparent_75%)]" aria-hidden="true" />
        <div className="pointer-events-none absolute -left-24 top-1/3 h-96 w-96 rounded-full bg-accent/25 blur-3xl" aria-hidden="true" />
        <div className="pointer-events-none absolute bottom-0 right-0 h-80 w-80 rounded-full bg-violet/20 blur-3xl" aria-hidden="true" />
        <div className="relative"><Logo /></div>
        <div className="relative mt-auto max-w-lg">
          <Mark size={64} animated />
          <h2 className="mt-8 heading-4 text-ink">Research Indian stocks <span className="text-brand">with the working shown</span></h2>
          <ul className="mt-8 space-y-4">
            {POINTS.map(([Icon, t, d]) => (
              <li key={t} className="flex gap-4 rounded-2xl border border-line glass p-4">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-button text-white"><Icon size={20} aria-hidden="true" /></span>
                <span><span className="block body-5 text-ink">{t}</span><span className="caption-2 text-ink-secondary">{d}</span></span>
              </li>
            ))}
          </ul>
          <p className="mt-8 caption-5 text-ink-muted">Educational project. Not investment advice.</p>
        </div>
      </aside>
      <div className="flex min-h-screen flex-col px-4 py-8 sm:px-8">
        <div className="lg:hidden"><Logo /></div>
        <main id="main" className="flex flex-1 items-center justify-center py-12">
          <div className="relative w-full max-w-md rounded-3xl border border-line glass p-6 shadow-float sm:p-8">
            <span className="pointer-events-none absolute inset-x-8 top-0 h-px bg-brand" aria-hidden="true" />
            <h1 className="heading-5 text-ink">{title}</h1>
            <p className="mt-2 body-6 text-ink-secondary">{subtitle}</p>
            <div className="mt-8">{children}</div>
            <p className="mt-6 caption-2 text-ink-secondary">{footer}</p>
          </div>
        </main>
      </div>
    </div>
  )
}

function AuthForm({ mode }) {
  const { user, login, register, notice } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState(null)
  const [busy, setBusy] = useState(false)
  const next = location.state?.from || '/app'

  if (user) return <Navigate to={next} replace />

  const set = (k) => (e) => {
    setForm((f) => ({ ...f, [k]: e.target.value }))
    if (errors[k]) setErrors((x) => ({ ...x, [k]: undefined }))
  }

  const submit = async (e) => {
    e.preventDefault()
    const found = validate(form, mode)
    setErrors(found)
    setServerError(null)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      if (mode === 'register') await register(form.name.trim(), form.email.trim(), form.password)
      else await login(form.email.trim(), form.password)
      navigate(next, { replace: true })
    } catch (err) {
      setServerError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      {notice && mode === 'login' && !serverError && <p className="rounded-lg border border-line bg-surface p-3 caption-2 text-ink-secondary">{notice}</p>}
      {serverError && <ErrorState message={serverError} />}
      {mode === 'register' && (
        <Field label="Name" error={errors.name}>
          {(p) => <Input {...p} value={form.name} onChange={set('name')} autoComplete="name" maxLength={80} />}
        </Field>
      )}
      <Field label="Email" error={errors.email}>
        {(p) => <Input {...p} type="email" value={form.email} onChange={set('email')} autoComplete="email" />}
      </Field>
      <Field label="Password" error={errors.password} hint={mode === 'register' ? '8 to 128 characters. A short phrase is easier to remember.' : undefined}>
        {(p) => (
          <Input {...p} type="password" value={form.password} onChange={set('password')}
                 autoComplete={mode === 'register' ? 'new-password' : 'current-password'} maxLength={128} />
        )}
      </Field>
      <Button type="submit" size="lg" className="w-full" disabled={busy}>
        {busy ? (mode === 'register' ? 'Creating your account' : 'Logging in') : mode === 'register' ? 'Create a free account' : 'Log in'}
      </Button>
    </form>
  )
}

export function LoginPage() {
  usePageTitle('Log in')
  return (
    <AuthFrame title="Log in" subtitle="Your reports and watchlist are private to your account."
               footer={<>No account yet? <Link to="/register" className="text-accent-ink underline-offset-4 hover:underline">Create a free account</Link></>}>
      <AuthForm mode="login" />
    </AuthFrame>
  )
}

export function RegisterPage() {
  usePageTitle('Create an account')
  return (
    <AuthFrame title="Create a free account" subtitle="Accounts live in your own MongoDB database. Passwords are stored only as Argon2 hashes."
               footer={<>Already registered? <Link to="/login" className="text-accent-ink underline-offset-4 hover:underline">Log in</Link></>}>
      <AuthForm mode="register" />
    </AuthFrame>
  )
}
