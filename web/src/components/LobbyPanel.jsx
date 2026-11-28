import React, { useMemo, useState } from 'react'
import RealIcon from './RealIcon.jsx'
import CatAvatar from './CatAvatar.jsx'

const FALLBACK_META = {
  original: {
    title: 'Original Classic',
    deck_type: 'Standalone',
    description: 'Bộ bài gốc cổ điển — nhanh gọn, dễ làm quen',
    theme_color: '#e65c2c',
  },
  web: {
    title: 'Web Full Expansion',
    deck_type: 'Standalone',
    description: 'Bộ mở rộng đầy đủ — nhiều lá bài & combo kịch tính',
    theme_color: '#22c55e',
  },
}

function normalizeDesk(raw) {
  const isStr = typeof raw === 'string'
  const obj = isStr ? { id: raw } : (raw || {})
  const id = String(obj.id || obj.name || '').trim()
  const fb = FALLBACK_META[id] || {}
  const rawType = String(obj.deck_type || fb.deck_type || 'Standalone').trim()
  const isExpansion = rawType.toLowerCase() === 'expansion'
  const deckType = isExpansion ? 'Expansion' : 'Standalone'
  const title = String(obj.title || fb.title || id).trim()
  const baseMerged = Boolean(obj.base_merged)
  const cardCount = Number.isFinite(Number(obj.card_count)) && obj.card_count !== null
    ? Number(obj.card_count)
    : null
  const expansionCardCount = Number.isFinite(Number(obj.expansion_card_count)) && obj.expansion_card_count !== null
    ? Number(obj.expansion_card_count)
    : null
  const description = String(obj.description || fb.description || `Bộ bài ${title}`).trim()
  const themeColor = String(obj.theme_color || fb.theme_color || '').trim()

  return {
    id,
    title,
    deck_type: deckType,
    isExpansion,
    base_merged: baseMerged,
    card_count: cardCount,
    expansion_card_count: expansionCardCount,
    description,
    theme_color: themeColor,
  }
}

