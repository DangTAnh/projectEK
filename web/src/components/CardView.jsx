import React, { useState } from 'react'

// emoji fallback khi chưa có ảnh thẻ
const EMOJI = {
  explodingkitten: '💥', implodingkitten: '😼', defuse: '✂️', streakingkitten: '🐈',
  zombiekitten: '🧟', godcat: '😇', devilcat: '😈', barkingkitten: '🐶',
  skip: '⏭️', superskip: '⏩', shuffle: '🔀', shufflenow: '🌀', attack2x: '⚔️',
  targetattack2x: '🎯', personalattack3x: '🥊', attackofthedead: '☠️',
  reverse: '↩️', drawfromthebottom: '⬇️', digdeeper: '⛏️', raisingheck: '🔥',
  bury: '⚰️', towerofpower: '👑', catomicbomb: '💣', feralcat: '🐾',
  seethefuture3x: '🔮', seethefuture5x: '🔮', revealthefuture3x: '📖',
  sharethefuture3x: '🤝', alter3x: '🃏', alter5x: '🃏', alter3xnow: '⚡',
  clairvoyance: '👁️', cat: '🐱', favor: '🎁', potluck: '🍲', illtakethat: '🫳',
  mark: '📌', curseofthecatbutt: '🙈', garbagecollection: '🗑️', graverobber: '⚰️',
  clone: '🧬', swaptopandbottom: '🔁', nope: '🚫', feedthedead: '🍖',
}

export default function CardView({ card, small = false, secret = false, label = '' }) {
  const [broken, setBroken] = useState(false)
  if (!card) return null
  const src = broken === false ? `/static/cards/${card.type}/${card.variant}.jpg`
    : broken === 'v0' ? `/static/cards/${card.type}/0.jpg`
      : null
  const faceupFlag = card.type === 'implodingkitten' && card.faceup ? ' MẶT LÊN' : ''
  return (
    <figure className={`card ${small ? 'small' : ''} ${secret ? 'secret' : ''}`}>
      {src
        ? <img src={src} alt={card.type} draggable={false}
               onError={() => setBroken(broken === false ? 'v0' : true)} />
        : <div className="card-fallback"><span>{EMOJI[card.type] || '❔'}</span></div>}
      <figcaption>
        {label && <b className="who">{label}</b>}
        {secret ? '?' : ''}
        {faceupFlag}
      </figcaption>
    </figure>
  )
}
