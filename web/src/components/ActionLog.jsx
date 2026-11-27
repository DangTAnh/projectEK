import React, { useMemo, useState } from 'react'
import RealIcon from './RealIcon.jsx'

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function logClass(line) {
  if (/BOOM|nổ|tung|💥|💣/i.test(line)) return 'log-boom'
  if (/thắng|THẮNG|🏆|vô địch|🎉/i.test(line)) return 'log-win'
  if (/chết|💀|bị loại|loại khỏi/i.test(line)) return 'log-dead'
  if (/trộm|đánh cắp|🕵️|ăn trộm|giật mất|bẫy/i.test(line)) return 'log-steal'
  if (/Nope|nope|🚫|❌/i.test(line)) return 'log-nope'
  if (/defuse|Defuse|✂️|hồi sinh/i.test(line)) return 'log-defuse'
  return ''
}

function logIconName(line) {
  if (/BOOM|nổ|tung|imploding|exploding|catomic|armageddon|💥|💣|☄️/i.test(line)) return 'bomb'
  if (/thắng|THẮNG|vô địch|🏆|🎉/i.test(line)) return 'trophy'
  if (/chết|bị loại|loại khỏi|💀|☠️/i.test(line)) return 'skull'
  if (/nope|yup|chặn|hủy|🚫|❌/i.test(line)) return 'nope'
  if (/defuse|gỡ bom|hồi sinh|zombie|✂️|🧟/i.test(line)) return 'defuse'
  if (/mù|curse|cat butt|🙈/i.test(line)) return 'blind'
  if (/mark|đánh dấu|📌/i.test(line)) return 'pin'
  if (/nhìn|peek|future|clairvoyance|tiên tri|👀|🔮|👁️/i.test(line)) return 'peek'
  if (/trộm|đánh cắp|ăn trộm|giật mất|bẫy|illtakethat|take that|favor|🕵️|🫳|🎁/i.test(line)) return 'trap'
  if (/barking|🐶/i.test(line)) return 'dog'
  if (/tower|vương miện|👑/i.test(line)) return 'crown'
  if (/attack|tấn công|⚔️|🥊/i.test(line)) return 'swords'
  return 'sort'
}

const LEADING_EMOJI_RE = /^(?:[\p{Extended_Pictographic}\p{Emoji_Presentation}\uFE0F\u200D]+)\s*/u

function stripLeadingEmojis(line) {
  let out = String(line || '').trimStart()
  while (LEADING_EMOJI_RE.test(out)) {
    out = out.replace(LEADING_EMOJI_RE, '')
  }
  return out
}

