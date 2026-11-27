import React, { useEffect, useState } from 'react'
import './CardSlamHand.css'

const DANGER_TYPES = new Set([
  'nope',
  'attack',
  'targetedattack',
  'personalattack',
  'attackofthedead',
  'explodingkitten',
  'implodingkitten',
  'devilcat',
  'barkingkitten',
  'curseofthecatbutt',
])

const EMERALD_TYPES = new Set([
  'defuse',
  'skip',
  'superskip',
  'reverse',
  'shuffle',
  'seethefuture',
  'alterthefuture',
])

function getRippleTone(cardType) {
  if (!cardType) return 'gold'
  if (DANGER_TYPES.has(cardType)) return 'danger'
  if (EMERALD_TYPES.has(cardType)) return 'emerald'
  return 'gold'
}

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export default React.memo(function CardSlamHand({ slam }) {
  const [handBroken, setHandBroken] = useState(false)

  useEffect(() => {
    setHandBroken(false)
  }, [slam?.key])

  if (!slam || prefersReducedMotion()) return null

  const sideClass = slam.isMine ? 'is-mine' : 'is-opponent'
  const toneClass = `tone-${getRippleTone(slam.cardType)}`

  return (
    <div
      key={slam.key}
      className={`card-slam-layer ${sideClass} ${toneClass}`}
      aria-hidden="true"
    >
      <div className="slam-shadow" />
      <div className="slam-ripple" />
      <div className="slam-ripple slam-ripple-outer" />
      {!handBroken && (
        <div className="slam-hand-track">
          <img
            src="/ui/play-hand.png"
            alt=""
            className="slam-hand-img"
            draggable={false}
            decoding="async"
            onError={() => setHandBroken(true)}
          />
        </div>
      )}
    </div>
  )
})
