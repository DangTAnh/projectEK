import React, { useEffect, useState } from 'react'
import RealIcon from './RealIcon.jsx'
import { getCardIcon, getCardName } from '../utils/cardCatalog.js'

export default function CardView({
  card,
  small = false,
  mini = false,
  secret = false,
  marked = false,
  label = '',
  catalog = null,
}) {
  const [broken, setBroken] = useState(false)

  useEffect(() => {
    setBroken(false)
  }, [card?.type, card?.variant])

  if (!card) return null
  const variant = card.variant ?? 0
  const src = broken === false ? `/static/cards/${card.type}/${variant}.jpg`
    : broken === 'v0' ? `/static/cards/${card.type}/0.jpg`
      : null
  const displayName = getCardName(catalog, card.type, variant)
  const faceupFlag = card.type === 'implodingkitten' && card.faceup ? ' MẶT LÊN' : ''
  const sizeClass = mini ? 'mini' : small ? 'small' : ''

  return (
    <figure className={`card ${sizeClass} ${secret ? 'secret' : ''} ${marked ? 'is-marked' : ''}`}>
      {src
        ? (
          <img
            src={src}
            alt={displayName}
            draggable={false}
            onError={() => setBroken(broken === false && variant !== 0 ? 'v0' : true)}
          />
        )
        : (
          <div className="card-fallback" aria-label={displayName}>
            <RealIcon name={getCardIcon(card.type)} size={mini ? 24 : small ? 38 : 48} />
            {!mini && <small>{displayName}</small>}
          </div>
        )}
      {marked && (
        <span className="card-mark-badge" title="Lá này đang bị Mark công khai">
          <RealIcon name="pin" size={16} />
        </span>
      )}
      {(label || secret || faceupFlag) && (
        <figcaption>
          {label && <b className="who">{label}</b>}
          {secret ? '?' : ''}
          {faceupFlag}
        </figcaption>
      )}
    </figure>
  )
}
