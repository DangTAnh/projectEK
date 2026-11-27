import React, { useEffect, useRef, useState } from 'react'
import CardView from './CardView.jsx'
import RealIcon from './RealIcon.jsx'
import { getCardName } from '../utils/cardCatalog.js'

const NOPE_SECONDS = 2 // khớp NOPE_SECONDS phía server

export default function NopeBar({
  window: win,
  name,
  send,
  alive = true,
  hasNope = true,
  isBlind = false,
  errorNonce = 0,
  connected = true,
  catalog = null,
  onInspectCard = null,
}) {
  const windowKey = win
    ? `${win.actor}:${win.card?.id || win.card?.type || ''}:${win.stacked ?? 0}:${win.ends_ms ?? ''}:${win.as_type || ''}`
    : ''

  const anchorRef = useRef({ key: '', startLocal: 0, initialMs: NOPE_SECONDS * 1000 })
  const [remainingMs, setRemainingMs] = useState(NOPE_SECONDS * 1000)
  const [submittedKey, setSubmittedKey] = useState('')

  // Khi server trả lỗi (vd bị mù bấm Nope nhưng không có lá Nope), mở khoá lại nút ngay
  useEffect(() => {
    if (errorNonce > 0) setSubmittedKey('')
  }, [errorNonce])

  // đồng bộ mốc thời gian khi cửa sổ Nope mở/cập nhật — tránh lệch đồng hồ client/server
  useEffect(() => {
    if (!win) {
      anchorRef.current = { key: '', startLocal: 0, initialMs: 0 }
      setRemainingMs(0)
      setSubmittedKey('')
      return undefined
    }
    const nowLocal = Date.now()
    let initialMs = NOPE_SECONDS * 1000
    if (typeof win.remaining_ms === 'number' && Number.isFinite(win.remaining_ms)) {
      initialMs = Math.max(0, win.remaining_ms)
    } else if (typeof win.server_now_ms === 'number' && typeof win.ends_ms === 'number') {
      initialMs = Math.max(0, win.ends_ms - win.server_now_ms)
    } else if (typeof win.ends_ms === 'number') {
      initialMs = Math.max(0, win.ends_ms - nowLocal)
    }
    anchorRef.current = { key: windowKey, startLocal: nowLocal, initialMs }
    setRemainingMs(initialMs)

    const t = setInterval(() => {
      const elapsed = Date.now() - anchorRef.current.startLocal
      setRemainingMs(Math.max(0, anchorRef.current.initialMs - elapsed))
    }, 100)
    return () => clearInterval(t)
  }, [windowKey, win])

  if (!win) return null

  const secs = remainingMs / 1000
  const isActor = win.actor === name
  const stacked = win.stacked ?? 0
  // Khi đã có người Nope (stacked > 0), chính actor cũng có thể phản-Nope (Yup) hoặc Bỏ qua
  const canAct = alive && (!isActor || stacked > 0)
  const responded = !!win.you_responded || submittedKey === windowKey
  const cardName = win.card ? getCardName(catalog, win.card.type) : 'thẻ'
  const asName = win.as_type ? getCardName(catalog, win.as_type) : ''
  const isCancelled = stacked % 2 === 1

  function handleNope() {
    if (!connected || !canAct || responded || !hasNope) return
    // Nếu đang bị mù, không khoá nút lạc quan trước khi server xác nhận thực sự có thẻ Nope
    if (!isBlind) setSubmittedKey(windowKey)
    send({ action: 'nope' })
  }

  function handlePass() {
    if (!connected || !canAct || responded) return
    setSubmittedKey(windowKey)
    send({ action: 'pass_nope' })
  }

  const actorStatusText = stacked === 0
    ? ' — chờ cửa sổ Nope…'
    : isCancelled
      ? ' — bị Nope, phản công (Yup)?'
      : ' — đã Yup lại, chờ cửa sổ Nope…'

  return (
    <div
      className={`nope-bar ${secs < 1 ? 'urgent' : ''}`}
      role="region"
      aria-live="polite"
      aria-label="Cửa sổ Nope"
    >
      {win.card && (
        <button
          type="button"
          className="nope-card-thumb"
          title={`Xem chi tiết ${cardName}`}
          onClick={() => onInspectCard?.(win.card)}
        >
          <CardView mini card={win.card} catalog={catalog} />
        </button>
      )}
      <div className="nope-info">
        <div className="nope-eyebrow">NOPE WINDOW</div>
        <div className="nope-headline">
          {isActor
            ? <>Bạn vừa đánh <b>{cardName}</b>{asName ? <> → <b>{asName}</b></> : ''}{actorStatusText}</>
            : <><b>{win.actor}</b> vừa đánh <b>{cardName}</b>{asName ? <> → <b>{asName}</b></> : ''}</>}
        </div>
        <div className="nope-meta">
          {stacked > 0 && (
            <>
              <span className="nope-stack-count">×{stacked} Nope</span>
              <span className={`nope-status ${isCancelled ? 'blocked' : 'active'}`}>
                {isCancelled
                  ? <><RealIcon name="nope" size={14} /> Đang bị CHẶN</>
                  : '✓ Đang có HIỆU LỰC'}
              </span>
            </>
          )}
          {canAct && responded && (
            <span className="nope-done-pill">✓ Đã phản hồi</span>
          )}
        </div>
      </div>

      <span className="timer" aria-label={`Còn ${secs.toFixed(1)} giây`}>{secs.toFixed(1)}s</span>

      {canAct && (
        <div className="nope-actions">
          <button
            type="button"
            className="danger"
            disabled={!connected || !hasNope || responded}
            title={!connected ? 'Đang mất kết nối' : responded ? 'Bạn đã phản hồi' : hasNope ? 'Phím tắt: N' : 'Bạn không có thẻ Nope'}
            onClick={handleNope}
          >
            {isCancelled
              ? <><RealIcon name="nope" size={16} /> Yup! (Nope)</>
              : <><RealIcon name="nope" size={16} /> Nope!</>} <kbd>N</kbd>
          </button>
          <button
            type="button"
            disabled={!connected || responded}
            title={responded ? 'Bạn đã phản hồi' : 'Phím tắt: P'}
            onClick={handlePass}
          >
            Bỏ qua <kbd>P</kbd>
          </button>
        </div>
      )}

      <div
        className="nope-progress"
        style={{ transform: `scaleX(${Math.min(1, Math.max(0, secs / NOPE_SECONDS))})` }}
      />
    </div>
  )
}
