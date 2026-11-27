import React, { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import './EpicCardOverlay.css'

export const EPIC_CARD_TYPES = new Set([
  'armageddon',
  'towerofpower',
  'catomicbomb',
  'attackofthedead',
  'godcat',
  'devilcat',
])

export const EPIC_PRELOAD_IMAGES = [
  '/static/cards/armageddon/0.jpg',
  '/static/cards/towerofpower/0.jpg',
  '/static/cards/catomicbomb/0.jpg',
  '/static/cards/attackofthedead/0.jpg',
  '/static/cards/godcat/0.jpg',
  '/static/cards/devilcat/0.jpg',
  '/static/cards/barkingkitten/0.jpg',
]

export const EPIC_FX_PRESETS = [
  { id: 'armageddon', label: 'Armageddon', fx: { kind: 'card_fx', card_type: 'armageddon', actor: 'Alice' } },
  { id: 'towerofpower', label: 'Tower of Power', fx: { kind: 'card_fx', card_type: 'towerofpower', actor: 'Alice' } },
  { id: 'catomicbomb', label: 'Catomic Bomb', fx: { kind: 'card_fx', card_type: 'catomicbomb', actor: 'Alice' } },
  {
    id: 'attackofthedead',
    label: 'Attack of the Dead',
    fx: { kind: 'card_fx', card_type: 'attackofthedead', actor: 'Alice', target: 'Bob', count: 3 },
  },
  { id: 'godcat', label: 'Godcat', fx: { kind: 'card_fx', card_type: 'godcat', actor: 'Alice' } },
  { id: 'devilcat', label: 'Devilcat', fx: { kind: 'card_fx', card_type: 'devilcat', actor: 'Alice' } },
]

const EPIC_DURATIONS = {
  armageddon: 2400,
  catomicbomb: 2300,
  towerofpower: 2250,
  attackofthedead: 2250,
  godcat: 2150,
  devilcat: 2150,
}

export function getEpicDuration(cardType) {
  return EPIC_DURATIONS[cardType] || 2200
}

function makeRng(seedStart) {
  let seed = seedStart >>> 0
  return () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
    return seed / 4294967296
  }
}

// 20 deterministic gold/crimson sparks for Armageddon eclipse clash
function buildArmageddonSparks() {
  const next = makeRng(0x4a7f21d3)
  const goldPalette = ['#ffffff', '#ffe58f', '#ffbe3d']
  const crimsonPalette = ['#fff1d0', '#ff6a1a', '#ff2942']
  const list = []
  for (let i = 0; i < 20; i += 1) {
    const theta = (i / 20) * Math.PI * 2 + (next() - 0.5) * 0.24
    const dist = 26 + next() * 24
    const size = 18 + next() * 20
    const delay = 0.22 + next() * 0.24
    const dur = 0.72 + next() * 0.42
    const isGold = i % 2 === 0
    const col = isGold
      ? goldPalette[Math.floor(next() * goldPalette.length)]
      : crimsonPalette[Math.floor(next() * crimsonPalette.length)]
    list.push({
      id: i,
      tx: `${(Math.cos(theta) * dist).toFixed(2)}vmin`,
      ty: `${(Math.sin(theta) * dist).toFixed(2)}vmin`,
      rot: `${((theta * 180) / Math.PI).toFixed(1)}deg`,
      size: `${size.toFixed(1)}px`,
      delay: `${delay.toFixed(3)}s`,
      dur: `${dur.toFixed(3)}s`,
      color: col,
    })
  }
  return list
}

// 6 royal stash cards orbiting + 18 golden sparkles for Tower of Power
function buildTowerStashCards() {
  const cards = []
  for (let i = 0; i < 6; i += 1) {
    const angleDeg = i * 60 - 90
    const rad = (angleDeg * Math.PI) / 180
    const radius = 24
    cards.push({
      id: i,
      tx: `${(Math.cos(rad) * radius).toFixed(2)}vmin`,
      ty: `${(Math.sin(rad) * radius).toFixed(2)}vmin`,
      rot: `${(angleDeg + 90).toFixed(1)}deg`,
      delay: `${(0.14 + i * 0.045).toFixed(3)}s`,
    })
  }
  return cards
}

