import React from 'react'
import { createPortal } from 'react-dom'
import './BoomOverlay.css'

const VARIANTS = {
  exploding: {
    eyebrow: 'EXPLODING KITTEN',
    subtitle: 'EXPLODING KITTEN · BỊ LOẠI KHỎI VÁN ĐẤU',
    palette: ['#fff6d1', '#ffae2b', '#ff4b1f', '#b31217'],
  },
  imploding: {
    eyebrow: 'COSMIC SINGULARITY · IMPLODING KITTEN',
    subtitle: 'IMPLODING KITTEN · KHÔNG THỂ DEFUSE!',
    palette: ['#e0fbff', '#56e6ff', '#a855f7', '#ec4899'],
  },
  devilcat: {
    eyebrow: 'UNDERWORLD ABYSS · DEVILCAT',
    subtitle: 'DEVILCAT · NGỌN LỬA ĐỊA NGỤC!',
    palette: ['#fff1d0', '#ff6a1a', '#e5192a', '#59000c'],
  },
}

// 18 deterministic radial particles (precomputed once at module load — zero Math.random() in render)
function buildParticles() {
  let seed = 0x51a7f3c9
  const next = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
    return seed / 4294967296
  }

  const list = []
  const specs = [
    { kind: 'spark', count: 10 },
    { kind: 'ember', count: 5 },
    { kind: 'smoke', count: 3 },
  ]

  let id = 0
  for (const { kind, count } of specs) {
    for (let i = 0; i < count; i += 1) {
      const baseAngle = (i / count) * Math.PI * 2
      const jitter = (next() - 0.5) * ((Math.PI * 2) / count) * 0.6
      const theta = baseAngle + jitter + (kind === 'ember' ? 0.25 : kind === 'smoke' ? 0.55 : 0)
      const deg = (theta * 180) / Math.PI

      let dist
      let size
      let delay
      let dur
      let colorIdx

      if (kind === 'spark') {
        dist = 32 + next() * 24
        size = 20 + next() * 18
        delay = 0.03 + next() * 0.1
        dur = 0.72 + next() * 0.38
        colorIdx = next() < 0.48 ? 0 : 1
      } else if (kind === 'ember') {
        dist = 20 + next() * 24
        size = 7 + next() * 8
        delay = 0.06 + next() * 0.14
        dur = 1.05 + next() * 0.45
        colorIdx = next() < 0.55 ? 1 : 2
      } else {
        dist = 14 + next() * 12
        size = 36 + next() * 24
        delay = 0.12 + next() * 0.14
        dur = 1.35 + next() * 0.42
        colorIdx = next() < 0.5 ? 2 : 3
      }

      const tx = Math.cos(theta) * dist
      const ty = Math.sin(theta) * dist

      list.push({
        id: id++,
        kind,
        tx: `${tx.toFixed(2)}vmin`,
        ty: `${ty.toFixed(2)}vmin`,
        rot: `${deg.toFixed(1)}deg`,
        size: `${size.toFixed(1)}px`,
        delay: `${delay.toFixed(3)}s`,
        dur: `${dur.toFixed(3)}s`,
        colorIdx,
      })
    }
  }
  return list
}

// 20 deterministic cosmic background stars for Imploding Kitten
function buildCosmicStars() {
  let seed = 0x9b2c4e17
  const next = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
    return seed / 4294967296
  }

  const stars = []
  for (let i = 0; i < 20; i += 1) {
    const x = 4 + next() * 92
    const y = 4 + next() * 92
    const size = 2 + next() * 2.5
    const opacity = 0.5 + next() * 0.5
    stars.push({
      id: i,
      x: `${x.toFixed(2)}%`,
      y: `${y.toFixed(2)}%`,
      size: `${size.toFixed(1)}px`,
      opacity: opacity.toFixed(2),
    })
  }
  return stars
}