export default function ActionLog({
  logEntries = null,
  legacyLog = [],
  playerNames = [],
  catalog = {},
  mobileOpen = false,
  onCloseMobile = null,
  onHide = null,
}) {
  const [filter, setFilter] = useState('all') // 'all' | 'important'

  const entries = useMemo(() => {
    if (Array.isArray(logEntries) && logEntries.length > 0) {
      return logEntries.map((e, i, arr) => ({
        key: `seq-${e.seq ?? i}`,
        text: String(e.text ?? ''),
        isLatest: i === arr.length - 1,
      }))
    }
    const list = legacyLog || []
    return list.map((text, i, arr) => ({
      key: `lg-${i}-${text}`,
      text: String(text ?? ''),
      isLatest: i === arr.length - 1,
    }))
  }, [logEntries, legacyLog])

  const cardNames = useMemo(() => {
    const set = new Set()
    for (const c of Object.values(catalog || {})) {
      if (c?.name) set.add(c.name)
    }
    return [...set].sort((a, b) => b.length - a.length)
  }, [catalog])

  const cardNameSet = useMemo(() => new Set(cardNames), [cardNames])

  // Unicode-safe boundary cho tên tiếng Việt có dấu (Hùng, Đức, Thảo...)
  const { namesRe, cardsRe } = useMemo(() => {
    const safeNames = [...new Set((playerNames || []).filter((n) => n && n.length > 1 && /\S/.test(n)))]
      .sort((a, b) => b.length - a.length)
    let nRe = null
    if (safeNames.length) {
      const joined = safeNames.map(escapeRegex).join('|')
      try {
        nRe = new RegExp(`(?<![\\p{L}\\p{N}_])(${joined})(?![\\p{L}\\p{N}_])`, 'gu')
      } catch {
        nRe = new RegExp(`(${joined})`, 'g')
      }
    }
    const cRe = cardNames.length
      ? new RegExp(`(${cardNames.map(escapeRegex).join('|')})`, 'g')
      : null
    return { namesRe: nRe, cardsRe: cRe }
  }, [playerNames, cardNames])

  function highlightLine(text) {
    const segments = []
    if (!namesRe) {
      segments.push({ t: text, isPlayer: false })
    } else {
      namesRe.lastIndex = 0
      let last = 0
      let m
      while ((m = namesRe.exec(text))) {
        if (m.index > last) segments.push({ t: text.slice(last, m.index), isPlayer: false })
        segments.push({ t: m[0], isPlayer: true })
        last = m.index + m[0].length
      }
      if (last < text.length) segments.push({ t: text.slice(last), isPlayer: false })
    }

    return segments.flatMap((seg, si) => {
      if (seg.isPlayer) return <span key={`p${si}`} className="lg-player">{seg.t}</span>
      if (!cardsRe) return <span key={`s${si}`}>{seg.t}</span>
      return seg.t.split(cardsRe).map((chunk, ci) => {
        if (chunk === '') return null
        if (cardNameSet.has(chunk)) return <span key={`c${si}-${ci}`} className="lg-card">{chunk}</span>
        return <span key={`s${si}-${ci}`}>{chunk}</span>
      })
    })
  }

  const displayed = useMemo(() => {
    const rev = entries.slice().reverse()
    if (filter === 'important') {
      return rev.filter((e) => logClass(e.text) !== '')
    }
    return rev
  }, [entries, filter])

  return (
    <aside className={`log-box ${mobileOpen ? 'mobile-open' : ''}`} aria-label="Nhật ký ván đấu">
      <div className="log-header">
        <span className="log-title">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="8" y1="6" x2="21" y2="6" />
            <line x1="8" y1="12" x2="21" y2="12" />
            <line x1="8" y1="18" x2="21" y2="18" />
            <line x1="3" y1="6" x2="3.01" y2="6" />
            <line x1="3" y1="12" x2="3.01" y2="12" />
            <line x1="3" y1="18" x2="3.01" y2="18" />
          </svg>
          Nhật ký <span className="log-count">{entries.length}</span>
        </span>
        <div className="log-summary-tools" role="tablist" aria-label="Lọc nhật ký">
          <button
            type="button"
            role="tab"
            aria-selected={filter === 'all'}
            className={`log-filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            Tất cả
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={filter === 'important'}
            className={`log-filter-btn ${filter === 'important' ? 'active' : ''}`}
            onClick={() => setFilter('important')}
          >
            Nổi bật
          </button>
          {mobileOpen && onCloseMobile ? (
            <button
              type="button"
              className="log-filter-btn mobile-only-btn"
              aria-label="Đóng nhật ký"
              onClick={onCloseMobile}
            >
              ✕
            </button>
          ) : onHide && (
            <button
              type="button"
              className="log-filter-btn log-hide-btn"
              aria-label="Ẩn nhật ký"
              title="Ẩn nhật ký"
              onClick={onHide}
            >
              ✕
            </button>
          )}
        </div>
      </div>
      <ul>
        {displayed.map((entry) => {
          const cls = logClass(entry.text)
          const iconName = logIconName(entry.text)
          const rest = stripLeadingEmojis(entry.text)
          return (
            <li key={entry.key} className={`log-entry ${cls} ${entry.isLatest ? 'latest' : ''}`.trim()}>
              <span className="log-icon" aria-hidden="true">
                <RealIcon name={iconName} size={16} />
              </span>
              <span className="log-text">{highlightLine(rest)}</span>
            </li>
          )
        })}
        {displayed.length === 0 && (
          <li className="log-empty">
            {filter === 'important' ? 'Chưa có sự kiện nổi bật.' : 'Chưa có nhật ký.'}
          </li>
        )}
      </ul>
    </aside>
  )
}