function buildTowerSparkles() {
  const next = makeRng(0x88c1e305)
  const colors = ['#ffffff', '#fff2b2', '#ffd147', '#34d399']
  const list = []
  for (let i = 0; i < 18; i += 1) {
    const theta = (i / 18) * Math.PI * 2 + (next() - 0.5) * 0.28
    const dist = 18 + next() * 26
    const size = 5 + next() * 7
    const delay = 0.1 + next() * 0.5
    const dur = 0.85 + next() * 0.55
    list.push({
      id: i,
      tx: `${(Math.cos(theta) * dist).toFixed(2)}vmin`,
      ty: `${(Math.sin(theta) * dist).toFixed(2)}vmin`,
      size: `${size.toFixed(1)}px`,
      delay: `${delay.toFixed(3)}s`,
      dur: `${dur.toFixed(3)}s`,
      color: colors[i % colors.length],
    })
  }
  return list
}

// 20 rising nuclear sparks & embers for Catomic Bomb
function buildCatomicEmbers() {
  const next = makeRng(0xc47091ab)
  const colors = ['#fff5cc', '#ffb703', '#ff5400', '#ff1e38']
  const list = []
  for (let i = 0; i < 20; i += 1) {
    const kind = i % 3 === 0 ? 'spark' : 'ember'
    const left = 10 + next() * 80
    const drift = (next() - 0.5) * 20
    const size = kind === 'spark' ? 16 + next() * 18 : 6 + next() * 8
    const delay = 0.08 + next() * 0.58
    const dur = 1.05 + next() * 0.65
    list.push({
      id: i,
      kind,
      left: `${left.toFixed(2)}%`,
      drift: `${drift.toFixed(2)}vw`,
      size: `${size.toFixed(1)}px`,
      delay: `${delay.toFixed(3)}s`,
      dur: `${dur.toFixed(3)}s`,
      color: colors[Math.floor(next() * colors.length)],
    })
  }
  return list
}

// 18 rising green soul wisps for Attack of the Dead
function buildDeadWisps() {
  const next = makeRng(0x2e9a4f11)
  const colors = ['#d9ffe7', '#6ee7b7', '#10b981', '#a3e635']
  const list = []
  for (let i = 0; i < 18; i += 1) {
    const left = 6 + next() * 88
    const drift = (next() - 0.5) * 18
    const size = 6 + next() * 9
    const delay = 0.08 + next() * 0.65
    const dur = 1.15 + next() * 0.7
    list.push({
      id: i,
      left: `${left.toFixed(2)}%`,
      drift: `${drift.toFixed(2)}vw`,
      size: `${size.toFixed(1)}px`,
      delay: `${delay.toFixed(3)}s`,
      dur: `${dur.toFixed(3)}s`,
      color: colors[Math.floor(next() * colors.length)],
    })
  }
  return list
}

// 18 radiant starlight motes for Godcat
function buildGodcatMotes() {
  const next = makeRng(0xf19d72b4)
  const colors = ['#ffffff', '#fff7cc', '#ffd859', '#93c5fd']
  const list = []
  for (let i = 0; i < 18; i += 1) {
    const theta = (i / 18) * Math.PI * 2 + (next() - 0.5) * 0.25
    const dist = 16 + next() * 28
    const size = 5 + next() * 7
    const delay = 0.08 + next() * 0.52
    const dur = 0.95 + next() * 0.55
    list.push({
      id: i,
      tx: `${(Math.cos(theta) * dist).toFixed(2)}vmin`,
      ty: `${(Math.sin(theta) * dist).toFixed(2)}vmin`,
      size: `${size.toFixed(1)}px`,
      delay: `${delay.toFixed(3)}s`,
      dur: `${dur.toFixed(3)}s`,
      color: colors[i % colors.length],
    })
  }
  return list
}

// 5 surging flame plumes + 18 rising embers for Devilcat
const DEVILCAT_FLAMES = [
  { id: 0, left: '14%', width: '28vw', height: '58vh', delay: '0.04s', dur: '1.85s', hue: 'crimson' },
  { id: 1, left: '32%', width: '30vw', height: '68vh', delay: '0.00s', dur: '1.95s', hue: 'gold' },
  { id: 2, left: '50%', width: '34vw', height: '76vh', delay: '0.02s', dur: '2.00s', hue: 'core' },
  { id: 3, left: '68%', width: '30vw', height: '68vh', delay: '0.05s', dur: '1.90s', hue: 'gold' },
  { id: 4, left: '86%', width: '28vw', height: '56vh', delay: '0.07s', dur: '1.80s', hue: 'crimson' },
]

