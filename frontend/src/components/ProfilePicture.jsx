// Profile picture controls for the Settings page (Phase 12B). The browser crops the chosen image
// to a centred square and shrinks it to 512 px before uploading (phone photos are often over the
// 5 MB limit); the API then validates it again and stores a 256 px WebP without photo metadata.
import { useRef, useState } from 'react'
import { Camera, Trash, UploadSimple } from '@phosphor-icons/react'
import { useAuth } from '../auth/AuthContext'
import { useNotifications } from '../feedback/Notifications'
import { errorMessage } from '../services/api'
import Avatar from './Avatar'
import { Modal } from './motion'
import { Button } from './ui'

const ACCEPT = ['image/jpeg', 'image/png', 'image/webp']
const MAX_SOURCE_MB = 25
const OUTPUT = 512

async function squareImage(file) {
  const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
  const side = Math.min(bitmap.width, bitmap.height)
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = Math.min(OUTPUT, side)
  canvas.getContext('2d').drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, canvas.width, canvas.height)
  bitmap.close?.()
  // WebP where the browser can encode it; otherwise it falls back to PNG, which the API also accepts.
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/webp', 0.9))
  if (!blob || !ACCEPT.includes(blob.type)) throw new Error('This browser could not prepare the image.')
  return blob
}

export default function ProfilePicture() {
  const { user, avatarUrl, setAvatar, removeAvatar } = useAuth()
  const { notify } = useNotifications()
  const input = useRef(null)
  const [draft, setDraft] = useState(null) // { blob, url }
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)

  const discard = () => {
    if (draft) URL.revokeObjectURL(draft.url)
    setDraft(null)
  }

  const choose = async (file) => {
    setError(null)
    if (!file) return
    if (!ACCEPT.includes(file.type)) {
      setError('Choose a JPEG, PNG or WebP image. HEIC photos from iPhones need converting first.')
      return
    }
    if (file.size > MAX_SOURCE_MB * 1024 * 1024) {
      setError(`That file is over ${MAX_SOURCE_MB} MB. Choose a smaller image.`)
      return
    }
    try {
      const blob = await squareImage(file)
      discard()
      setDraft({ blob, url: URL.createObjectURL(blob) })
    } catch {
      setError('That file could not be read as an image.')
    }
  }

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      await setAvatar(draft.blob)
      discard()
      notify({ tone: 'good', title: 'Profile picture updated' })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    setBusy(true)
    setError(null)
    try {
      await removeAvatar()
      notify({ tone: 'info', title: 'Profile picture removed' })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files?.[0]) }}
      className={`flex flex-wrap items-center gap-4 rounded-2xl border border-dashed p-4 transition-colors duration-300 ease-nv ${dragging ? 'border-accent bg-accent/5' : 'border-line'}`}
    >
      <button type="button" onClick={() => input.current?.click()} aria-label="Choose a profile picture"
              className="group relative rounded-xl">
        <Avatar size={72} />
        <span className="absolute inset-0 grid place-items-center rounded-xl bg-black/45 text-white opacity-0 transition-opacity duration-300 ease-nv group-hover:opacity-100 group-focus-visible:opacity-100" aria-hidden="true">
          <Camera size={22} />
        </span>
      </button>
      <div className="min-w-0 flex-1">
        <p className="title-4 text-ink">Profile picture</p>
        <p className="caption-5 text-ink-muted">JPEG, PNG or WebP. Drop an image here or choose one. It is cropped to a square, and photo details such as location are removed.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => input.current?.click()} disabled={busy}>
            <UploadSimple size={16} aria-hidden="true" />{avatarUrl ? 'Change picture' : 'Upload a picture'}
          </Button>
          {user?.avatar_version && (
            <Button variant="ghost" size="sm" onClick={remove} disabled={busy}><Trash size={16} aria-hidden="true" />Remove</Button>
          )}
        </div>
        {error && !draft && <p role="alert" className="mt-2 caption-2 text-critical">{error}</p>}
      </div>
      <input ref={input} type="file" accept={ACCEPT.join(',')} className="sr-only" tabIndex={-1} aria-hidden="true"
             onChange={(e) => { choose(e.target.files?.[0]); e.target.value = '' }} />

      <Modal open={Boolean(draft)} onClose={() => { if (!busy) discard() }} title="New profile picture">
        {draft && (
          <div className="p-6">
            <div className="flex flex-col items-center gap-4 sm:flex-row">
              <img src={draft.url} alt="Preview of the new profile picture" className="h-40 w-40 rounded-2xl border border-line object-cover" />
              <div className="flex items-center gap-3 sm:flex-col sm:items-start">
                <img src={draft.url} alt="" className="h-10 w-10 rounded-xl object-cover" />
                <p className="caption-5 text-ink-muted">How it looks in the top bar</p>
              </div>
            </div>
            <p className="mt-4 caption-2 text-ink-secondary">Cropped to the centre of your image. Only you see it, in this app.</p>
            {error && <p role="alert" className="mt-2 caption-2 text-critical">{error}</p>}
            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={discard} disabled={busy}>Cancel</Button>
              <Button variant="secondary" size="sm" onClick={() => input.current?.click()} disabled={busy}>Choose another</Button>
              <Button size="sm" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save picture'}</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
