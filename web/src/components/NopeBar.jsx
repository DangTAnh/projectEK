import React from 'react'

const NOPE_SECONDS = 5 // khớp NOPE_SECONDS phía server

export default function NopeBar({ window, now, name, send, alive = true, hasNope = true }) {
  if (!window) return null
  const secs = window.ends_ms ? Math.max(0, (window.ends_ms - now) / 1000) : 0
  const isActor = window.actor === name
  return (
    <div className={`nope-bar ${secs < 2 ? 'urgent' : ''}`}>
      <span>
        {isActor
          ? 'Thẻ của bạn đang trong cửa sổ Nope…'
          : `${window.actor} vừa đánh thẻ — NOPE được không?`}
      </span>
      {window.stacked > 0 && <b> ×{window.stacked} Nope đã chồng</b>}
      <span className="timer">{secs.toFixed(1)}s</span>
      {/* người chết và actor không bấm; hết Nope thì disable thay vì gửi lệnh chắc chắn lỗi */}
      {!isActor && alive && (
        <>
          <button className="danger" disabled={!hasNope}
                  title={hasNope ? undefined : 'Bạn không có thẻ Nope'}
                  onClick={() => send({ action: 'nope' })}>🚫 Nope!</button>
          <button onClick={() => send({ action: 'pass_nope' })}>Bỏ qua</button>
        </>
      )}
      <div className="nope-progress" style={{ transform: `scaleX(${Math.min(1, secs / NOPE_SECONDS)})` }} />
    </div>
  )
}
