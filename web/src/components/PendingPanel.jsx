import React, { useEffect, useState } from 'react'
import CardView from './CardView.jsx'

const REASON_TEXT = {
  defuse: 'Chọn vị trí chèn Exploding Kitten (0 = đỉnh deck)',
  defuse_receive: 'Nhận Exploding Kitten — chọn vị trí chèn lại vào deck (0 = đỉnh)',
  zombie: 'Chèn bom lại vào deck (0 = đỉnh)',
  imploding: 'Đặt Imploding Kitten trở lại deck (0 = đỉnh)',
  godcat_defuse: 'Chèn bom lại vào deck (Godcat làm Defuse)',
  bury: 'Chọn vị trí vùi lá vừa nhặt (0 = đỉnh)',
  favor: 'Ai phải đưa thẻ?',
  steal: 'Ăn trộm thẻ của ai?',
  call_card: 'Gọi tên thẻ của ai?',
  targetattack: 'Tấn công ai (được thêm 2 lượt)?',
  mark: 'Mark ai?',
  curse: 'Curse ai?',
  illtakethat: 'Bẫy lá rút kế tiếp của ai?',
  revive: 'Hồi sinh ai?',
  barking: 'Ép Defuse-or-die: chọn nạn nhân',
  armageddon_target: 'Giao lá úp cho ai?',
}

export default function PendingPanel({ pending, mine, send }) {
  const [idx, setIdx] = useState(0)
  const promptKey = pending ? `${pending.kind}:${pending.owner}:${JSON.stringify(pending.data || {})}` : 'none'
  useEffect(() => { setIdx(0) }, [promptKey])
  if (!pending) return null
  // người khác đang quyết định: hiện banner chờ thay vì màn hình trơ (không lộ chi tiết pending)
  if (!mine) {
    return (
      <div className="pending-panel waiting">
        <h3>⏳ {pending.owner} đang quyết định…</h3>
      </div>
    )
  }
  const { kind, data } = pending
  const respond = (payload) => send({ action: 'respond', payload })
  return (
    <div className="pending-panel">
      <h3>⏳ Đến lượt quyết định của bạn</h3>

      {kind === 'pick_index' && (
        <div className="pend-row">
          <p>{REASON_TEXT[data.reason] || data.reason}</p>
          {data.card && <CardView card={data.card} small />}
          <input type="range" min={data.min} max={data.max} value={idx}
                 onChange={(e) => setIdx(+e.target.value)} />
          <b>{idx} từ đỉnh</b>
          <button onClick={() => respond({ index: idx })}>Xác nhận</button>
        </div>
      )}

      {(kind === 'yes_no') && (
        <div className="pend-row">
          <p>{data.question}</p>
          <button className="primary" onClick={() => respond({ value: true })}>Có</button>
          <button onClick={() => respond({ value: false })}>Không</button>
        </div>
      )}

      {kind === 'pick_player' && (
        <div className="pend-row">
          <p>{REASON_TEXT[data.reason] || 'Chọn người chơi'}:</p>
          {data.candidates.map((c) => (
            <button key={c} onClick={() => respond({ player: c })}>{c}</button>
          ))}
        </div>
      )}

      {kind === 'input_card' && <InputCardForm data={data} respond={respond} />}

      {kind === 'pick_card' && data.source === 'victim_hand' && (
        <div className="pend-row">
          <p>🕵️ Trộm 1 thẻ từ tay <b>{data.victim}</b> — chọn úp một lá:</p>
          <div className="steal-backs">
            {Array.from({ length: data.count }, (_, i) => (
              <button key={i} type="button" className="steal-back"
                      title="Chọn lá này"
                      onClick={() => respond({ position: i })}>
                <div className="card-back" />
              </button>
            ))}
          </div>
        </div>
      )}

      {kind === 'pick_card' && data.source === 'own_hand' && (
        <div className="handout-zone">
          <div id="handout-drop" className="handout-drop">
            <img src="/handout.png" alt="" className="handout-img" draggable={false} />
          </div>
          <p className="handout-hint">
            Kéo 1 lá từ tay bài vào bàn tay{data.give_to ? ` để đưa ${data.give_to}` : ''} (hoặc bấm chọn 1 lá rồi bấm “Đưa lá đã chọn”)
          </p>
        </div>
      )}

      {kind === 'reorder' && <ReorderForm key={promptKey} cards={data.cards} onDone={(order) => respond({ order })} />}
    </div>
  )
}

function ReorderForm({ cards, onDone }) {
  const [order, setOrder] = useState(cards.map((c) => c.id))
  function move(i, dir) {
    const j = i + dir
    if (j < 0 || j >= order.length) return
    const next = order.slice()
    ;[next[i], next[j]] = [next[j], next[i]]
    setOrder(next)
  }
  return (
    <div className="pend-row">
      <p>Sắp xếp lại các thẻ trên cùng (thứ tự sẽ rút):</p>
      <ol>
        {order.map((id, i) => {
          const c = cards.find((x) => x.id === id)
          return (
            <li key={id}>
              <span>{c.type}</span>
              <button onClick={() => move(i, -1)}>↑</button>
              <button onClick={() => move(i, +1)}>↓</button>
            </li>
          )
        })}
      </ol>
      <button className="primary" onClick={() => onDone(order)}>Xác nhận</button>
    </div>
  )
}

function InputCardForm({ data, respond }) {
  const [text, setText] = useState('')
  const submit = () => { if (text.trim()) respond({ text: text.trim() }) }
  return (
    <div className="pend-row">
      <p>🎯 Lấy thẻ nào từ tay <b>{data.victim}</b>? Nhập tên bài (gần đúng được):</p>
      <div className="input-card-row">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="vd attack2x, defuse, favor…"
          autoFocus
        />
        <button className="primary" onClick={submit}>Lấy</button>
      </div>
    </div>
  )
}