export default function LobbyPanel({
  code,
  players = [],
  desks = [],
  votes = {},
  name,
  connected,
  onVoteDesk,
  onStart,
  onCopyCode,
  onCopyLink,
  onEditAvatar = null,
}) {
  const [filter, setFilter] = useState('all')
  const canStart = players.length >= 2 && connected

  const normalizedDesks = useMemo(
    () => (Array.isArray(desks) ? desks : []).map(normalizeDesk).filter((d) => d.id),
    [desks],
  )

  const counts = useMemo(() => {
    let standalone = 0
    let expansion = 0
    for (const d of normalizedDesks) {
      if (d.isExpansion) expansion += 1
      else standalone += 1
    }
    return {
      all: normalizedDesks.length,
      Standalone: standalone,
      Expansion: expansion,
    }
  }, [normalizedDesks])

  const filteredDesks = useMemo(() => {
    if (filter === 'Standalone') return normalizedDesks.filter((d) => !d.isExpansion)
    if (filter === 'Expansion') return normalizedDesks.filter((d) => d.isExpansion)
    return normalizedDesks
  }, [normalizedDesks, filter])

  const filterTabs = [
    { key: 'all', label: `Tất cả (${counts.all})` },
    { key: 'Standalone', label: `Standalone (${counts.Standalone})` },
    { key: 'Expansion', label: `Expansion (${counts.Expansion})` },
  ]

  return (
    <section className="lobby-stage" aria-label="Sảnh chờ">
      <div className="lobby-panel">
        <div className="lobby-head">
          <div className="lobby-head-main">
            <span className="lobby-eyebrow">Sảnh chờ</span>
            <div className="lobby-title-row">
              <h2>Phòng <span className="lobby-code">{code}</span></h2>
              <p>{players.length}/9 người sẵn sàng · Cần ít nhất 2 người</p>
            </div>
          </div>
          <div className="lobby-share">
            <button type="button" className="secondary-btn" onClick={onCopyCode}>Sao chép mã</button>
            <button type="button" className="secondary-btn" onClick={onCopyLink}>
              <RealIcon name="link" size={15} /> Sao chép link mời
            </button>
          </div>
        </div>

        <div className="lobby-body">
          <aside className="lobby-side">
            <div className="lobby-block lobby-players-block">
              <div className="lobby-block-head">
                <span>Người chơi</span>
                <div className="lobby-roster-head-right">
                  {onEditAvatar && (
                    <button
                      type="button"
                      className="lobby-cat-edit-btn"
                      onClick={onEditAvatar}
                    >
                      Tùy chỉnh mèo
                    </button>
                  )}
                  <span className="lobby-pill-count">{players.length} / 9</span>
                </div>
              </div>
              <div className="lobby-roster">
                {players.map((p) => {
                  const isMe = p.name === name
                  return (
                    <div
                      key={p.name}
                      className={`lobby-player ${isMe ? 'me' : ''} ${p.connected === false ? 'offline' : ''}`}
                    >
                      {isMe && onEditAvatar ? (
                        <button
                          type="button"
                          className="lobby-cat-perch editable"
                          title="Bấm để tùy chỉnh mèo"
                          aria-label="Tùy chỉnh nhân vật mèo"
                          onClick={onEditAvatar}
                        >
                          <CatAvatar avatar={p.avatar} name={p.name} size={40} />
                        </button>
                      ) : (
                        <div className="lobby-cat-perch">
                          <CatAvatar avatar={p.avatar} name={p.name} size={40} />
                        </div>
                      )}
                      <div className="lobby-player-plate">
                        <span className="lobby-player-name">{p.name}</span>
                        {isMe && <em className="me-tag">Bạn</em>}
                        {p.connected === false && (
                          <span className="offline-tag" title="Mất kết nối">
                            <span className="offline-pulse-dot" aria-hidden="true" />
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="lobby-actions">
              <button
                type="button"
                className="primary lobby-start-btn"
                disabled={!canStart}
                onClick={onStart}
              >
                {players.length < 2 ? 'Đang chờ thêm người chơi…' : 'Bắt đầu ván mới'}
              </button>
            </div>
          </aside>

          <div className="lobby-block lobby-desks-col">
            <div className="lobby-block-head desk-block-head">
              <div className="desk-head-title">
                <span>Chọn bộ bài</span>
                <span className="desk-hint">Bỏ trống để chọn ngẫu nhiên</span>
              </div>
              <div className="desk-filter-tabs" role="tablist" aria-label="Lọc loại bộ bài">
                {filterTabs.map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    role="tab"
                    aria-selected={filter === tab.key}
                    className={`desk-filter-tab ${filter === tab.key ? 'active' : ''}`}
                    onClick={() => setFilter(tab.key)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="desk-votes">
              {filteredDesks.map((d) => {
                const voters = Object.entries(votes || {}).filter(([, v]) => v === d.id).map(([n]) => n)
                const mine = voters.includes(name)
                const typeLabel = d.isExpansion
                  ? (d.base_merged ? 'Expansion + Base' : 'Expansion')
                  : 'Standalone'
                const countHint = d.isExpansion && d.expansion_card_count
                  ? `${d.expansion_card_count} lá mở rộng + bộ gốc`
                  : undefined
                return (
                  <button
                    key={d.id}
                    type="button"
                    className={`desk-card ${mine ? 'mine' : ''}`}
                    style={d.theme_color ? { '--desk-accent': d.theme_color } : undefined}
                    disabled={!connected}
                    title={voters.length ? `${d.description} (Đã vote: ${voters.join(', ')})` : d.description}
                    onClick={() => onVoteDesk(d.id)}
                  >
                    <div className="desk-card-top">
                      <span className="desk-card-name">{d.title}</span>
                      {voters.length > 0 && <span className="desk-vote-badge">{voters.length}</span>}
                    </div>
                    <div className="desk-card-meta">
                      <span className={`desk-type-badge ${d.isExpansion ? 'expansion' : 'standalone'}`}>
                        {typeLabel}
                      </span>
                      {d.card_count !== null && (
                        <span className="desk-count-badge" title={countHint}>
                          {d.card_count} lá
                        </span>
                      )}
                    </div>
                    <span className="desk-card-desc">
                      {d.description}
                    </span>
                  </button>
                )
              })}
              {normalizedDesks.length === 0 && <span className="desk-hint">Đang tải danh sách bộ bài…</span>}
              {normalizedDesks.length > 0 && filteredDesks.length === 0 && (
                <span className="desk-hint">Không có bộ bài nào trong mục này.</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
