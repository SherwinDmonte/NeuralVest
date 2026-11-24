// Login state for the whole app (tasks 12.2.2 and 12.2.3). On start, a token found in
// sessionStorage is checked with GET /auth/me; an invalid or expired token is dropped.
// The profile picture (Phase 12B) is fetched with the token and shown through an object URL.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import * as api from '../services/api'
import { PageSkeleton } from '../components/ui'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(() => Boolean(api.tokenStore.get()))
  const [notice, setNotice] = useState(null) // why the user was sent to the login page

  const logout = useCallback((reason = null) => {
    api.tokenStore.set(null)
    setUser(null)
    setNotice(reason)
  }, [])

  useEffect(() => {
    api.setUnauthorizedHandler((code) =>
      logout(code === 'token_expired' ? 'Your session expired. Log in again to continue.' : 'Log in to continue.'),
    )
    if (!api.tokenStore.get()) return
    api
      .getMe()
      .then((r) => setUser(r.user))
      .catch(() => api.tokenStore.set(null))
      .finally(() => setChecking(false))
  }, [logout])

  const login = useCallback(async (email, password) => {
    const r = await api.login({ email, password })
    api.tokenStore.set(r.access_token)
    setUser(r.user)
    setNotice(null)
    return r.user
  }, [])

  const register = useCallback(
    async (name, email, password) => {
      await api.register({ name, email, password })
      return login(email, password)
    },
    [login],
  )

  // The picture is refetched only when avatar_version changes (an upload or a removal).
  const [avatar, setAvatarState] = useState({ key: null, url: null })
  const userId = user?.user_id
  const avatarVersion = user?.avatar_version
  const avatarKey = userId && avatarVersion ? `${userId}:${avatarVersion}` : null
  useEffect(() => {
    if (!avatarKey) return undefined
    let url = null
    let cancelled = false
    api.getAvatar()
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setAvatarState({ key: avatarKey, url })
      })
      .catch(() => {})
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [avatarKey])
  // Shown only while it belongs to the current user and picture version.
  const avatarUrl = avatar.key && avatar.key === avatarKey ? avatar.url : null

  const setAvatar = useCallback(async (blob) => {
    const r = await api.putAvatar(blob)
    setUser(r.user)
    return r.user
  }, [])
  const removeAvatar = useCallback(async () => {
    const r = await api.deleteAvatar()
    setUser(r.user)
    return r.user
  }, [])

  const value = useMemo(
    () => ({ user, checking, notice, login, register, logout: () => logout(null), avatarUrl, setAvatar, removeAvatar }),
    [user, checking, notice, login, register, logout, avatarUrl, setAvatar, removeAvatar],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext)

// Protected routes: send visitors to /login and come back afterwards.
export function RequireAuth({ children }) {
  const { user, checking } = useAuth()
  const location = useLocation()
  if (checking) return <PageSkeleton />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return children
}
