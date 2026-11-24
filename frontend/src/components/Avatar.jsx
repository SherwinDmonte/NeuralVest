// The signed-in user's picture, or their initials when no picture is set (Phase 12B).
import { useAuth } from '../auth/AuthContext'

const initialsOf = (name) => (name || '?').split(' ').filter(Boolean).map((p) => p[0]).slice(0, 2).join('').toUpperCase()

export default function Avatar({ size = 36, className = '', alt = '' }) {
  const { user, avatarUrl } = useAuth()
  const style = { width: size, height: size }
  if (avatarUrl) {
    return <img src={avatarUrl} alt={alt} width={size} height={size} style={style} className={`shrink-0 rounded-xl object-cover ${className}`} />
  }
  return (
    <span style={{ ...style, fontSize: Math.max(11, Math.round(size * 0.36)) }} aria-hidden={alt ? undefined : 'true'}
          className={`grid shrink-0 place-items-center rounded-xl bg-brand-button font-semibold text-white ${className}`}>
      {initialsOf(user?.name)}
    </span>
  )
}
