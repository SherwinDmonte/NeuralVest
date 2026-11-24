// Scroll reveals with IntersectionObserver (never a scroll listener). Each element is revealed
// once and stays visible. Reduced motion is handled in CSS (opacity only).
import { useEffect, useRef } from 'react'

export function useReveal() {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return undefined
    if (!('IntersectionObserver' in window)) {
      el.classList.add('is-visible')
      return undefined
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add('is-visible')
          io.disconnect()
        }
      },
      { rootMargin: '0px 0px -10% 0px', threshold: 0.1 },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return ref
}

// Tagline reveal (B11): each word switches on as it crosses a trigger line 40% above the
// bottom of the viewport, in reading order.
export function useWordReveal() {
  const ref = useRef(null)
  useEffect(() => {
    const root = ref.current
    if (!root) return undefined
    const words = [...root.querySelectorAll('.tagline-word')]
    if (!('IntersectionObserver' in window)) {
      words.forEach((w) => w.classList.add('is-on'))
      return undefined
    }
    const io = new IntersectionObserver(
      (entries) => {
        // Words on one line cross the line together: step them 70ms apart in reading order.
        entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => words.indexOf(a.target) - words.indexOf(b.target))
          .forEach((e, i) => {
            e.target.style.transitionDelay = `${i * 70}ms`
            e.target.classList.add('is-on')
            io.unobserve(e.target)
          })
      },
      { rootMargin: '0px 0px -40% 0px', threshold: 1 },
    )
    words.forEach((w) => io.observe(w))
    return () => io.disconnect()
  }, [])
  return ref
}