function buildDevilcatEmbers() {
  const next = makeRng(0x6619d0a7)
  const colors = ['#fff1d0', '#ff8c24', '#ff293b']
  const list = []
  for (let i = 0; i < 18; i += 1) {
    const kind = i % 2 === 0 ? 'spark' : 'ember'
    const left = 6 + next() * 88
    const drift = (next() - 0.5) * 22
    const size = kind === 'spark' ? 14 + next() * 16 : 6 + next() * 8
    const delay = next() * 0.45
    const dur = 1.15 + next() * 0.7
    list.push({
      id: i,
      kind,
      left: `${left.toFixed(2)}%`,
      drift: `${drift.toFixed(2)}vw`,
      size: `${size.toFixed(1)}px`,
      delay: `${delay.toFixed(3)}s`,
      dur: `${dur.toFixed(3)}s`,
      color: colors[Math.floor(next() * colors.length)],
    })
  }
  return list
}

const ARMAGEDDON_SPARKS = buildArmageddonSparks()
const TOWER_STASH_CARDS = buildTowerStashCards()
const TOWER_SPARKLES = buildTowerSparkles()
const CATOMIC_EMBERS = buildCatomicEmbers()
const DEAD_WISPS = buildDeadWisps()
const GODCAT_MOTES = buildGodcatMotes()
const DEVILCAT_EMBERS = buildDevilcatEmbers()

function SafeImg({ src, fallback = null, alt = '', className = '', resetKey }) {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    setStage(0)
  }, [src, fallback, resetKey])

  const activeSrc = stage === 0 ? src : stage === 1 ? fallback : null
  if (!activeSrc) return null

  return (
    <img
      src={activeSrc}
      alt={alt}
      className={className}
      draggable={false}
      decoding="async"
      onError={() => {
        setStage((prev) => {
          if (prev === 0 && fallback && fallback !== src) return 1
          return 2
        })
      }}
    />
  )
}

