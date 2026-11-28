import React, { useEffect, useRef } from 'react'
import RealIcon from './RealIcon.jsx'
import CatAvatar from './CatAvatar.jsx'
import { getCardName } from '../utils/cardCatalog.js'

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

            <div className="seat-plate">
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
              {(!isConnected || isTower || p.blind || turnsLeft > 1 || (!isTurn && p.extra_turns > 0) || (p.faceup?.length || 0) > 0 || p.illtake_by || p.marked) && (
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
                  {(p.faceup?.length || 0) > 0 && (
                    <span className="chip-icon" title="Barking Kitten lật trước mặt">
                      <RealIcon name="dog" size={15} />
                    </span>
                  )}
                  {p.illtake_by && (
                    <span className="trap-pill" title={`Lá rút kế tiếp thuộc về ${p.illtake_by}`}>
                      <RealIcon name="trap" size={13} /> {p.illtake_by}
                    </span>
                  )}
                  {p.marked && (
                    <button
                      type="button"
                      className="marked-pill"
                      title={`Lá bị Mark: ${markedName} (bấm để xem)`}
                      onClick={() => onInspectCard?.(p.marked)}
                    >
                      <RealIcon name="pin" size={13} /> {markedName}
                    </button>
                  )}
                </div>
              )}
            </div>
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
