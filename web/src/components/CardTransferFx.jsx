import React, { useEffect, useState } from 'react'
import { getCardName } from '../utils/cardCatalog.js'
import './CardTransferFx.css'

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function FxImg({ src, fallback, className = '', resetKey }) {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    setStage(0)
  }, [src, fallback, resetKey])

  const activeSrc = stage === 0 ? src : stage === 1 ? fallback : null
  if (!activeSrc) return null

  return (
    <img
      src={activeSrc}
      alt=""
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

function getTransferLabel(fx, catalog) {
  const { mode, source, reason, toDeck, actor, target, card } = fx

  if (mode === 'draw_mine') {
    if (source === 'bottom') return 'DRAW BOTTOM!'
    return 'DRAW!'
  }

  if (mode === 'draw_other') {
    const who = actor || 'Opponent'
    return source === 'bottom' ? `${who} DRAWS BOTTOM` : `${who} DRAWS`
  }

  if (mode === 'give_out') {
    if (toDeck) return 'PUT INTO DECK'
    if (reason === 'illtakethat' && card) {
      return `BẠN RÚT: ${getCardName(catalog, card.type, card.variant)}`
    }
    if (reason === 'favor') return target ? `FAVOR → ${target}` : 'GIVE CARD'
    return target ? `GIVE → ${target}` : 'GIVE CARD'
  }

  if (mode === 'receive_in') {
    return 'CARD RECEIVED!'
  }

  if (mode === 'transfer_other') {
    if (toDeck) return `${actor || '?'} → DECK`
    if (actor && target) return `${actor} → ${target}`
    if (actor) return `${actor} RECEIVES`
    return 'CARD TRANSFER'
  }

  return ''
}

export function getTransferDuration(fx) {
  if (fx?.reason === 'illtakethat' && fx?.mode === 'give_out' && fx?.card) return 1650
  return fx?.reason === 'favor' && fx?.mode === 'give_out' ? 980 : 850
}

export default React.memo(function CardTransferFx({ fx, catalog = null }) {
  if (!fx || !fx.mode || prefersReducedMotion()) return null

  const {
    key,
    mode,
    source = 'top',
    reason,
    toDeck = false,
    actor,
    target,
    card = null,
    deckAnchor = null,
  } = fx

  const isIlltakeReveal = mode === 'give_out' && reason === 'illtakethat' && Boolean(card)
  const cardImgSrc = isIlltakeReveal
    ? `/static/cards/${card.type}/${card.variant ?? 0}.jpg`
    : '/backside.jpg'
  const cardImgFallback = isIlltakeReveal
    ? `/static/cards/${card.type}/0.jpg`
    : '/ui/sort.png'

  const anchorStyle = deckAnchor
    ? {
        '--ctf-dx': `${deckAnchor.dx}px`,
        '--ctf-dy': `${deckAnchor.dy}px`,
        '--ctf-deck-w': `${deckAnchor.w}px`,
        '--ctf-deck-h': `${deckAnchor.h}px`,
      }
    : undefined

  const label = getTransferLabel(fx, catalog)
  const subLabel =
    mode === 'receive_in' && actor
      ? `FROM ${actor}`
      : isIlltakeReveal
        ? (target ? `I'LL TAKE THAT → ${target}` : "I'LL TAKE THAT")
        : mode === 'give_out' && reason === 'favor'
          ? 'HAND OVER · FAVOR'
          : null

  const rootClasses = [
    'card-transfer-layer',
    `mode-${mode}`,
    source === 'bottom' ? 'is-bottom' : 'is-top',
    toDeck ? 'is-to-deck' : '',
    reason === 'favor' ? 'is-favor' : '',
    isIlltakeReveal ? 'is-illtake-reveal' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div key={key || mode} className={rootClasses} style={anchorStyle} aria-hidden="true">
      {mode === 'receive_in' && <div className="ctf-catch-ring" />}
      {mode === 'give_out' && toDeck && <div className="ctf-deck-ring" />}
      {(mode === 'draw_mine' || isIlltakeReveal) && <div className="ctf-deck-ring ctf-draw-ring" />}

      {mode === 'give_out' && reason === 'favor' && (
        <div className="ctf-favor-pop">
          <FxImg
            src="/handout.png"
            fallback="/ui/trap.png"
            className="ctf-favor-img"
            resetKey={key}
          />
        </div>
      )}

      <div className="ctf-card-track">
        <div className="ctf-card-frame">
          <FxImg
            src={cardImgSrc}
            fallback={cardImgFallback}
            className="ctf-card-img"
            resetKey={key}
          />
        </div>
      </div>

      <div className="ctf-hand-track">
        <div className="ctf-hand-orient">
          <FxImg
            src="/ui/fx/draw-hand.png"
            fallback="/ui/play-hand.png"
            className="ctf-hand-img"
            resetKey={key}
          />
        </div>
      </div>

      {label && (
        <div className="ctf-pill-wrap">
          <div className="ctf-pill">{label}</div>
          {subLabel && <div className="ctf-sub-pill">{subLabel}</div>}
        </div>
      )}
    </div>
  )
})