// 20 deterministic inward-spiraling matter streaks/orbs sucked into the black hole
function buildBlackHoleMatter() {
  let seed = 0x3d8a19f5
  const next = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
    return seed / 4294967296
  }

  const matter = []
  const palette = ['#56e6ff', '#a855f7', '#ec4899']
  for (let i = 0; i < 20; i += 1) {
    const kind = i % 3 === 0 ? 'orb' : 'streak'
    const a0 = (i / 20) * 360 + (next() - 0.5) * 14
    const spin = 160 + next() * 150
    const r0 = 24 + next() * 32
    const size = kind === 'streak' ? 20 + next() * 20 : 6 + next() * 6
    const delay = next() * 0.45
    const dur = 1.15 + next() * 0.58
    const colorIdx = i % 3

    matter.push({
      id: i,
      kind,
      a0: `${a0.toFixed(1)}deg`,
      spin: `${spin.toFixed(1)}deg`,
      r0: `${r0.toFixed(2)}vmin`,
      size: `${size.toFixed(1)}px`,
      delay: `${delay.toFixed(3)}s`,
      dur: `${dur.toFixed(3)}s`,
      color: palette[colorIdx],
    })
  }
  return matter
}

// 5 surging underworld flame plumes rising from bottom
function buildHellFlames() {
  return [
    { id: 0, left: '12%', width: '30vw', height: '62vh', delay: '0.03s', dur: '1.95s', hue: 'crimson' },
    { id: 1, left: '30%', width: '32vw', height: '74vh', delay: '0.00s', dur: '2.05s', hue: 'gold' },
    { id: 2, left: '50%', width: '36vw', height: '84vh', delay: '0.02s', dur: '2.10s', hue: 'core' },
    { id: 3, left: '70%', width: '32vw', height: '74vh', delay: '0.05s', dur: '1.95s', hue: 'gold' },
    { id: 4, left: '88%', width: '30vw', height: '60vh', delay: '0.06s', dur: '1.85s', hue: 'crimson' },
  ]
}

// 20 deterministic rising brimstone sparks, glowing embers, and dark hell ash
function buildHellEmbers() {
  let seed = 0x666d3a1b
  const next = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
    return seed / 4294967296
  }

  const embers = []
  const palette = ['#fff1d0', '#ff8c24', '#ff293b', '#3a0a10']
  for (let i = 0; i < 20; i += 1) {
    const kind = i % 5 === 0 ? 'ash' : i % 2 === 0 ? 'spark' : 'ember'
    const left = 4 + next() * 92
    const drift = (next() - 0.5) * 24
    const size = kind === 'spark'
      ? 16 + next() * 16
      : kind === 'ember'
        ? 6 + next() * 8
        : 11 + next() * 12
    const delay = next() * 0.5
    const dur = 1.2 + next() * 0.8
    const color = kind === 'ash'
      ? palette[3]
      : palette[Math.floor(next() * 3)]

    embers.push({
      id: i,
      kind,
      left: `${left.toFixed(2)}%`,
      drift: `${drift.toFixed(2)}vw`,
      size: `${size.toFixed(1)}px`,
      delay: `${delay.toFixed(3)}s`,
      dur: `${dur.toFixed(3)}s`,
      color,
    })
  }
  return embers
}

const PARTICLES = buildParticles()
const COSMIC_STARS = buildCosmicStars()
const BLACKHOLE_MATTER = buildBlackHoleMatter()
const HELL_FLAMES = buildHellFlames()
const HELL_EMBERS = buildHellEmbers()

