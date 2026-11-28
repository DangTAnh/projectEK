import React, { useEffect, useMemo, useState } from 'react'
import { getDeskDetail } from '../api.js'
import { getCategoryLabel } from '../utils/cardCatalog.js'
import './CustomDeskModal.css'

const MIN_NONBOMB = 10
const MAX_TOTAL = 200
const MAX_PER_TYPE = 30

const STARTER_COUNTS = {
  defuse: 6,
  skip: 4,
  attack2x: 4,
  favor: 4,
  shuffle: 4,
  seethefuture3x: 5,
  nope: 5,
  cat: 16,
}

const CAT_FILTERS = [
  { key: 'all', label: 'Tất cả' },
  { key: 'action', label: 'Hành động' },
  { key: 'future', label: 'Nhìn / Xáo' },
  { key: 'steal', label: 'Trộm' },
  { key: 'combo', label: 'Combo' },
  { key: 'rescue', label: 'Cứu & Hồi sinh' },
  { key: 'bomb', label: 'Bom' },
]

function sanitizeCounts(raw) {
  const out = {}
  if (!raw || typeof raw !== 'object') return out
  for (const [k, v] of Object.entries(raw)) {
    if (k === 'explodingkitten') continue
    const n = Number.parseInt(v, 10)
    if (Number.isFinite(n) && n > 0) {
      out[k] = Math.min(MAX_PER_TYPE, n)
    }
  }
  return out
}

