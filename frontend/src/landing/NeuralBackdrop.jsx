// The landing page's background graphic: a quiet network of nodes and links, drawn in code so
// it is sharp at any size and follows the theme. Positions come from a seeded generator, so the
// picture is the same on every visit. Decorative only (aria-hidden).

function seeded(seed) {
  let s = seed
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296
    return s / 4294967296
  }
}

function build(count, w, h, seed, reach) {
  const rnd = seeded(seed)
  const nodes = Array.from({ length: count }, (_, i) => ({
    x: Math.round(rnd() * w), y: Math.round(rnd() * h), r: rnd() < 0.18 ? 2.6 : 1.6, accent: rnd() < 0.14, delay: (i % 9) * 0.7,
  }))
  const links = []
  nodes.forEach((a, i) => {
    nodes.slice(i + 1).forEach((b) => {
      const d = Math.hypot(a.x - b.x, a.y - b.y)
      if (d < reach) links.push({ a, b, o: 1 - d / reach })
    })
  })
  return { nodes, links }
}

const LAYOUTS = {
  hero: build(46, 1440, 760, 7, 190),
  cta: build(26, 1200, 420, 19, 170),
}

export default function NeuralBackdrop({ variant = 'hero', className = '' }) {
  const { nodes, links } = LAYOUTS[variant]
  const [w, h] = variant === 'hero' ? [1440, 760] : [1200, 420]
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid slice" aria-hidden="true"
         className={`pointer-events-none absolute inset-0 h-full w-full ${className}`}>
      <g className="lp-drift">
        {links.map(({ a, b, o }, i) => (
          <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="var(--nv-ink)" strokeOpacity={(0.1 * o).toFixed(3)} strokeWidth="1" />
        ))}
        {nodes.map((n, i) => (
          <circle key={i} className="lp-node" cx={n.x} cy={n.y} r={n.r} style={{ animationDelay: `${n.delay}s` }}
                  fill={n.accent ? 'var(--nv-accent)' : 'var(--nv-ink-muted)'} />
        ))}
      </g>
    </svg>
  )
}