function HellSealSvg() {
  return (
    <svg className="dv-seal-svg" viewBox="0 0 240 240" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="dvSealGrad" x1="0" y1="0" x2="240" y2="240" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#fff1d0" />
          <stop offset="42%" stopColor="#ff6a1a" />
          <stop offset="100%" stopColor="#e5192a" />
        </linearGradient>
      </defs>
      <circle cx="120" cy="120" r="110" stroke="url(#dvSealGrad)" strokeWidth="2.4" opacity="0.9" />
      <circle
        cx="120"
        cy="120"
        r="100"
        stroke="#ff9e3d"
        strokeWidth="2"
        strokeDasharray="6 7"
        opacity="0.78"
      />
      <circle cx="120" cy="120" r="84" stroke="url(#dvSealGrad)" strokeWidth="1.8" opacity="0.82" />
      <polygon
        points="120,36 192.7,162 47.3,162"
        stroke="url(#dvSealGrad)"
        strokeWidth="2.2"
        strokeLinejoin="round"
        opacity="0.88"
      />
      <polygon
        points="120,204 47.3,78 192.7,78"
        stroke="url(#dvSealGrad)"
        strokeWidth="2.2"
        strokeLinejoin="round"
        opacity="0.88"
      />
      <circle cx="120" cy="120" r="42" stroke="#fff1d0" strokeWidth="1.6" opacity="0.75" />
      <path
        d="M92 104c-8-14-6-30 6-40-2 12 4 22 14 26 5-10 8-22 8-30 9 10 14 20 12 31 10-4 16-14 14-26 12 10 14 26 6 40 10 9 14 23 10 36-5 15-21 25-42 25s-37-10-42-25c-4-13 0-27 14-37Z"
        stroke="url(#dvSealGrad)"
        strokeWidth="2.4"
        fill="rgba(229, 25, 42, 0.2)"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function VariantIcon({ variant }) {
  if (variant === 'imploding') {
    return (
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
        <ellipse
          cx="12"
          cy="12"
          rx="10"
          ry="3.6"
          transform="rotate(-22 12 12)"
          stroke="currentColor"
          strokeWidth="1.9"
          opacity="0.92"
        />
        <circle cx="12" cy="12" r="4.3" fill="#05020b" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    )
  }
  if (variant === 'devilcat') {
    return (
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
        <path
          d="M5.4 3.2c-.8 3.2.4 5.7 2.5 7.4C6.5 12.1 5.6 14 5.6 16c0 3.3 2.8 5.8 6.4 5.8s6.4-2.5 6.4-5.8c0-2-.9-3.9-2.3-5.4 2.1-1.7 3.3-4.2 2.5-7.4-1.5 2-3.1 3.3-4.6 3.7-.6-1.4-1.3-2.9-2-4.1-.7 1.2-1.4 2.7-2 4.1-1.5-.4-3.1-1.7-4.6-3.7Z"
          fill="currentColor"
        />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
      <path
        d="M12 1.8 14.4 7.6 20.6 5.4 17.3 11l5.2 3.2-6.1 1.3 1.2 6.1-5.6-3.1-5.6 3.1 1.2-6.1-6.1-1.3L6.7 11 3.4 5.4l6.2 2.2L12 1.8Z"
        fill="currentColor"
      />
    </svg>
  )
}

function BoomOverlay({ boom }) {
  if (!boom || typeof document === 'undefined') return null

  const normalized = typeof boom === 'string'
    ? { who: boom, variant: 'exploding' }
    : boom

  const variant = VARIANTS[normalized.variant] ? normalized.variant : 'exploding'
  const meta = VARIANTS[variant]
  const who = typeof normalized.who === 'string' ? normalized.who.trim() : ''
  const overlayKey = normalized.key || normalized.who || 'boom'

  if (variant === 'imploding') {
    return createPortal(
      <div
        key={overlayKey}
        className="boom-overlay boom-cinema boom-imploding bh-cinema"
        role="alert"
        aria-live="assertive"
      >
        <div className="bh-backdrop" aria-hidden="true" />

        <div className="bh-starfield" aria-hidden="true">
          {COSMIC_STARS.map((s) => (
            <span
              key={s.id}
              className="bh-star"
              style={{
                left: s.x,
                top: s.y,
                width: s.size,
                height: s.size,
                opacity: s.opacity,
              }}
            />
          ))}
        </div>

        <div className="bh-gravity-ring g1" aria-hidden="true" />
        <div className="bh-gravity-ring g2" aria-hidden="true" />

        <div className="bh-orbits" aria-hidden="true">
          {BLACKHOLE_MATTER.map((m) => (
            <div
              key={m.id}
              className="bh-orbit-arm"
              style={{
                '--a0': m.a0,
                '--spin': m.spin,
                '--delay': m.delay,
                '--dur': m.dur,
              }}
            >
              <span
                className={`bh-matter bh-m-${m.kind}`}
                style={{
                  '--r0': m.r0,
                  '--size': m.size,
                  '--mcol': m.color,
                  '--delay': m.delay,
                  '--dur': m.dur,
                }}
              />
            </div>
          ))}
        </div>

        <div className="bh-vortex-stage" aria-hidden="true">
          <div className="bh-lens-halo" />
          <div className="bh-accretion-back">
            <div className="bh-accretion-disc" />
          </div>
          <div className="bh-singularity" />
          <div className="bh-accretion-front">
            <div className="bh-accretion-disc" />
          </div>
        </div>

        <div className="bh-collapse-flash" aria-hidden="true" />

        <div className="bh-banner">
          <div className="boom-eyebrow">
            <span className="boom-eyebrow-icon" aria-hidden="true">
              <VariantIcon variant="imploding" />
            </span>
            <span>{meta.eyebrow}</span>
          </div>
          <div className="boom-title bh-title">IMPLODED!</div>
          <div className="boom-victim bh-victim">
            {who ? `${who.toUpperCase()} BỊ HỐ ĐEN NUỐT CHỬNG!` : 'BỊ HỐ ĐEN NUỐT CHỬNG!'}
          </div>
          <div className="boom-subtitle">{meta.subtitle}</div>
        </div>
      </div>,
      document.body,
    )
  }

  if (variant === 'devilcat') {
    return createPortal(
      <div
        key={overlayKey}
        className="boom-overlay boom-cinema boom-devilcat dv-cinema"
        role="alert"
        aria-live="assertive"
      >
        <div className="dv-backdrop" aria-hidden="true" />

        <div className="dv-flames" aria-hidden="true">
          {HELL_FLAMES.map((f) => (
            <span
              key={f.id}
              className={`dv-flame dv-f-${f.hue}`}
              style={{
                left: f.left,
                '--fw': f.width,
                '--fh': f.height,
                '--delay': f.delay,
                '--dur': f.dur,
              }}
            />
          ))}
        </div>

        <div className="dv-seal-wrap" aria-hidden="true">
          <HellSealSvg />
        </div>

        <div className="dv-shock s1" aria-hidden="true" />
        <div className="dv-shock s2" aria-hidden="true" />

        <div className="dv-embers" aria-hidden="true">
          {HELL_EMBERS.map((e) => (
            <span
              key={e.id}
              className={`dv-ember dv-e-${e.kind}`}
              style={{
                left: e.left,
                '--drift': e.drift,
                '--size': e.size,
                '--delay': e.delay,
                '--dur': e.dur,
                '--ecol': e.color,
              }}
            />
          ))}
        </div>

        <div className="dv-flash" aria-hidden="true" />

        <div className="dv-banner">
          <div className="boom-eyebrow">
            <span className="boom-eyebrow-icon" aria-hidden="true">
              <VariantIcon variant="devilcat" />
            </span>
            <span>{meta.eyebrow}</span>
          </div>
          <div className="boom-title dv-title">INFERNO!</div>
          <div className="boom-victim dv-victim">
            {who ? `${who.toUpperCase()} BỊ THIÊU RỤI DƯỚI ĐỊA NGỤC!` : 'BỊ THIÊU RỤI DƯỚI ĐỊA NGỤC!'}
          </div>
          <div className="boom-subtitle">{meta.subtitle}</div>
        </div>
      </div>,
      document.body,
    )
  }

  return createPortal(
    <div
      key={overlayKey}
      className={`boom-overlay boom-cinema boom-${variant}`}
      role="alert"
      aria-live="assertive"
    >
      <div className="boom-backdrop" aria-hidden="true" />
      <div className="boom-rays" aria-hidden="true" />
      <div className="boom-core" aria-hidden="true" />
      <div className="boom-wave w1" aria-hidden="true" />
      <div className="boom-wave w2" aria-hidden="true" />

      <div className="boom-particles" aria-hidden="true">
        {PARTICLES.map((p) => (
          <span
            key={p.id}
            className={`boom-particle boom-p-${p.kind}`}
            style={{
              '--tx': p.tx,
              '--ty': p.ty,
              '--rot': p.rot,
              '--size': p.size,
              '--delay': p.delay,
              '--dur': p.dur,
              '--pcol': meta.palette[p.colorIdx],
            }}
          />
        ))}
      </div>

      <div className="boom-flash" aria-hidden="true" />

      <div className="boom-banner">
        <div className="boom-eyebrow">
          <span className="boom-eyebrow-icon" aria-hidden="true">
            <VariantIcon variant={variant} />
          </span>
          <span>{meta.eyebrow}</span>
        </div>
        <div className="boom-title">BOOM!</div>
        <div className="boom-victim">
          {who ? `${who.toUpperCase()} NỔ TUNG!` : 'NỔ TUNG!'}
        </div>
        <div className="boom-subtitle">{meta.subtitle}</div>
      </div>
    </div>,
    document.body,
  )
}

export default React.memo(BoomOverlay)
