import React from 'react'
import CardView from './CardView.jsx'
import { getCardName } from '../utils/cardCatalog.js'
import './FutureVisionPanel.css'

const isBombType = (t) => (
  t === 'explodingkitten' || t === 'implodingkitten' || t === 'devilcat'
)

const isSafeType = (t) => (
  t === 'defuse' || t === 'zombiekitten' || t === 'skip' || t === 'superskip'
)

function EyeIcon({ size = 15 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="fv-icon"
    >
      <path
        d="M1.333 8C2.467 5.28 5.013 3.5 8 3.5C10.987 3.5 13.533 5.28 14.667 8C13.533 10.72 10.987 12.5 8 12.5C5.013 12.5 2.467 10.72 1.333 8Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx="8"
        cy="8"
        r="2"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  )
}

function BombDotIcon({ size = 15 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="fv-icon"
    >
      <circle cx="7" cy="9.5" r="4.5" fill="currentColor" />
      <path
        d="M9.6 5.6L11.2 4M11.2 4L12.8 2.4M11.2 4L13 4.8M11.2 4L10.4 2.2"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  )
}

function FutureVisionPanel({ cards, peekMeta, open, onToggle, catalog, onInspectCard }) {
  if (!cards?.length) return null

  const hasBomb = cards.some((c) => isBombType(c?.type))
  const bombFirst = isBombType(cards[0]?.type)
  const isShared = peekMeta?.source === 'share'
  const sharedBy = peekMeta?.from || ''
  const eyebrow = isShared ? 'SHARE THE FUTURE' : 'SEE THE FUTURE'
  const title = isShared
    ? (sharedBy ? `${sharedBy} chia sẻ Top ${cards.length} lá` : `Được chia sẻ Top ${cards.length} lá`)
    : `Top ${cards.length} Cards`
  const dockLabel = isShared ? `Chia sẻ · Top ${cards.length}` : `Top ${cards.length}`

  if (!open) {
    return (
      <button
        type="button"
        className={`fv-dock-pill ${hasBomb ? 'has-bomb' : ''}`}
        onClick={onToggle}
        title={isShared ? 'Mở lại các lá được chia sẻ' : 'Mở lại tầm nhìn tương lai'}
        aria-expanded={false}
      >
        <EyeIcon size={15} />
        <span className="fv-dock-label">{dockLabel}</span>
        {hasBomb && (
          <span className="fv-dock-danger">
            <span className="fv-dock-danger-dot" aria-hidden="true" />
            BOMB
          </span>
        )}
      </button>
    )
  }

  return (
    <section
      className={`fv-stage ${hasBomb ? 'has-bomb' : ''}`}
      role="region"
      aria-label={isShared ? 'Share the Future — Shared Top Deck Cards' : 'See the Future — Top Deck Cards'}
    >
      <header className="fv-header">
        <div className="fv-title-group">
          <span className="fv-eyebrow">{eyebrow}</span>
          <h3 className="fv-title">{title}</h3>
        </div>

        <div className="fv-header-controls">
          {hasBomb && (
            <span className={`fv-hazard-pill ${bombFirst ? 'is-critical' : ''}`}>
              <BombDotIcon size={14} />
              <span>{bombFirst ? 'BOMB AT #1' : `BOMB IN TOP ${cards.length}`}</span>
            </span>
          )}
          <button
            type="button"
            className="fv-min-btn"
            onClick={onToggle}
            aria-expanded={true}
          >
            Thu gọn
          </button>
        </div>
      </header>

      <div className="fv-rail">
        {cards.map((c, i) => {
          const bomb = isBombType(c?.type)
          const safe = !bomb && isSafeType(c?.type)
          const cardName = getCardName(catalog, c?.type)
          const slotClass = [
            'fv-slot',
            i === 0 ? 'is-next' : '',
            bomb ? 'is-bomb' : '',
            safe ? 'is-safe' : '',
          ].filter(Boolean).join(' ')

          return (
            <React.Fragment key={c?.id || `${c?.type || 'card'}-${i}`}>
              {i > 0 && <span className="fv-arrow" aria-hidden="true">›</span>}
              <div className={slotClass} style={{ '--fv-delay': `${i * 55}ms` }}>
                <div className="fv-slot-head">
                  <span className="fv-order-badge">
                    {i === 0 ? '#1 · NEXT' : `#${i + 1}`}
                  </span>
                  {bomb && <span className="fv-tag is-bomb">BOMB</span>}
                  {safe && <span className="fv-tag is-safe">SAFE</span>}
                </div>

                <button
                  type="button"
                  className="fv-card-btn"
                  title={`Phóng to ${cardName}`}
                  onClick={() => onInspectCard?.(c)}
                >
                  <CardView card={c} secret catalog={catalog} />
                </button>

                <span className="fv-card-name" title={cardName}>{cardName}</span>
              </div>
            </React.Fragment>
          )
        })}
      </div>
    </section>
  )
}

export const RevealedFutureStrip = React.memo(function RevealedFutureStrip({
  cards,
  catalog,
  onInspectCard,
}) {
  if (!cards?.length) return null

  return (
    <div className="fv-revealed-strip" role="region" aria-label="Public Top Deck Cards">
      <span className="fv-strip-eyebrow">
        <EyeIcon size={15} />
        <span>PUBLIC TOP CARDS</span>
      </span>

      <div className="fv-strip-row">
        {cards.map((c, i) => {
          const bomb = isBombType(c?.type)
          const cardName = getCardName(catalog, c?.type)
          return (
            <React.Fragment key={c?.id || `${c?.type || 'rev'}-${i}`}>
              {i > 0 && <span className="fv-strip-arrow" aria-hidden="true">›</span>}
              <button
                type="button"
                className={`fv-strip-card ${bomb ? 'is-bomb' : ''}`}
                title={`#${i + 1} ${cardName} — Bấm để phóng to`}
                onClick={() => onInspectCard?.(c)}
              >
                <span className="fv-strip-pos">#{i + 1}</span>
                <CardView card={c} catalog={catalog} />
              </button>
            </React.Fragment>
          )
        })}
      </div>
    </div>
  )
})

export const BombRadarStrip = React.memo(function BombRadarStrip({ positions, deckCount }) {
  if (!positions?.length) return null

  const denom = Math.max(deckCount || 1, ...positions, 1)

  return (
    <div className="fv-bomb-radar" role="status" aria-live="polite" aria-label="Bomb Radar">
      <span className="fv-radar-label">
        <BombDotIcon size={15} />
        <span>BOMB RADAR</span>
      </span>

      <div className="fv-radar-meter">
        <span className="fv-radar-end">TOP</span>
        <div className="fv-radar-track" aria-hidden="true">
          <span className="fv-radar-rail" />
          {positions.map((pos, idx) => {
            const pct = Math.min(
              96,
              Math.max(4, ((pos - 1) / Math.max(1, denom - 1)) * 92 + 4),
            )
            return (
              <span
                key={`${pos}-${idx}`}
                className={`fv-radar-dot ${pos === 1 ? 'is-critical' : ''}`}
                style={{ left: `${pct}%` }}
                title={`Bom tại vị trí #${pos}`}
              />
            )
          })}
        </div>
        <span className="fv-radar-end">BOTTOM</span>
      </div>

      <div className="fv-radar-pills">
        {positions.map((pos, idx) => (
          <span
            key={`${pos}-${idx}`}
            className={`fv-radar-pill ${pos === 1 ? 'is-critical' : ''}`}
          >
            #{pos}
          </span>
        ))}
      </div>
    </div>
  )
})

export default React.memo(FutureVisionPanel)
