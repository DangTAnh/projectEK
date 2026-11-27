import React, { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import CatAvatar from './CatAvatar.jsx'
import {
  ACC_OPTIONS,
  CAT_PRESETS,
  EYES_OPTIONS,
  FUR_OPTIONS,
  HAT_OPTIONS,
  MOUTH_OPTIONS,
  PATTERN_OPTIONS,
  normalizeAvatar,
  randomAvatar,
} from '../utils/catAvatar.js'
import './CatCustomizerModal.css'

const TABS = [
  { key: 'fur', label: 'Màu lông', options: FUR_OPTIONS },
  { key: 'pattern', label: 'Họa tiết', options: PATTERN_OPTIONS },
  { key: 'eyes', label: 'Mắt', options: EYES_OPTIONS },
  { key: 'mouth', label: 'Miệng', options: MOUTH_OPTIONS },
  { key: 'hat', label: 'Mũ', options: HAT_OPTIONS },
  { key: 'acc', label: 'Phụ kiện', options: ACC_OPTIONS },
]

export default function CatCustomizerModal({
  open,
  avatar,
  playerName = 'Bạn',
  onClose,
  onSave,
}) {
  const [draft, setDraft] = useState(() => normalizeAvatar(avatar, playerName))
  const [tab, setTab] = useState('fur')

  useEffect(() => {
    if (open) {
      setDraft(normalizeAvatar(avatar, playerName))
    }
  }, [open, avatar, playerName])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const activeTab = TABS.find((t) => t.key === tab) || TABS[0]

  function setTrait(key, val) {
    setDraft((prev) => ({ ...prev, [key]: val }))
  }

  return createPortal(
    <div
      className="zoom-overlay cat-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Tùy chỉnh nhân vật mèo"
      onClick={onClose}
    >
      <div className="cat-modal" onClick={(e) => e.stopPropagation()}>
        <header className="cat-modal-head">
          <div>
            <span className="cat-modal-eyebrow">EXPLODING KITTY CREATOR</span>
            <h3>Độ con mèo bựa của bạn</h3>
          </div>
          <button
            type="button"
            className="icon-close"
            aria-label="Đóng"
            onClick={onClose}
          >
            ✕
          </button>
        </header>

        <div className="cat-modal-body">
          <div className="cat-preview-col">
            <div className="cat-stage-card">
              <div className="cat-stage-seat">
                <CatAvatar avatar={draft} name={playerName} size={118} className="cat-preview-hero" />
                <div className="cat-stage-plate">
                  <span className="cat-stage-name">{playerName || 'Mèo chiến'}</span>
                  <span className="cat-stage-cards">7</span>
                </div>
              </div>
              <button
                type="button"
                className="cat-rand-btn"
                onClick={() => setDraft(randomAvatar())}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="16 3 21 3 21 8" />
                  <line x1="4" y1="20" x2="21" y2="3" />
                  <polyline points="21 16 21 21 16 21" />
                  <line x1="15" y1="15" x2="21" y2="21" />
                  <line x1="4" y1="4" x2="9" y2="9" />
                </svg>
                Ngẫu nhiên
              </button>
            </div>

            <div className="cat-presets">
              <span className="cat-presets-label">Mẫu nhanh</span>
              <div className="cat-preset-grid">
                {CAT_PRESETS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className="cat-preset-btn"
                    onClick={() => setDraft({ ...p.avatar })}
                  >
                    <CatAvatar avatar={p.avatar} size={30} />
                    <span>{p.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="cat-controls-col">
            <div className="cat-tabs" role="tablist" aria-label="Nhóm tùy chỉnh">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.key}
                  className={`cat-tab-btn ${tab === t.key ? 'active' : ''}`}
                  onClick={() => setTab(t.key)}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="cat-option-grid" role="tabpanel">
              {activeTab.options.map((opt) => {
                const selected = draft[activeTab.key] === opt.id
                const previewAvatar = { ...draft, [activeTab.key]: opt.id }
                return (
                  <button
                    key={opt.id}
                    type="button"
                    className={`cat-opt-card ${selected ? 'active' : ''}`}
                    aria-pressed={selected}
                    onClick={() => setTrait(activeTab.key, opt.id)}
                  >
                    {activeTab.key === 'fur' ? (
                      <span
                        className="cat-fur-swatch"
                        style={{ background: opt.fill, borderColor: opt.shade }}
                        aria-hidden="true"
                      />
                    ) : (
                      <CatAvatar avatar={previewAvatar} size={42} />
                    )}
                    <span className="cat-opt-label">{opt.label}</span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        <footer className="cat-modal-foot">
          <button type="button" onClick={onClose}>Hủy</button>
          <button
            type="button"
            className="primary"
            onClick={() => {
              onSave?.(draft)
              onClose?.()
            }}
          >
            Lưu nhân vật
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  )
}
