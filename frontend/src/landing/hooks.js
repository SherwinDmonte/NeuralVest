// Small interaction hooks for the landing page. No scroll work runs more than once per frame,
// and every effect is skipped when the visitor asks for reduced motion.
import { useEffect, useRef, useState } from 'react'

const reducedMotion = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const finePointer = () => typeof window !== 'undefined' && window.matchMedia?.('(hover: hover) and (pointer: fine)').matches

// Pointer parallax: sets --px and --py (-1..1) on the element; children use them with a depth.
export function usePointerParallax() {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el || reducedMotion() || !finePointer()) return undefined
    let frame = 0
    const onMove = (e) => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect()
        el.style.setProperty('--px', (((e.clientX - r.left) / r.width) * 2 - 1).toFixed(3))
        el.style.setProperty('--py', (((e.clientY - r.top) / r.height) * 2 - 1).toFixed(3))
      })
    }
    const onLeave = () => {
      cancelAnimationFrame(frame)
      el.style.setProperty('--px', '0')
      el.style.setProperty('--py', '0')
    }
    el.addEventListener('pointermove', onMove, { passive: true })
    el.addEventListener('pointerleave', onLeave)
    return () => {
      cancelAnimationFrame(frame)
      el.removeEventListener('pointermove', onMove)
      el.removeEventListener('pointerleave', onLeave)
    }
  }, [])
  return ref
}

// Reading progress: scales the element horizontally from 0 to 1 (one update per frame).
export function useScrollProgress() {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return undefined
    let frame = 0
    const update = () => {
      frame = 0
      const max = document.documentElement.scrollHeight - window.innerHeight
      el.style.transform = `scaleX(${max > 0 ? Math.min(1, window.scrollY / max) : 0})`
    }
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
    }
  }, [])
  return ref
}

// The step whose text crosses the middle of the viewport (IntersectionObserver, no scroll listener).
export function useActiveStep(count) {
  const [active, setActive] = useState(0)
  const nodes = useRef([])
  useEffect(() => {
    if (!('IntersectionObserver' in window)) return undefined
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) setActive(Number(e.target.dataset.step)) }),
      { rootMargin: '-45% 0px -45% 0px' },
    )
    nodes.current.slice(0, count).forEach((n) => n && io.observe(n))
    return () => io.disconnect()
  }, [count])
  const register = (i) => (n) => { nodes.current[i] = n }
  return [active, register, setActive]
}

// Marks the element visible one frame after it mounts, so its CSS entrance runs (used for tab panels).
export function useMountVisible() {
  const ref = useRef(null)
  useEffect(() => {
    const frame = requestAnimationFrame(() => ref.current?.classList.add('is-visible'))
    return () => cancelAnimationFrame(frame)
  }, [])
  return ref
}

// Cycles 0..count-1 every `ms` while `on` is true and motion is allowed.
export function useCycle(count, ms, on = true) {
  const [i, setI] = useState(0)
  useEffect(() => {
    if (!on || reducedMotion()) return undefined
    const t = setInterval(() => setI((v) => (v + 1) % count), ms)
    return () => clearInterval(t)
  }, [count, ms, on])
  return i
}
