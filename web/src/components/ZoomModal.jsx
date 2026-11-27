import React from 'react'
import { createPortal } from 'react-dom'
import CardView from './CardView.jsx'
import RealIcon from './RealIcon.jsx'
import { getCardMeta, getCategoryLabel } from '../utils/cardCatalog.js'

export default function ZoomModal({ card, catalog, onClose }) {
  if (!card) return null
  const meta = getCardMeta(catalog, card.type)
  const catLabel = getCategoryLabel(meta?.category)

  return createPortal(
    <div
      className="zoom-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={`Chi tiết thẻ ${meta?.name || card.type}`}
      onClick={onClose}
    >
      <div className="zoom-dialog" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          className="icon-close zoom-close"
          aria-label="Đóng xem chi tiết"
          onClick={onClose}
        >
          ✕
        </button>
        <figure className="zoom-card">
          <CardView card={card} catalog={catalog} />
        </figure>
        <div className="zoom-meta">
          <div className="zoom-meta-top">
            <span className="zoom-eyebrow">Chi tiết lá bài</span>
            <h3>{meta?.name || card.type}</h3>
            <div className="zoom-tags">
              {catLabel && <span className="zoom-tag cat">{catLabel}</span>}
              {meta?.anytime && (
                <span className="zoom-tag anytime">
                  <RealIcon name="turn" size={13} /> Bất cứ lúc nào
                </span>
              )}
              {meta?.nopeable === false
                ? (
                  <span className="zoom-tag unnopeable">
                    <RealIcon name="defuse" size={13} /> Không thể bị Nope
                  </span>
                )
                : (
                  <span className="zoom-tag nopeable">
                    <RealIcon name="nope" size={13} /> Có thể bị Nope
                  </span>
                )}
              {meta?.combo_only && (
                <span className="zoom-tag">
                  <RealIcon name="sort" size={13} /> Đánh theo combo
                </span>
              )}
              {meta?.godcat_banned && <span className="zoom-tag muted">Godcat không sao chép</span>}
            </div>
            <div className="zoom-desc-wrap">
              <span className="zoom-desc-label">Tác dụng</span>
              <div className="zoom-desc">
                {meta?.description
                  ? meta.description
                  : 'Chưa có mô tả chi tiết cho lá bài này.'}
              </div>
            </div>
          </div>
          <p className="zoom-hint">Bấm ra ngoài hoặc nhấn <kbd>Esc</kbd> để đóng</p>
        </div>
      </div>
    </div>,
    document.body,
  )
}
