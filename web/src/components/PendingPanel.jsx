import React, { useEffect, useState } from 'react'
import CardView from './CardView.jsx'
import CardPickerModal from './CardPickerModal.jsx'
import RealIcon from './RealIcon.jsx'
import { getCardMeta, getCardName } from '../utils/cardCatalog.js'

const BOMB_INSERT_REASONS = new Set(['defuse', 'defuse_receive', 'zombie', 'imploding', 'godcat_defuse'])

const REASON_TEXT = {
  defuse: 'Chọn vị trí chèn Exploding Kitten (1 = đỉnh deck)',
  defuse_receive: 'Nhận Exploding Kitten — chọn vị trí chèn lại vào deck (1 = đỉnh)',
  zombie: 'Chèn bom lại vào deck (1 = đỉnh)',
  imploding: 'Đặt Imploding Kitten trở lại deck (1 = đỉnh)',
  godcat_defuse: 'Chèn bom lại vào deck (Godcat làm Defuse, 1 = đỉnh)',
  bury: 'Chọn vị trí vùi lá vừa nhặt (1 = đỉnh)',
  favor: 'Ai phải đưa thẻ?',
  steal: 'Ăn trộm thẻ của ai?',
  call_card: 'Gọi tên thẻ của ai?',
  targetattack: 'Tấn công ai (nhận thêm lượt)?',
  mark: 'Mark ai?',
  curse: 'Curse ai?',
  illtakethat: 'Bẫy lá rút kế tiếp của ai?',
  revive: 'Hồi sinh ai?',
  barking: 'Ép Defuse-or-die: chọn nạn nhân',
  armageddon_target: 'Giao lá úp cho ai?',
  potluck: 'Chọn 1 thẻ đặt lên đỉnh deck (Potluck)',
  into_deck: 'Chọn 1 thẻ cài lén vào deck',
  feedthedead: 'Chọn 1 thẻ dâng cho người hồi sinh',
  blind_defuse: 'Đang bị MÙ và rút phải bom — chọn bừa lá úp trên tay để tìm Defuse!',
}

