import React, { useEffect, useRef } from 'react'
import RealIcon from './RealIcon.jsx'
import CatAvatar from './CatAvatar.jsx'
import CardView from './CardView.jsx'
import { getCardName } from '../utils/cardCatalog.js'
import './PlayerList.css'

export default function PlayerList({
  players,
  turn,
  phase,
  meName,
  towerWearer,
  catalog,
  onInspectCard,
  onEditAvatar = null,
}) {
  const list = players || []
  const isPlaying = phase === 'playing'
  const isReversed = turn?.direction === -1
  const stripRef = useRef(null)
  const activeChipRef = useRef(null)

  useEffect(() => {
    if (!isPlaying || !turn?.current) return
    const container = stripRef.current
    const chip = activeChipRef.current
    if (!container || !chip) return
    const targetLeft = chip.offsetLeft - (container.clientWidth - chip.offsetWidth) / 2
    container.scrollTo({ left: Math.max(0, targetLeft), behavior: 'smooth' })
  }, [isPlaying, turn?.current])

  return (
    <div ref={stripRef} className="players-strip" role="list" aria-label="Danh sách người chơi">
      {list.map((p, idx) => {
        const isMe = p.name === meName
        const isTurn = isPlaying && turn?.current === p.name
        const isConnected = p.connected !== false
        const isTower = !!towerWearer && towerWearer === p.name
        const turnsLeft = isTurn && (turn?.turns_left ?? 1) > 1 ? turn.turns_left : 0
        const markedName = p.marked ? getCardName(catalog, p.marked.type, p.marked.variant) : ''
        const illTakeCard = p.illtake_by
          ? { id: `illtake-${p.name}`, type: 'illtakethat', variant: 0 }
          : null
        const faceupCards = Array.isArray(p.faceup) ? p.faceup : []
        const hasSeatTags = !isConnected || isTower || p.blind || turnsLeft > 1 || (!isTurn && p.extra_turns > 0)
        const hasPeeks = Boolean(p.marked || illTakeCard || faceupCards.length > 0)
        const canEditMe = isMe && typeof onEditAvatar === 'function'
        const nextPlayer = idx < list.length - 1 ? list[idx + 1] : null
        const arrowActive = isPlaying && (
          isReversed ? turn?.current === nextPlayer?.name : isTurn
        )

        return (
          <React.Fragment key={p.name}>
            <div
              ref={isTurn ? activeChipRef : null}
              role="listitem"
              className={`player-chip ${p.alive ? '' : 'dead'} ${isTurn ? 'turn' : ''} ${isMe ? 'is-me' : ''} ${isConnected ? '' : 'offline'}`}
              title={[
                p.name,
                isMe ? '(Bạn — bấm vào mèo để tùy chỉnh)' : '',
                !isConnected ? 'Đang mất kết nối' : '',
                p.blind ? 'Đang bị mù bài' : '',
                isTower ? 'Đang đội Tower of Power' : '',
                p.illtake_by ? `Bị ${p.illtake_by} đặt bẫy I'll Take That` : '',
              ].filter(Boolean).join(' · ')}
            >
            {canEditMe ? (
              <button
                type="button"
                className="seat-cat-perch editable"
                aria-label="Tùy chỉnh nhân vật mèo của bạn"
                title="Bấm để tùy chỉnh nhân vật mèo"
                onClick={onEditAvatar}
              >
                <CatAvatar
                  avatar={p.avatar}
                  name={p.name}
                  size={38}
                  dead={!p.alive}
                  blind={!!p.blind}
                  isTower={isTower}
                />
                {!isConnected && <i className="offline-dot" />}
              </button>
            ) : (
              <div className="seat-cat-perch">
                <CatAvatar
                  avatar={p.avatar}
                  name={p.name}
                  size={38}
                  dead={!p.alive}
                  blind={!!p.blind}
                  isTower={isTower}
                />
                {!isConnected && <i className="offline-dot" />}
              </div>
            )}

            <div className="seat-plate player-nameplate">
              <div className="seat-main">
                <span className="pname">
                  {p.name}
                  {isMe && <em className="me-tag">Bạn</em>}
                </span>
                {phase !== 'lobby' && (
                  <span className="seat-cards pcount" title={`${p.count} lá trên tay`}>
                    <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <rect x="4" y="2.5" width="9" height="11.5" rx="1.6" />
                      <path d="M2.5 5v7.5A1.5 1.5 0 0 0 4 14h6.5" />
                    </svg>
                    {p.count}
                  </span>
                )}
              </div>
              {hasSeatTags && (
                <div className="seat-tags">
                  {!isConnected && (
                    <span className="offline-tag" title="Mất kết nối">
                      <span className="offline-pulse-dot" aria-hidden="true" />
                    </span>
                  )}
                  {isTower && (
                    <span className="crown-tag" title="Đang đội Tower of Power">
                      <RealIcon name="crown" size={14} />
                    </span>
                  )}
                  {p.blind && (
                    <span className="status-icon-tag" title="Đang bị mù bài">
                      <RealIcon name="blind" size={14} />
                    </span>
                  )}
                  {turnsLeft > 1 && <span className="turns-badge" title={`Còn ${turnsLeft} lượt rút`}>×{turnsLeft}</span>}
                  {!isTurn && p.extra_turns > 0 && (
                    <span className="extra-badge" title={`Có thêm ${p.extra_turns} lượt`}>+{p.extra_turns}</span>
                  )}
                </div>
              )}
            </div>
            {hasPeeks && (
              <div className="seat-peeks" aria-label={`Thẻ công khai của ${p.name}`}>
                {p.marked && (
                  <button
                    type="button"
                    className="seat-peek-card is-marked"
                    title={`Lá bị Mark: ${markedName} (bấm để xem)`}
                    aria-label={`Lá bị Mark: ${markedName}`}
                    onClick={() => onInspectCard?.(p.marked)}
                  >
                    <span className="seat-peek-clip">
                      <CardView card={p.marked} small marked catalog={catalog} />
                    </span>
                  </button>
                )}
                {illTakeCard && (
                  <button
                    type="button"
                    className="seat-peek-card is-trap"
                    title={`Bị ${p.illtake_by} đặt bẫy I'll Take That`}
                    aria-label={`Bị ${p.illtake_by} đặt bẫy I'll Take That`}
                    onClick={() => onInspectCard?.(illTakeCard)}
                  >
                    <span className="seat-peek-clip">
                      <CardView card={illTakeCard} small catalog={catalog} />
                    </span>
                    <span className="seat-peek-badge is-trap">
                      <RealIcon name="trap" size={10} />
                      <span className="seat-peek-who">{p.illtake_by}</span>
                    </span>
                  </button>
                )}
                {faceupCards.map((c, cIdx) => {
                  const faceupName = getCardName(catalog, c.type)
                  return (
                    <button
                      key={c.id || `${p.name}-faceup-${cIdx}`}
                      type="button"
                      className="seat-peek-card is-faceup"
                      title={`${faceupName} lật trước mặt (bấm để xem)`}
                      aria-label={`${faceupName} lật trước mặt`}
                      onClick={() => onInspectCard?.(c)}
                    >
                      <span className="seat-peek-clip">
                        <CardView card={c} small catalog={catalog} />
                      </span>
                    </button>
                  )
                })}
              </div>
            )}
            </div>
            {isPlaying && idx < list.length - 1 && (
              <span
                className={`seat-dir-arrow ${arrowActive ? 'active' : ''} ${isReversed ? 'rev' : ''}`}
                title={isReversed ? 'Chiều đánh: Ngược lại (←)' : 'Chiều đánh: Thuận chiều (→)'}
                aria-hidden="true"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  {isReversed
                    ? <><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></>
                    : <><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></>}
                </svg>
              </span>
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}