export default function CustomDeskModal({
  open,
  catalog = {},
  presets = [],
  initialMode = 'new', // 'new' | 'preset' | 'edit' | 'clone'
  initialPreset = '',
  initialDesk = null,
  onClose,
  onSave,
}) {
  const [title, setTitle] = useState('')
  const [presetId, setPresetId] = useState('')
  const [counts, setCounts] = useState({})
  const [catFilter, setCatFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [loadingPreset, setLoadingPreset] = useState(false)
  const [formErr, setFormErr] = useState('')

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  useEffect(() => {
    if (!open) return
    setFormErr('')
    setCatFilter('all')
    setQuery('')

    if (initialDesk && (initialMode === 'edit' || initialMode === 'clone')) {
      setTitle(initialMode === 'clone' ? `Bản sao · ${initialDesk.title}` : initialDesk.title || '')
      setPresetId(initialDesk.preset || '')
      setCounts(sanitizeCounts(initialDesk.counts))
      return
    }

    if (initialPreset) {
      setPresetId(initialPreset)
      const pMeta = presets.find((p) => p.id === initialPreset)
      setTitle(`Custom · ${pMeta?.title || initialPreset}`.slice(0, 40))
      setLoadingPreset(true)
      getDeskDetail(initialPreset)
        .then((detail) => {
          setCounts(sanitizeCounts(detail?.counts))
        })
        .catch((err) => {
          setFormErr(err?.message || 'Không tải được dữ liệu preset')
          setCounts({})
        })
        .finally(() => setLoadingPreset(false))
      return
    }

    setPresetId('')
    setTitle('Bộ bài Custom')
    setCounts({})
  }, [open, initialMode, initialPreset, initialDesk, presets])

  const cardList = useMemo(() => {
    const orderRank = { rescue: 0, action: 1, future: 2, steal: 3, combo: 4, revive: 5, bomb: 6 }
    return Object.entries(catalog || {})
      .map(([type, meta]) => ({ type, ...(meta || {}) }))
      .filter((c) => c.type)
      .sort((a, b) => {
        if (a.type === 'explodingkitten') return 1
        if (b.type === 'explodingkitten') return -1
        const ra = orderRank[a.category] ?? 9
        const rb = orderRank[b.category] ?? 9
        if (ra !== rb) return ra - rb
        return String(a.name || a.type).localeCompare(String(b.name || b.type))
      })
  }, [catalog])

  const filteredCards = useMemo(() => {
    const q = query.trim().toLowerCase()
    return cardList.filter((c) => {
      if (catFilter !== 'all') {
        if (catFilter === 'rescue') {
          if (c.category !== 'rescue' && c.category !== 'revive') return false
        } else if (c.category !== catFilter) {
          return false
        }
      }
      if (!q) return true
      const name = String(c.name || c.type).toLowerCase()
      const desc = String(c.description || '').toLowerCase()
      return name.includes(q) || c.type.toLowerCase().includes(q) || desc.includes(q)
    })
  }, [cardList, catFilter, query])

  const stats = useMemo(() => {
    let total = 0
    let nonBomb = 0
    let types = 0
    for (const [k, raw] of Object.entries(counts)) {
      if (k === 'explodingkitten') continue
      const n = Number(raw) || 0
      if (n <= 0) continue
      total += n
      types += 1
      if (k !== 'implodingkitten') nonBomb += n
    }
    return { total, nonBomb, types }
  }, [counts])

  if (!open) return null

  async function handleSelectPreset(nextId) {
    setFormErr('')
    setPresetId(nextId)
    if (!nextId) {
      setCounts({})
      if (!title.trim() || title.startsWith('Custom ·')) setTitle('Bộ bài Custom')
      return
    }
    const pMeta = presets.find((p) => p.id === nextId)
    if (initialMode !== 'edit') {
      setTitle(`Custom · ${pMeta?.title || nextId}`.slice(0, 40))
    }
    setLoadingPreset(true)
    try {
      const detail = await getDeskDetail(nextId)
      setCounts(sanitizeCounts(detail?.counts))
    } catch (err) {
      setFormErr(err?.message || 'Không tải được dữ liệu preset')
    } finally {
      setLoadingPreset(false)
    }
  }

  function setCardCount(ctype, nextVal) {
    if (ctype === 'explodingkitten') return
    const n = Math.max(0, Math.min(MAX_PER_TYPE, Number.parseInt(nextVal, 10) || 0))
    setCounts((prev) => {
      const next = { ...prev }
      if (n <= 0) delete next[ctype]
      else next[ctype] = n
      return next
    })
    if (formErr) setFormErr('')
  }

  function handleSave(e) {
    e.preventDefault()
    const cleanTitle = title.trim()
    if (!cleanTitle) {
      setFormErr('Vui lòng nhập tên bộ bài.')
      return
    }
    if (stats.nonBomb < MIN_NONBOMB) {
      setFormErr(`Bộ bài cần tối thiểu ${MIN_NONBOMB} lá thường (hiện có ${stats.nonBomb}).`)
      return
    }
    if (stats.total > MAX_TOTAL) {
      setFormErr(`Tổng số lá không được vượt quá ${MAX_TOTAL} (hiện có ${stats.total}).`)
      return
    }
    onSave?.({
      id: initialMode === 'edit' && initialDesk?.id ? initialDesk.id : undefined,
      title: cleanTitle,
      preset: presetId || null,
      counts,
    })
  }

  const valid = title.trim().length > 0 && stats.nonBomb >= MIN_NONBOMB && stats.total <= MAX_TOTAL

  return (
    <div
      className="zoom-overlay custom-desk-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Tạo hoặc chỉnh sửa Custom Desk"
      onClick={onClose}
    >
      <form className="custom-desk-modal" onSubmit={handleSave} onClick={(e) => e.stopPropagation()}>
        <div className="custom-desk-head">
          <div>
            <span className="custom-desk-eyebrow">CUSTOM DESK BUILDER</span>
            <h3>
              {initialMode === 'edit'
                ? 'Chỉnh sửa Custom Desk'
                : presetId
                  ? 'Tạo Custom Desk từ Preset'
                  : 'Tạo Custom Desk'}
            </h3>
          </div>
          <button type="button" className="icon-btn" aria-label="Đóng" onClick={onClose}>✕</button>
        </div>

        <div className="custom-desk-controls">
          <div className="custom-desk-top-row">
            <label className="custom-desk-field">
              <span>Tên bộ bài</span>
              <input
                value={title}
                onChange={(e) => { setTitle(e.target.value); if (formErr) setFormErr('') }}
                placeholder="VD: Hỗn chiến 3x, Bộ mèo nổ nhanh…"
                maxLength={40}
                autoFocus
              />
            </label>

            <label className="custom-desk-field">
              <span>Khởi tạo từ Preset</span>
              <select
                value={presetId}
                disabled={loadingPreset}
                onChange={(e) => handleSelectPreset(e.target.value)}
              >
                <option value="">— Trống (tự chọn từ đầu) —</option>
                {presets.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title} ({p.card_count} lá)
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="custom-desk-toolbar">
            <div className="custom-desk-quick">
              <button
                type="button"
                className="secondary-btn"
                onClick={() => {
                  setCounts({ ...STARTER_COUNTS })
                  if (formErr) setFormErr('')
                }}
              >
                Cơ bản nhanh (48 lá)
              </button>
              <button
                type="button"
                className="secondary-btn"
                onClick={() => {
                  setCounts({})
                  if (formErr) setFormErr('')
                }}
              >
                Đặt lại 0
              </button>
            </div>

            <div className="custom-desk-stats">
              <span className={`custom-desk-count-pill ${stats.nonBomb < MIN_NONBOMB || stats.total > MAX_TOTAL ? 'warn' : 'ok'}`}>
                {loadingPreset ? 'Đang nạp preset…' : `Tổng: ${stats.total}/${MAX_TOTAL} lá · ${stats.types} loại`}
              </span>
            </div>
          </div>

          <div className="custom-desk-filter-row">
            <div className="custom-desk-cats" role="tablist" aria-label="Lọc nhóm thẻ">
              {CAT_FILTERS.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  role="tab"
                  aria-selected={catFilter === f.key}
                  className={`desk-filter-tab ${catFilter === f.key ? 'active' : ''}`}
                  onClick={() => setCatFilter(f.key)}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <input
              type="search"
              className="custom-desk-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tìm tên lá bài…"
              aria-label="Tìm lá bài"
            />
          </div>
        </div>

        <div className="custom-desk-grid">
          {filteredCards.map((c) => {
            const isAutoEk = c.type === 'explodingkitten'
            const cnt = counts[c.type] || 0
            return (
              <div key={c.type} className={`custom-card-row ${cnt > 0 ? 'selected' : ''} ${isAutoEk ? 'auto' : ''}`}>
                <img
                  src={c.image || `/static/cards/${c.type}/0.jpg`}
                  alt={c.name || c.type}
                  className="custom-card-thumb"
                  loading="lazy"
                />
                <div className="custom-card-info">
                  <div className="custom-card-title-row">
                    <span className="custom-card-name">{c.name || c.type}</span>
                    {c.category && (
                      <span className="custom-card-cat">{getCategoryLabel(c.category)}</span>
                    )}
                    {c.anytime && <span className="custom-card-tag">NOW</span>}
                  </div>
                  <p className="custom-card-desc" title={c.description || ''}>
                    {isAutoEk
                      ? 'Tự động chia N−1 (hoặc N nếu có Streaking) theo số người chơi.'
                      : c.type === 'cat'
                        ? 'Tự gom bộ 4 lá cùng loại mèo để ghép được combo.'
                        : c.description || c.type}
                  </p>
                </div>
                {isAutoEk ? (
                  <span className="custom-card-auto-pill">Tự động</span>
                ) : (
                  <div className="custom-card-stepper">
                    <button
                      type="button"
                      aria-label={`Giảm ${c.name || c.type}`}
                      disabled={cnt <= 0}
                      onClick={() => setCardCount(c.type, cnt - 1)}
                    >
                      −
                    </button>
                    <input
                      type="number"
                      min={0}
                      max={MAX_PER_TYPE}
                      aria-label={`Số lượng ${c.name || c.type}`}
                      value={cnt}
                      onChange={(e) => setCardCount(c.type, e.target.value)}
                    />
                    <button
                      type="button"
                      aria-label={`Tăng ${c.name || c.type}`}
                      disabled={cnt >= MAX_PER_TYPE}
                      onClick={() => setCardCount(c.type, cnt + 1)}
                    >
                      +
                    </button>
                  </div>
                )}
              </div>
            )
          })}
          {filteredCards.length === 0 && (
            <p className="custom-desk-empty">Không tìm thấy lá bài phù hợp.</p>
          )}
        </div>

        <div className="custom-desk-foot">
          <span className="custom-desk-foot-msg">
            {formErr ? (
              <span className="custom-desk-err">{formErr}</span>
            ) : (
              'Khi bắt đầu ván, hệ thống tự chèn Exploding Kitten và 1 lá cứu cho mỗi người chơi.'
            )}
          </span>
          <div className="custom-desk-foot-actions">
            <button type="button" onClick={onClose}>Hủy</button>
            <button type="submit" className="primary" disabled={!valid || loadingPreset}>
              Lưu &amp; Vote bộ bài
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