export default function PendingPanel({
  pending,
  mine,
  send,
  connected = true,
  overHo = false,
  isBlind = false,
  canClairvoyance = false,
  catalog = null,
  peekCards = [],
  onInspectCard = null,
}) {
  const promptKey = pending ? `${pending.kind}:${pending.owner}:${JSON.stringify(pending.data || {})}` : 'none'
  const minVal = pending?.data?.min ?? 0
  const maxVal = pending?.data?.max ?? 0
  const [idx, setIdx] = useState(minVal)

  useEffect(() => {
    setIdx(pending?.data?.min ?? 0)
  }, [promptKey, pending?.data?.min])

  if (!pending) return null

  if (!mine) {
    return (
      <div className="pending-panel waiting" role="status" aria-live="polite">
        <h3><RealIcon name="hourglass" size={18} /> {pending.owner} đang quyết định…</h3>
        {canClairvoyance && (
          <p className="handout-sub">
            🔮 Bạn có <b>Clairvoyance</b> — bấm <b>NOW</b> trên lá Clairvoyance để nhìn lén vị trí đặt bom!
          </p>
        )}
      </div>
    )
  }

  const { kind, data = {} } = pending
  const isBombInsert = kind === 'pick_index' && BOMB_INSERT_REASONS.has(data.reason)
  const displayMin = minVal + 1
  const displayMax = maxVal + 1
  const displayIdx = idx + 1
  const depthPct = maxVal > minVal ? Math.min(100, Math.max(0, ((idx - minVal) / (maxVal - minVal)) * 100)) : 0
  const respond = (payload) => {
    if (!connected) return
    send({ action: 'respond', payload })
  }

  // Dig Deeper / Raising Heck: hiển thị ngay lá vừa đào nếu backend gửi data.card (hoặc fallback từ peek)
  const yesNoCard = kind === 'yes_no'
    ? (data.card || (peekCards?.length === 1 && /đào|đáy/i.test(data.question || '') ? peekCards[0] : null))
    : null
  const yesNoMeta = yesNoCard ? getCardMeta(catalog, yesNoCard.type) : null

  return (
    <div className="pending-panel" role="dialog" aria-live="polite" aria-label="Lượt quyết định của bạn">
      <div className="pend-eyebrow">
        {kind === 'reorder'
          ? 'ALTER THE FUTURE'
          : (isBombInsert || data.reason === 'blind_defuse')
            ? 'DEFUSE BOMB'
            : 'ACTION REQUIRED'}
      </div>
      <h3>Đến lượt quyết định của bạn</h3>

      {kind === 'pick_index' && (
        <div className="pend-row pick-index-layout">
          <p>{REASON_TEXT[data.reason] || data.reason}</p>
          {data.card && (
            <button
              type="button"
              className="pend-card-btn"
              title="Bấm để xem chi tiết lá bài"
              onClick={() => onInspectCard?.(data.card)}
            >
              <CardView card={data.card} small catalog={catalog} />
            </button>
          )}
          <div className="pick-index-controls">
            <div className="preset-row">
              <button
                type="button"
                className={`preset-chip ${idx === minVal ? 'active' : ''}`}
                disabled={!connected}
                onClick={() => setIdx(minVal)}
              >
                Đỉnh ({displayMin})
              </button>
              {maxVal >= minVal + 1 && (
                <button
                  type="button"
                  className={`preset-chip ${idx === minVal + 1 ? 'active' : ''}`}
                  disabled={!connected}
                  onClick={() => setIdx(minVal + 1)}
                >
                  Thứ 2 ({displayMin + 1})
                </button>
              )}
              {maxVal >= minVal + 2 && (
                <button
                  type="button"
                  className={`preset-chip ${idx === minVal + 2 ? 'active' : ''}`}
                  disabled={!connected}
                  onClick={() => setIdx(minVal + 2)}
                >
                  Thứ 3 ({displayMin + 2})
                </button>
              )}
              {maxVal > minVal && (
                <button
                  type="button"
                  className="preset-chip"
                  disabled={!connected}
                  onClick={() => {
                    const rand = minVal + Math.floor(Math.random() * (maxVal - minVal + 1))
                    setIdx(rand)
                  }}
                >
                  <RealIcon name="sort" size={14} /> Ngẫu nhiên
                </button>
              )}
              {maxVal > minVal && (
                <button
                  type="button"
                  className={`preset-chip ${idx === maxVal ? 'active' : ''}`}
                  disabled={!connected}
                  onClick={() => setIdx(maxVal)}
                >
                  Đáy ({displayMax})
                </button>
              )}
            </div>
            <div className={`depth-meter ${isBombInsert ? 'is-bomb' : ''}`} aria-hidden="true">
              <div className="depth-labels">
                <span>TOP ({displayMin})</span>
                <span>BOTTOM ({displayMax})</span>
              </div>
              <div className="depth-track">
                <div className="depth-fill" style={{ width: `${depthPct}%` }} />
                <div className="depth-pip" style={{ left: `${depthPct}%` }} />
              </div>
            </div>
            <div className="slider-row">
              <input
                type="range"
                aria-label="Vị trí chèn từ đỉnh deck"
                min={minVal}
                max={maxVal}
                value={idx}
                disabled={maxVal <= minVal}
                onChange={(e) => setIdx(+e.target.value)}
              />
              <b>
                {maxVal <= minVal
                  ? `Deck trống — đặt ở đỉnh (${displayMin})`
                  : idx === minVal
                    ? `Vị trí ${displayIdx} / ${displayMax} (Đỉnh — rút kế tiếp!)`
                    : idx === maxVal
                      ? `Vị trí ${displayIdx} / ${displayMax} (Đáy deck)`
                      : `Vị trí ${displayIdx} / ${displayMax} từ đỉnh`}
              </b>
              <button
                type="button"
                className="primary"
                disabled={!connected}
                onClick={() => respond({ index: idx })}
              >
                Xác nhận
              </button>
            </div>
          </div>
        </div>
      )}

      {kind === 'yes_no' && (
        <div className="pend-row yesno-layout">
          <p>{data.question}</p>
          {yesNoCard && (
            <div className="yesno-preview">
              <button
                type="button"
                className="pend-card-btn"
                title="Bấm để phóng to"
                onClick={() => onInspectCard?.(yesNoCard)}
              >
                <CardView card={yesNoCard} small catalog={catalog} />
              </button>
              <div className="yesno-card-info">
                <strong>{getCardName(catalog, yesNoCard.type, yesNoCard.variant)}</strong>
                {yesNoMeta?.description && <p className="yesno-desc">{yesNoMeta.description}</p>}
              </div>
            </div>
          )}
          <div className="yesno-btns">
            <button type="button" className="primary" disabled={!connected} onClick={() => respond({ value: true })}>
              Có
            </button>
            <button type="button" disabled={!connected} onClick={() => respond({ value: false })}>
              Không
            </button>
          </div>
        </div>
      )}

      {kind === 'pick_player' && (
        <div className="pend-row pend-player-layout">
          <p>{REASON_TEXT[data.reason] || 'Chọn người chơi'}:</p>
          <div className="pend-player-grid">
            {(data.candidates || []).map((c) => (
              <button
                key={c}
                type="button"
                className="pend-player-btn"
                disabled={!connected}
                onClick={() => respond({ player: c })}
              >
                <span className="pend-player-avatar" aria-hidden="true">{(c || '?')[0].toUpperCase()}</span>
                <span className="pend-player-name">{c}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {kind === 'input_card' && (
        <CardPickerModal
          key={promptKey}
          inline
          mode="call_card"
          catalog={catalog}
          disabled={!connected}
          iconName="turn"
          title={`Gọi tên thẻ muốn lấy từ ${data.victim}`}
          subtitle="Chọn thẻ từ danh sách hoặc gõ tên để lọc (Enter chọn kết quả đầu)"
          onSelect={(ctype) => respond({ text: ctype })}
        />
      )}

      {kind === 'pick_card' && data.source === 'victim_hand' && (
        <div className="pend-row">
          <p className="pend-prompt-line">
            <RealIcon name="trap" size={18} /> Trộm 1 thẻ từ tay <b>{data.victim}</b> — chọn úp một lá:
          </p>
          <div className="steal-backs">
            {Array.from({ length: data.count || 0 }, (_, i) => (
              <button
                key={i}
                type="button"
                className="steal-back"
                disabled={!connected}
                aria-label={`Chọn lá úp số ${i + 1} của ${data.victim}`}
                title={`Chọn lá #${i + 1}`}
                onClick={() => respond({ position: i })}
              >
                <div className="card-back" />
                <span className="steal-num">#{i + 1}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {kind === 'pick_card' && data.source === 'own_hand' && (
        <div className={`handout-zone ${isBlind ? 'is-blind' : ''}`}>
          <div id="handout-drop" className={`handout-drop ${overHo ? 'over' : ''}`}>
            {data.reason === 'blind_defuse' && data.card ? (
              <button
                type="button"
                className="pend-card-btn"
                title="Bấm để xem chi tiết lá bom"
                onClick={() => onInspectCard?.(data.card)}
              >
                <CardView card={data.card} small catalog={catalog} />
              </button>
            ) : (
              <img src="/handout.png" alt="" className="handout-img" draggable={false} />
            )}
          </div>
          <div className="handout-text">
            {data.reason === 'blind_defuse' ? (
              <>
                <p className="handout-hint">
                  <RealIcon name="bomb" size={18} /> Bạn đang bị MÙ và rút phải <b>{getCardName(catalog, data.card?.type || 'explodingkitten', data.card?.variant)}</b>! Hãy lật bừa 1 lá úp để tìm Defuse.
                </p>
                {data.last_wasted && (
                  <p className="handout-sub">
                    Vừa đánh trượt: <b>{data.last_wasted}</b> (mất hiệu lực) — hãy chọn tiếp lá úp khác!
                  </p>
                )}
                <p className="handout-sub">
                  Trúng Defuse/Zombie/Godcat sẽ cứu sống và gỡ mù · Trúng lá bỏ lượt (Skip/Super Skip/Reverse/Attack) sẽ nổ ngay · Kéo thả lá úp vào đây hoặc bấm chọn rồi bấm “Thử lật lá úp”.
                </p>
              </>
            ) : isBlind ? (
              <>
                <p className="handout-hint">
                  <RealIcon name="blind" size={18} /> Bạn đang bị mù! Hãy tự chọn hoặc kéo 1 lá úp bất kỳ
                  {data.give_to
                    ? <> đưa cho <b>{data.give_to}</b></>
                    : <> ({REASON_TEXT[data.reason] || 'từ tay bài'})</>}
                </p>
                <p className="handout-sub">
                  Kéo 1 lá úp bên dưới thả vào bàn tay, hoặc bấm chọn 1 lá úp rồi bấm “Đưa lá úp”.
                </p>
              </>
            ) : (
              <>
                <p className="handout-hint">
                  {REASON_TEXT[data.reason] || 'Chọn 1 lá từ tay bài'}
                  {data.give_to ? <> để đưa <b>{data.give_to}</b></> : ''}
                </p>
                <p className="handout-sub">
                  Kéo 1 lá vào bàn tay hoặc bấm chọn 1 lá bên dưới rồi bấm “Đưa lá đã chọn”.
                </p>
              </>
            )}
          </div>
        </div>
      )}

      {kind === 'reorder' && (
        <ReorderForm
          key={promptKey}
          cards={data.cards || []}
          catalog={catalog}
          connected={connected}
          onInspectCard={onInspectCard}
          onDone={(order) => respond({ order })}
        />
      )}
    </div>
  )
}

function isBombCard(card) {
  const t = card?.type
  return t === 'explodingkitten' || t === 'implodingkitten' || t === 'devilcat'
}

function ReorderForm({ cards, catalog, connected, onInspectCard, onDone }) {
  const [order, setOrder] = useState(() => cards.map((c) => c.id))
  const [swapIdx, setSwapIdx] = useState(null)

  const firstCard = cards.find((x) => x.id === order[0])
  const firstIsBomb = isBombCard(firstCard)

  function move(i, dir) {
    const j = i + dir
    if (j < 0 || j >= order.length) return
    const next = order.slice()
    ;[next[i], next[j]] = [next[j], next[i]]
    setOrder(next)
    setSwapIdx(null)
  }

  function handleCardClick(i) {
    if (!connected) return
    if (swapIdx === null) {
      setSwapIdx(i)
      return
    }
    if (swapIdx === i) {
      setSwapIdx(null)
      return
    }
    const next = order.slice()
    ;[next[swapIdx], next[i]] = [next[i], next[swapIdx]]
    setOrder(next)
    setSwapIdx(null)
  }

  return (
    <div className="pend-row reorder-layout">
      <div className="reorder-oracle-head">
        <p>Sắp xếp lại các thẻ trên cùng (từ trái sang phải = thứ tự sẽ rút):</p>
        {firstIsBomb && (
          <span className="reorder-bomb-warn">
            <RealIcon name="bomb" size={14} /> BOMB AT #1!
          </span>
        )}
      </div>
      <p className="reorder-swap-hint">Bấm 2 lá để đổi chỗ nhanh, hoặc dùng nút ← → bên dưới</p>
      <ol className="reorder-list reorder-oracle-list">
        {order.map((id, i) => {
          const c = cards.find((x) => x.id === id)
          if (!c) return null
          const cardName = getCardName(catalog, c.type, c.variant)
          const isBomb = isBombCard(c)
          return (
            <React.Fragment key={id}>
              {i > 0 && (
                <li className="reorder-arrow-sep" aria-hidden="true">➔</li>
              )}
              <li
                className={`reorder-card-item ${i === 0 ? 'is-next' : ''} ${isBomb ? 'is-bomb' : ''} ${swapIdx === i ? 'is-swap-armed' : ''} ${swapIdx !== null && swapIdx !== i ? 'is-swap-target' : ''}`.trim()}
              >
                <span className="reorder-pos">
                  {i === 0 ? '#1 · NEXT DRAW' : `#${i + 1}`}
                </span>
                <div className="reorder-card-slot">
                  <button
                    type="button"
                    className="reorder-card-surface"
                    disabled={!connected}
                    aria-pressed={swapIdx === i}
                    title={
                      swapIdx === null
                        ? `Chọn ${cardName} để đổi chỗ`
                        : swapIdx === i
                          ? 'Bỏ chọn đổi chỗ'
                          : `Đổi chỗ với #${swapIdx + 1}`
                    }
                    onClick={() => handleCardClick(i)}
                  >
                    <CardView small card={c} catalog={catalog} />
                  </button>
                  <button
                    type="button"
                    className="reorder-zoom-btn"
                    aria-label={`Phóng to ${cardName}`}
                    title={`Phóng to ${cardName}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      onInspectCard?.(c)
                    }}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <circle cx="11" cy="11" r="7" />
                      <path d="m20 20-3.5-3.5" />
                    </svg>
                  </button>
                </div>
                <span className="reorder-name">{cardName}</span>
                <div className="reorder-arrows">
                  <button
                    type="button"
                    disabled={!connected || i === 0}
                    aria-label={`Đưa ${cardName} lên trước`}
                    onClick={() => move(i, -1)}
                  >
                    ←
                  </button>
                  <button
                    type="button"
                    disabled={!connected || i === order.length - 1}
                    aria-label={`Đưa ${cardName} ra sau`}
                    onClick={() => move(i, +1)}
                  >
                    →
                  </button>
                </div>
              </li>
            </React.Fragment>
          )
        })}
      </ol>
      <button
        type="button"
        className="primary"
        disabled={!connected}
        onClick={() => onDone(order)}
      >
        Xác nhận thứ tự
      </button>
    </div>
  )
}