function HellSealSvg() {
  return (
    <svg className="ep-dv-seal-svg" viewBox="0 0 240 240" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="epDvSealGrad" x1="0" y1="0" x2="240" y2="240" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#fff1d0" />
          <stop offset="45%" stopColor="#ff6a1a" />
          <stop offset="100%" stopColor="#e5192a" />
        </linearGradient>
      </defs>
      <circle cx="120" cy="120" r="110" stroke="url(#epDvSealGrad)" strokeWidth="2.4" opacity="0.9" />
      <circle
        cx="120"
        cy="120"
        r="100"
        stroke="#ff9e3d"
        strokeWidth="2"
        strokeDasharray="6 7"
        opacity="0.78"
      />
      <circle cx="120" cy="120" r="84" stroke="url(#epDvSealGrad)" strokeWidth="1.8" opacity="0.82" />
      <polygon
        points="120,36 192.7,162 47.3,162"
        stroke="url(#epDvSealGrad)"
        strokeWidth="2.2"
        strokeLinejoin="round"
        opacity="0.88"
      />
      <polygon
        points="120,204 47.3,78 192.7,78"
        stroke="url(#epDvSealGrad)"
        strokeWidth="2.2"
        strokeLinejoin="round"
        opacity="0.88"
      />
      <circle cx="120" cy="120" r="42" stroke="#fff1d0" strokeWidth="1.6" opacity="0.75" />
      <path
        d="M92 104c-8-14-6-30 6-40-2 12 4 22 14 26 5-10 8-22 8-30 9 10 14 20 12 31 10-4 16-14 14-26 12 10 14 26 6 40 10 9 14 23 10 36-5 15-21 25-42 25s-37-10-42-25c-4-13 0-27 14-37Z"
        stroke="url(#epDvSealGrad)"
        strokeWidth="2.4"
        fill="rgba(229, 25, 42, 0.2)"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function EpicCardOverlay({ epic }) {
  if (!epic || typeof document === 'undefined') return null

  const cardType = epic.card_type || epic.cardType
  if (!EPIC_CARD_TYPES.has(cardType)) return null

  const actor = typeof epic.actor === 'string' ? epic.actor.trim() : ''
  const target = typeof epic.target === 'string' ? epic.target.trim() : ''
  const count = typeof epic.count === 'number' && epic.count > 0 ? epic.count : 0
  const overlayKey = epic.key || `${cardType}:${actor}:${target}:${count}`

  if (cardType === 'armageddon') {
    const subtitle = actor ? `${actor} UNLEASHES THE APOCALYPSE` : 'THE APOCALYPSE BEGINS'
    return createPortal(
      <div
        key={overlayKey}
        className="epic-overlay epic-armageddon"
        role="alert"
        aria-live="assertive"
      >
        <div className="ep-backdrop ep-arma-backdrop" aria-hidden="true">
          <div className="ep-arma-heaven" />
          <div className="ep-arma-hell" />
          <div className="ep-arma-seam" />
        </div>

        <div className="ep-arma-ring r1" aria-hidden="true" />
        <div className="ep-arma-ring r2" aria-hidden="true" />
        <div className="ep-arma-eclipse-core" aria-hidden="true" />

        <div className="ep-arma-clash-stage" aria-hidden="true">
          <div className="ep-card-frame ep-arma-god">
            <SafeImg
              src="/static/cards/godcat/0.jpg"
              fallback="/ui/crown.png"
              className="ep-card-img"
              resetKey={overlayKey}
            />
          </div>
          <div className="ep-card-frame ep-arma-devil">
            <SafeImg
              src="/static/cards/devilcat/0.jpg"
              fallback="/ui/bomb.png"
              className="ep-card-img"
              resetKey={overlayKey}
            />
          </div>
        </div>

        <div className="ep-radial-particles" aria-hidden="true">
          {ARMAGEDDON_SPARKS.map((s) => (
            <span
              key={s.id}
              className="ep-spark"
              style={{
                '--tx': s.tx,
                '--ty': s.ty,
                '--rot': s.rot,
                '--size': s.size,
                '--delay': s.delay,
                '--dur': s.dur,
                '--pcol': s.color,
              }}
            />
          ))}
        </div>

        <div className="ep-arma-flash" aria-hidden="true" />

        <div className="ep-banner ep-banner-armageddon">
          <div className="ep-eyebrow">HEAVEN VS HELL · DUAL FATE</div>
          <div className="ep-title">ARMAGEDDON!</div>
          <div className="ep-subtitle">{subtitle}</div>
        </div>
      </div>,
      document.body,
    )
  }

  if (cardType === 'towerofpower') {
    const subtitle = actor ? `${actor} CLAIMS THE CROWN` : 'THE ROYAL STASH AWAKENS'
    return createPortal(
      <div
        key={overlayKey}
        className="epic-overlay epic-towerofpower"
        role="alert"
        aria-live="assertive"
      >
        <div className="ep-backdrop ep-tower-backdrop" aria-hidden="true" />
        <div className="ep-tower-rays" aria-hidden="true" />

        <div className="ep-tower-orbit" aria-hidden="true">
          {TOWER_STASH_CARDS.map((c) => (
            <div
              key={c.id}
              className="ep-tower-stash-slot"
              style={{
                '--tx': c.tx,
                '--ty': c.ty,
                '--rot': c.rot,
                '--delay': c.delay,
              }}
            >
              <div className="ep-tower-stash-card">
                <SafeImg
                  src="/backside.jpg"
                  fallback="/ui/crown.png"
                  className="ep-card-img"
                  resetKey={overlayKey}
                />
              </div>
            </div>
          ))}
        </div>

        <div className="ep-tower-center" aria-hidden="true">
          <div className="ep-tower-crown">
            <SafeImg src="/ui/crown.png" className="ep-prop-img" resetKey={overlayKey} />
          </div>
          <div className="ep-card-frame ep-tower-card">
            <SafeImg
              src="/static/cards/towerofpower/0.jpg"
              fallback="/ui/crown.png"
              className="ep-card-img"
              resetKey={overlayKey}
            />
          </div>
        </div>

        <div className="ep-radial-particles" aria-hidden="true">
          {TOWER_SPARKLES.map((s) => (
            <span
              key={s.id}
              className="ep-mote"
              style={{
                '--tx': s.tx,
                '--ty': s.ty,
                '--size': s.size,
                '--delay': s.delay,
                '--dur': s.dur,
                '--pcol': s.color,
              }}
            />
          ))}
        </div>

        <div className="ep-banner ep-banner-tower">
          <div className="ep-eyebrow">ROYAL CORONATION · 6-CARD STASH</div>
          <div className="ep-title">TOWER OF POWER!</div>
          <div className="ep-subtitle">{subtitle}</div>
        </div>
      </div>,
      document.body,
    )
  }

  if (cardType === 'catomicbomb') {
    return createPortal(
      <div
        key={overlayKey}
        className="epic-overlay epic-catomicbomb"
        role="alert"
        aria-live="assertive"
      >
        <div className="ep-backdrop ep-catomic-backdrop" aria-hidden="true" />
        <div className="ep-catomic-siren" aria-hidden="true" />
        <div className="ep-catomic-rays" aria-hidden="true" />
        <div className="ep-catomic-shock s1" aria-hidden="true" />
        <div className="ep-catomic-shock s2" aria-hidden="true" />

        <div className="ep-catomic-rocket" aria-hidden="true">
          <div className="ep-catomic-bomb-prop b-left">
            <SafeImg src="/ui/bomb.png" className="ep-prop-img" resetKey={overlayKey} />
          </div>
          <div className="ep-catomic-bomb-prop b-right">
            <SafeImg src="/ui/bomb.png" className="ep-prop-img" resetKey={overlayKey} />
          </div>
          <div className="ep-catomic-bomb-prop b-top">
            <SafeImg src="/ui/bomb.png" className="ep-prop-img" resetKey={overlayKey} />
          </div>
          <div className="ep-card-frame ep-catomic-card">
            <SafeImg
              src="/static/cards/catomicbomb/0.jpg"
              fallback="/ui/bomb.png"
              className="ep-card-img"
              resetKey={overlayKey}
            />
          </div>
        </div>

        <div className="ep-rising-particles" aria-hidden="true">
          {CATOMIC_EMBERS.map((e) => (
            <span
              key={e.id}
              className={`ep-rise ep-rise-${e.kind}`}
              style={{
                left: e.left,
                '--drift': e.drift,
                '--size': e.size,
                '--delay': e.delay,
                '--dur': e.dur,
                '--pcol': e.color,
              }}
            />
          ))}
        </div>

        <div className="ep-catomic-flash" aria-hidden="true" />

        <div className="ep-banner ep-banner-catomic">
          <div className="ep-eyebrow">NUCLEAR PROTOCOL · DECK MELTDOWN</div>
          <div className="ep-title">CATOMIC BOMB!</div>
          <div className="ep-subtitle">ALL BOMBS RISING TO THE TOP!</div>
        </div>
      </div>,
      document.body,
    )
  }

  if (cardType === 'attackofthedead') {
    const subtitle = actor
      ? `${actor} → ${target || 'NEXT'} · ${count ? `${count} TURNS` : 'CURSED ASSAULT'}`
      : `${target || 'NEXT'} · ${count ? `${count} TURNS` : 'CURSED ASSAULT'}`
    return createPortal(
      <div
        key={overlayKey}
        className="epic-overlay epic-attackofthedead"
        role="alert"
        aria-live="assertive"
      >
        <div className="ep-backdrop ep-dead-backdrop" aria-hidden="true" />
        <div className="ep-dead-mist" aria-hidden="true" />
        <div className="ep-dead-ring r1" aria-hidden="true" />
        <div className="ep-dead-ring r2" aria-hidden="true" />

        <div className="ep-dead-hand left" aria-hidden="true">
          <SafeImg
            src="/ui/fx/zombie-hand.png"
            fallback="/ui/skull.png"
            className="ep-prop-img"
            resetKey={overlayKey}
          />
        </div>
        <div className="ep-dead-hand right" aria-hidden="true">
          <SafeImg
            src="/ui/fx/zombie-hand.png"
            fallback="/ui/skull.png"
            className="ep-prop-img ep-flip-x"
            resetKey={overlayKey}
          />
        </div>

        <div className="ep-dead-center" aria-hidden="true">
          <div className="ep-card-frame ep-dead-card">
            <SafeImg
              src="/static/cards/attackofthedead/0.jpg"
              fallback="/ui/skull.png"
              className="ep-card-img"
              resetKey={overlayKey}
            />
          </div>
        </div>

        <div className="ep-rising-particles" aria-hidden="true">
          {DEAD_WISPS.map((w) => (
            <span
              key={w.id}
              className="ep-rise ep-rise-wisp"
              style={{
                left: w.left,
                '--drift': w.drift,
                '--size': w.size,
                '--delay': w.delay,
                '--dur': w.dur,
                '--pcol': w.color,
              }}
            />
          ))}
        </div>

        <div className="ep-banner ep-banner-dead">
          <div className="ep-eyebrow">UNDEAD LEGION · CURSED TURNS</div>
          <div className="ep-title">ATTACK OF THE DEAD!</div>
          <div className="ep-subtitle">{subtitle}</div>
        </div>
      </div>,
      document.body,
    )
  }

  if (cardType === 'godcat') {
    const subtitle = actor ? `${actor} COMMANDS THE TABLE` : 'DIVINE POWER COMMANDS THE TABLE'
    return createPortal(
      <div
        key={overlayKey}
        className="epic-overlay epic-godcat"
        role="alert"
        aria-live="assertive"
      >
        <div className="ep-backdrop ep-god-backdrop" aria-hidden="true" />
        <div className="ep-god-rays" aria-hidden="true" />
        <div className="ep-god-halo h1" aria-hidden="true" />
        <div className="ep-god-halo h2" aria-hidden="true" />

        <div className="ep-god-center" aria-hidden="true">
          <div className="ep-card-frame ep-god-card">
            <SafeImg
              src="/static/cards/godcat/0.jpg"
              fallback="/ui/crown.png"
              className="ep-card-img"
              resetKey={overlayKey}
            />
          </div>
        </div>

        <div className="ep-radial-particles" aria-hidden="true">
          {GODCAT_MOTES.map((m) => (
            <span
              key={m.id}
              className="ep-mote"
              style={{
                '--tx': m.tx,
                '--ty': m.ty,
                '--size': m.size,
                '--delay': m.delay,
                '--dur': m.dur,
                '--pcol': m.color,
              }}
            />
          ))}
        </div>

        <div className="ep-god-flash" aria-hidden="true" />

        <div className="ep-banner ep-banner-god">
          <div className="ep-eyebrow">DIVINE INTERVENTION · ANY CARD</div>
          <div className="ep-title">GODCAT!</div>
          <div className="ep-subtitle">{subtitle}</div>
        </div>
      </div>,
      document.body,
    )
  }

  // devilcat
  return createPortal(
    <div
      key={overlayKey}
      className="epic-overlay epic-devilcat"
      role="alert"
      aria-live="assertive"
    >
      <div className="ep-backdrop ep-dv-backdrop" aria-hidden="true" />

      <div className="ep-dv-flames" aria-hidden="true">
        {DEVILCAT_FLAMES.map((f) => (
          <span
            key={f.id}
            className={`ep-dv-flame ep-dv-f-${f.hue}`}
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

      <div className="ep-dv-seal-wrap" aria-hidden="true">
        <HellSealSvg />
      </div>

      <div className="ep-dv-center" aria-hidden="true">
        <div className="ep-card-frame ep-dv-card">
          <SafeImg
            src="/static/cards/devilcat/0.jpg"
            fallback="/ui/bomb.png"
            className="ep-card-img"
            resetKey={overlayKey}
          />
        </div>
      </div>

      <div className="ep-rising-particles" aria-hidden="true">
        {DEVILCAT_EMBERS.map((e) => (
          <span
            key={e.id}
            className={`ep-rise ep-rise-${e.kind}`}
            style={{
              left: e.left,
              '--drift': e.drift,
              '--size': e.size,
              '--delay': e.delay,
              '--dur': e.dur,
              '--pcol': e.color,
            }}
          />
        ))}
      </div>

      <div className="ep-dv-flash" aria-hidden="true" />

      <div className="ep-banner ep-banner-devil">
        <div className="ep-eyebrow">INFERNAL PACT · PLAYMAT ARMED</div>
        <div className="ep-title">DEVILCAT!</div>
        <div className="ep-subtitle">ARMAGEDDON NOW AWAKENS</div>
      </div>
    </div>,
    document.body,
  )
}

export default React.memo(EpicCardOverlay)
