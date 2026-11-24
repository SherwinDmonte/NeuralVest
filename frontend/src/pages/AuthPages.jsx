// Register and log in (task 12.2.1). Client side checks mirror the API rules; the API still
// validates everything and its message is shown if it disagrees.
import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Button, ErrorState, Field, Input } from '../components/ui'
import { Logo } from '../components/Logo'
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

function AuthFrame({ title, subtitle, children, footer }) {
  return (
    <div className="flex min-h-screen flex-col px-4 py-8">
      <Logo />
      <main id="main" className="flex flex-1 items-center justify-center py-12">
        <div className="w-full max-w-sm">
          <h1 className="heading-5 text-ink">{title}</h1>
          <p className="mt-2 body-6 text-ink-secondary">{subtitle}</p>
          <div className="mt-8">{children}</div>
          <p className="mt-6 caption-2 text-ink-secondary">{footer}</p>
        </div>
      </main>
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
      <Button type="submit" className="w-full" disabled={busy}>
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
