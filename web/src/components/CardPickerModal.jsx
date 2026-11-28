import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import CardView from './CardView.jsx'
import RealIcon from './RealIcon.jsx'
import { TURN_ENDING_TYPES, getCategoryLabel } from '../utils/cardCatalog.js'

function normalizeText(s) {
  return (s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

export default function CardPickerModal({
  mode = 'godcat',
  excludeTurnEnding = false,
  catalog = {},
  title,
  iconName = '',
  subtitle = '',
  onSelect,
  onClose = null,
  disabled = false,
  inline = false,
}) {
  const [query, setQuery] = useState('')
  const [activeCat, setActiveCat] = useState('all')
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const candidates = useMemo(() => {
    const all = Object.values(catalog || {})
    return all
      .filter((c) => {
        if (mode === 'godcat') {
          if (c.godcat_banned) return false
          if (excludeTurnEnding && TURN_ENDING_TYPES.has(c.type)) return false
          return c.is_action || c.type === 'defuse'
        }
        return true
      })
      .sort((a, b) => (a.name || a.type).localeCompare(b.name || b.type))
  }, [catalog, mode, excludeTurnEnding])

  const categories = useMemo(() => {
    const cats = [...new Set(candidates.map((c) => c.category).filter(Boolean))]
    return cats
  }, [candidates])

  const filtered = useMemo(() => {
    const q = normalizeText(query.trim())
    return candidates.filter((c) => {
      if (activeCat !== 'all' && c.category !== activeCat) return false
      if (!q) return true
      const variantAliases = Object.values(c.variant_names || {}).join(' ')
      const hay = normalizeText(`${c.name} ${variantAliases} ${c.type} ${c.category || ''} ${c.description || ''}`)
      return hay.includes(q)
    })
  }, [candidates, query, activeCat])

  function submitBest() {
    if (disabled) return
    if (filtered.length > 0) {
      onSelect(filtered[0].type)
    } else if (query.trim()) {
      onSelect(query.trim())
    }
  }

  const content = (
    <div
      className={inline ? 'card-picker inline' : 'card-picker modal'}
      onClick={inline ? undefined : (e) => e.stopPropagation()}
      role={inline ? undefined : 'dialog'}
      aria-modal={inline ? undefined : 'true'}
      aria-label={title}
    >
      <div className="picker-head">
        <div>
          <h3 className="picker-title">
            {iconName && <RealIcon name={iconName} size={22} />}
            <span>{title}</span>
          </h3>
          {subtitle && <p className="picker-sub">{subtitle}</p>}
        </div>
        {!inline && onClose && (
          <button
            type="button"
            className="icon-close"
            aria-label="Đóng"
            onClick={onClose}
          >
            ✕
          </button>
        )}
      </div>

      <div className="input-card-row">
        <input
          ref={inputRef}
          value={query}
          aria-label="Tìm tên thẻ"
          placeholder="Tìm theo tên thẻ (vd: Attack, Skip, Defuse, Favor…)"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              submitBest()
            } else if (e.key === 'Escape' && onClose) {
              e.preventDefault()
              onClose()
            }
          }}
        />
        <button
          type="button"
          className="primary"
          disabled={disabled || (filtered.length === 0 && !query.trim())}
          onClick={submitBest}
        >
          Chọn
        </button>
      </div>

      {categories.length > 1 && (
        <div className="picker-cats" role="tablist" aria-label="Lọc theo nhóm thẻ">
          <button
            type="button"
            role="tab"
            aria-selected={activeCat === 'all'}
            className={`cat-chip ${activeCat === 'all' ? 'active' : ''}`}
            onClick={() => setActiveCat('all')}
          >
            Tất cả ({candidates.length})
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              type="button"
              role="tab"
              aria-selected={activeCat === cat}
              className={`cat-chip ${activeCat === cat ? 'active' : ''}`}
              onClick={() => setActiveCat(cat)}
            >
              {getCategoryLabel(cat)}
            </button>
          ))}
        </div>
      )}

      <div className="picker-grid" role="listbox" aria-label="Danh sách thẻ">
        {filtered.map((c) => (
          <button
            key={c.type}
            type="button"
            className="picker-item"
            disabled={disabled}
            title={c.description || c.name}
            onClick={() => onSelect(c.type)}
          >
            <CardView mini card={{ type: c.type, variant: c.variants?.[0] ?? 0 }} catalog={catalog} />
            <span className="picker-name">{c.name}</span>
          </button>
        ))}
        {filtered.length === 0 && (
          <p className="picker-empty">
            Không thấy thẻ khớp “{query}” — bấm Chọn để gửi tìm kiếm gần đúng.
          </p>
        )}
      </div>
    </div>
  )

  if (inline) return content

  return createPortal(
    <div className="zoom-overlay picker-overlay" onClick={onClose}>
      {content}
    </div>,
    document.body,
  )
}
