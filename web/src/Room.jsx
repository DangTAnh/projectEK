import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { wsUrl, sessionKey, store } from './api.js'
import CardView from './components/CardView.jsx'
import PlayerList from './components/PlayerList.jsx'
import PendingPanel from './components/PendingPanel.jsx'
import NopeBar from './components/NopeBar.jsx'

const ANYTIMES = ['shufflenow', 'clairvoyance', 'alter3xnow', 'feedthedead', 'godcat']
const UNPLAYABLE = ['defuse', 'streakingkitten', 'zombiekitten', 'cat', 'feralcat',
                    'explodingkitten', 'implodingkitten']
const TERMINAL_CLOSE_CODES = new Set([4001, 4401, 4403, 4404])
const MAX_RETRIES = 20

// tên hiển thị thẻ để highlight trong nhật ký
const CARD_NAMES = [
  'Exploding Kitten', 'Imploding Kitten', 'Defuse', 'Streaking Kitten', 'Zombie Kitten',
  'Godcat', 'Devilcat', 'Barking Kitten', 'Skip', 'Super Skip', 'Shuffle', 'Shuffle NOW',
  'Attack 2x', 'Targeted Attack 2x', 'Personal Attack 3x', 'Attack of the Dead', 'Reverse',
  'Draw From the Bottom', 'Dig Deeper', 'Raising Heck', 'Bury', 'Tower of Power',
  'Catomic Bomb', 'Armageddon', 'Feral Cat', 'See the Future 3x', 'See the Future 5x',
  'Reveal the Future 3x', 'Share the Future 3x', 'Alter the Future 3x', 'Alter the Future 5x',
  'Alter the Future 3x NOW', 'Clairvoyance', 'Cat', 'Favor', 'Potluck', "I'll Take That",
  'Mark', 'Curse of the Cat Butt', 'Garbage Collection', 'Grave Robber', 'Clone',
  'Swap Top and Bottom', 'Nope', 'Feed the Dead',
]

export default function Room({ code }) {
  // tên: ưu tiên query param (?room=CODE&name=X), sau đó mới đến sessionStorage
  const [name, setName] = useState(() =>
    new URLSearchParams(location.search).get('name') || store.get('ek_name'))
  const [nameDraft, setNameDraft] = useState('')
  const [view, setView] = useState(null)
  const [error, setError] = useState('')
  const [connState, setConnState] = useState('connecting')
  const [selected, setSelected] = useState([]) // card_id đang chọn cho combo
  const [nowMs, setNowMs] = useState(Date.now())
  const [drag, setDrag] = useState(null)       // {card, x, y, over} khi đang kéo bài
  const [dealIds, setDealIds] = useState(() => new Set()) // bài vừa được phát -> animation
  const [shake, setShake] = useState(false)    // rung màn hình khi có bom lật ra
  const [zoom, setZoom] = useState(null)       // card đang phóng to (chuột phải)
  const [graveList, setGraveList] = useState(false) // overlay list thẻ đã đánh
  const [peekOpen, setPeekOpen] = useState(false)   // popup peek ẩn/hiện
  const [desks, setDesks] = useState([])       // các bộ bài có thể vote ở lobby
  const [boom, setBoom] = useState(null)       // cutscene bom nổ: tên người bị nổ
  const [deckLit, setDeckLit] = useState(false) // giữ glow deck một nhịp sau khi hết lượt
  const [godcatCard, setGodcatCard] = useState(null) // đang chơi godcat -> mở input chọn thẻ
  const [godcatNow, setGodcatNow] = useState(false) // godcat ngoài lượt (play_now)
  const seenLogRef = useRef(null)
  const wsRef = useRef(null)
  const retryRef = useRef(0)
  const tableRef = useRef(null)
  const dragStartedRef = useRef(false)
  const prevHandRef = useRef(null)
  const prevRevealedRef = useRef(null)
  const deckLitTimerRef = useRef(null)
  const connected = connState === 'open'

  const send = useCallback((obj) => {
    if (!connected || !wsRef.current || wsRef.current.readyState !== 1) {
      setError('Mất kết nối tới phòng — thao tác chưa được gửi.')
      return
    }
    wsRef.current.send(JSON.stringify(obj))
  }, [connected])

  useEffect(() => {
    if (!name) return undefined
    let closed = false
    let timer
    function terminalMessage(code) {
      if (code === 4001) return 'Phiên này đã được thay thế ở tab khác.'
      if (code === 4401) return 'Phiên không hợp lệ — hãy vào lại phòng.'
      if (code === 4403) return 'Phòng đã đầy hoặc không còn vào được.'
      if (code === 4404) return 'Phòng không tồn tại.'
      return 'Kết nối bị từ chối.'
    }
    function connect() {
      if (closed) return
      setConnState('connecting')
      const session = store.get(sessionKey(code, name))
      const ws = new WebSocket(wsUrl(code, name, session))
      wsRef.current = ws
      ws.onmessage = (ev) => {
        let msg
        try {
          msg = JSON.parse(ev.data)
        } catch {
          return // frame lạ (proxy/trang lỗi) — bỏ qua, chờ state sau
        }
        if (!msg || typeof msg !== 'object') return
        if (msg.type === 'state') {
          const token = msg.view?.you?.session
          if (token) store.set(sessionKey(code, name), token)
          // server gửi bộ đệm trượt 30 dòng theo thời gian; dò theo nội dung dòng cuối.
          const log = msg.view.log || []
          const lastSeen = seenLogRef.current
          if (lastSeen) {
            const idx = log.lastIndexOf(lastSeen)
            // reconnect mà dòng neo đã trôi khỏi cửa sổ 30 dòng: chỉ quét 3 dòng cuối, tránh phát lại cutscene cũ
            const tail = idx >= 0 ? log.slice(idx + 1) : log.slice(-3)
            const line = tail.find((l) => l.includes('BOOM'))
            if (line) {
              const who = line.match(/BOOM!\s*(.+?)\s+nổ/)?.[1] || ''
              setBoom(who)
              setTimeout(() => setBoom(null), 1400)
            }
          }
          seenLogRef.current = log[log.length - 1]
          setView(msg.view)
          setError('')
        } else if (msg.type === 'error') {
          setError(msg.message || 'Lỗi')
        }
      }
      ws.onclose = (ev) => {
        if (closed) return
        if (TERMINAL_CLOSE_CODES.has(ev.code)) {
          setConnState('rejected')
          setError(terminalMessage(ev.code))
          return
        }
        retryRef.current += 1
        if (retryRef.current > MAX_RETRIES) {
          setConnState('closed')
          setError('Không kết nối lại được — hãy tải lại trang.')
          return
        }
        setConnState('connecting')
        timer = setTimeout(connect, Math.min(1000 * retryRef.current, 5000))
      }
      ws.onopen = () => { retryRef.current = 0; setConnState('open') }
    }
    connect()
    const tick = setInterval(() => setNowMs(Date.now()), 250)
    return () => { closed = true; clearTimeout(timer); clearInterval(tick); wsRef.current?.close() }
  }, [code, name])

  const hand = view?.you?.hand

  // bài mới trên tay -> animation "phát bài"
  useEffect(() => {
    if (!hand) return undefined
    const prev = prevHandRef.current
    prevHandRef.current = new Set(hand.map((c) => c.id))
    if (!prev) return undefined // view đầu tiên — không animate
    const fresh = hand.filter((c) => !prev.has(c.id))
    if (!fresh.length) return undefined
    setDealIds(new Set(fresh.map((c) => c.id)))
    const t = setTimeout(() => setDealIds(new Set()), 700)
    return () => clearTimeout(t)
  }, [hand])

  // bom vừa lật ra -> rung màn hình
  useEffect(() => {
    const rev = view?.revealed
    const prev = prevRevealedRef.current
    prevRevealedRef.current = rev ? rev.map((c) => c.id) : null
    if (!rev || !prev) return undefined
    if (rev.some((c) => !prev.includes(c.id)
        && (c.type === 'explodingkitten' || c.type === 'implodingkitten'))) {
      setShake(true)
      const t = setTimeout(() => setShake(false), 600)
      return () => clearTimeout(t)
    }
    return undefined
  }, [view?.revealed])

  // giữ chuột phải trên lá -> phóng to đọc; Esc/click đóng. Grave list cũng đóng bằng Esc
  useEffect(() => {
    if (!zoom && !graveList && !godcatCard) return undefined
    const onKey = (e) => { if (e.key === 'Escape') { setZoom(null); setGraveList(false); setGodcatCard(null); setGodcatNow(false) } }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [zoom, graveList, godcatCard])

  // toast lỗi che tay bài: tự ẩn sau 5s khi đã có view (màn hình chờ khi chưa có view thì giữ)
  useEffect(() => {
    if (!error || !view) return undefined
    const t = setTimeout(() => setError(''), 5000)
    return () => clearTimeout(t)
  }, [error, view])

  // list bộ bài để vote ở lobby
  useEffect(() => {
    fetch('/api/desks').then((r) => r.json()).then(setDesks).catch(() => {})
  }, [])

  // Hết lượt: giữ class sáng deck thêm ~450ms để CSS có thời gian fade-out,
  // tránh deck "rơi" từ trạng thái hover/glow về bình thường ngay lập tức.
  // Hook này phải đứng trước mọi return sớm để số lượng hook ổn định mỗi render.
  const canDrawEarly = connected && !!view && view.turn?.current === name
    && view.you.alive && view.phase === 'playing' && !view.pending && !view.nope_window
  useEffect(() => {
    if (canDrawEarly) {
      clearTimeout(deckLitTimerRef.current)
      setDeckLit(true)
      return undefined
    }
    if (deckLit) {
      clearTimeout(deckLitTimerRef.current)
      deckLitTimerRef.current = setTimeout(() => setDeckLit(false), 450)
      return () => clearTimeout(deckLitTimerRef.current)
    }
    return undefined
  }, [canDrawEarly, deckLit])
  // Link phòng mở tab mới thường mất sessionStorage -> hỏi tên ngay tại đây thay vì bật về Home
  if (!name) {
    return (
      <div className="room room-join">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            const v = nameDraft.trim()
            if (!v) return
            store.set('ek_name', v)
            setName(v)
          }}
        >
          <p>Vào phòng <b>{code}</b> — bạn tên gì?</p>
          <input value={nameDraft} onChange={(e) => setNameDraft(e.target.value)} placeholder="Tên của bạn" maxLength={64} autoFocus />
          <button type="submit">Vào phòng</button>
        </form>
      </div>
    )
  }

  if (!view && !error) return <div className="room loading">Đang kết nối tới phòng {code}…</div>

  if (!view && error) {
    return (
      <div className="room loading">
        <p>{error}</p>
        <button onClick={() => { location.href = '/' }}>Về trang chủ</button>
      </div>
    )
  }

  const me = view.you
  const isMyTurn = view.turn?.current === name && me.alive && view.phase === 'playing'
  const myPending = view.pending && view.pending.owner === name
  const canDraw = connected && isMyTurn && !myPending && !view.nope_window
  const deckGlow = canDraw || deckLit
  // favor/potluck/into_deck/feedthedead: mình là người phải đưa bài — kéo lá vào bàn tay
  const givePending = !!myPending && view.pending.kind === 'pick_card'
                      && view.pending.data.source === 'own_hand'

  function toggleSelect(id) {
    setSelected((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]))
  }

  function selectedCards() {
    return (me.hand || []).filter((c) => selected.includes(c.id))
  }

  function playOne(card) {
    if (!connected) {
      setError('Mất kết nối tới phòng — thao tác chưa được gửi.')
      return
    }
    if (card.type === 'godcat') {
      // Ngoài lượt thì Godcat dùng play_now kèm as_type; trên lượt dùng play thường.
      setGodcatNow(!canPlay(card))
      setGodcatCard(card) // mở popup nhập thẻ (fuzzy) thay vì prompt()
      return
    }
    if (canPlay(card)) send({ action: 'play', card_id: card.id })
    else send({ action: 'play_now', card_id: card.id })
    setSelected([])
  }

  function tryPlaySelected() {
    const cards = selectedCards()
    if (!cards.length) return
    if (!connected) {
      setError('Mất kết nối tới phòng — thao tác chưa được gửi.')
      return
    }
    if (cards.length > 3) {
      setError('Combo chỉ hỗ trợ tối đa 3 lá — hãy bỏ bớt rồi thử lại.')
      return
    }
    // combo pair/three: lá phải CÙNG loại (feralcat chỉ thay thế lá Cat)
    if (cards.length >= 2) {
      const core = cards.map((c) => c.type).filter((t) => t !== 'feralcat')
      const same = new Set(core).size <= 1
      const noNope = cards.every((c) => c.type !== 'nope')
      const feralOk = !cards.some((c) => c.type === 'feralcat') || core.length === 0 || core[0] === 'cat'
      if (cards.length === 2 || cards.length === 3) {
        if (same && noNope && feralOk) {
          send({
            action: 'combo',
            combo: cards.length === 2 ? 'pair' : 'three',
            card_ids: cards.map((c) => c.id),
          })
          setSelected([])
          return
        }
        // chọn 2/3 lá khác loại: không phải combo hợp lệ — đừng âm thầm đánh lá đầu
        setError('Combo cần các lá cùng loại (Feral Cat chỉ thay thế lá Cat).')
        return
      }
    }
    // đánh lẻ 1 lá không chơi trực tiếp được: chặn ở client thay vì gửi play_now sai rồi nhận lỗi
    if (cards.length === 1 && (cards[0].type === 'nope' || UNPLAYABLE.includes(cards[0].type))) {
      setError('Lá này không đánh lẻ được — Nope chỉ dùng trong cửa sổ Nope, mèo đánh theo combo, bom/giải không đánh trực tiếp.')
      return
    }
    playOne(cards[0])
  }

  function canPlay(card) {
    return connected && isMyTurn && !myPending && !view.nope_window && !UNPLAYABLE.includes(card.type)
  }

  function canDrag(card) {
    if (drag || !connected) return false
    if (givePending) return me.alive  // đưa bài: lá nào cũng kéo được (kể cả defuse)
    return canPlay(card)
      || (me.alive && ANYTIMES.includes(card.type) && !view.nope_window && !view.pending)
  }

  // kéo bài bằng pointer: giữ >7px mới tính là kéo (click đơn vẫn dùng để chọn)
  function startDrag(e, card) {
    if (e.button !== 0 || !canDrag(card)) return
    const giveMode = !!givePending
    const sx = e.clientX
    const sy = e.clientY
    let started = false
    let overTable = false
    let overHo = false
    const move = (ev) => {
      if (!started) {
        if (Math.hypot(ev.clientX - sx, ev.clientY - sy) < 7) return
        started = true
        dragStartedRef.current = true
      }
      const r = tableRef.current?.getBoundingClientRect()
      overTable = !!r && ev.clientX >= r.left && ev.clientX <= r.right
                  && ev.clientY >= r.top && ev.clientY <= r.bottom
      const ho = giveMode ? document.getElementById('handout-drop') : null
      const hr = ho?.getBoundingClientRect()
      overHo = !!hr && ev.clientX >= hr.left && ev.clientX <= hr.right
               && ev.clientY >= hr.top && ev.clientY <= hr.bottom
      // give mode: drop-zone nằm trong pending-panel giữa bàn — kéo vào đó cũng glow bàn
      setDrag({ card, x: ev.clientX, y: ev.clientY, over: overTable || overHo, overHo })
    }
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      if (!started) return
      if (giveMode) {
        if (overHo) send({ action: 'respond', payload: { card_id: card.id } })
      } else if (overTable) {
        playOne(card)
      }
      setDrag(null)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  const cards = selectedCards()

  // nghiêng 3D theo con trỏ khi rê lên lá trên tay
  function tilt(e) {
    const el = e.currentTarget.querySelector('.card')
    if (!el) return
    const r = e.currentTarget.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width - 0.5
    const py = (e.clientY - r.top) / r.height - 0.5
    el.style.transform = `perspective(700px) rotateY(${px * 26}deg) rotateX(${-py * 18}deg) translateY(-8px) scale(1.04)`
  }
  function untilt(e) {
    const el = e.currentTarget.querySelector('.card')
    if (el) el.style.transform = ''
  }

  // tô màu keyword cho dòng nhật ký + tách icon emoji đầu dòng
  function logClass(line) {
    if (/BOOM|nổ|tung|💥|💣/.test(line)) return 'log-boom'
    if (/thắng|THẮNG|🏆|vô địch/.test(line)) return 'log-win'
    if (/chết|💀|bị loại|loại khỏi/.test(line)) return 'log-dead'
    if (/trộm|đánh cắp|🕵️|ăn trộm/.test(line)) return 'log-steal'
    if (/Nope|nope|🚫/.test(line)) return 'log-nope'
    if (/defuse|✂️/.test(line)) return 'log-defuse'
    return ''
  }
  function logParts(line) {
    const m = line.match(/^(\p{Emoji_Presentation}|\p{Emoji}️?|[🃏💥💣✂️🐈🐱🎁🍲⚔️🕵️👀💀🏆🚫📌♻️🔁])/u)
    const icon = m ? m[0] : ''
    const rest = m ? line.slice(m[0].length) : line
    return { icon, rest }
  }

  // highlight tên người chơi + tên thẻ trong dòng log
  function highlightLog(text, playerNames) {
    const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    // tên người chơi: chỉ khớp từ riêng lẻ (word boundary); bỏ tên 1 ký tự (quá mơ hồ)
    const safeNames = [...new Set(playerNames.filter((n) => n.length > 1 && /\S/.test(n)))]
      .sort((a, b) => b.length - a.length)
    const namesRe = safeNames.length
      ? new RegExp(`\\b(${safeNames.map(esc).join('|')})\\b`, 'g')
      : null
    const cards = [...CARD_NAMES].sort((a, b) => b.length - a.length)
    const cardsRe = new RegExp(`(${cards.map(esc).join('|')})`, 'g')

    // pass 1: đánh dấu tên người chơi trước
    const playerSet = new Set(safeNames)
    const findPlayer = (seg) => {
      const out = []
      let last = 0
      if (!namesRe) return [{ t: seg, p: false }]
      namesRe.lastIndex = 0
      let m
      while ((m = namesRe.exec(seg))) {
        if (m.index > last) out.push({ t: seg.slice(last, m.index), p: false })
        out.push({ t: m[0], p: true })
        last = m.index + m[0].length
      }
      if (last < seg.length) out.push({ t: seg.slice(last), p: false })
      return out
    }

    return findPlayer(text).flatMap((seg, si) => {
      if (seg.p) return <span key={`p${si}`} className="lg-player">{seg.t}</span>
      // pass 2: trong phần text còn lại, tô tên thẻ
      return seg.t.split(cardsRe).map((chunk, ci) => {
        if (chunk === '') return null
        if (CARD_NAMES.includes(chunk)) return <span key={`c${si}-${ci}`} className="lg-card">{chunk}</span>
        return <span key={`s${si}-${ci}`}>{chunk}</span>
      })
    })
  }

  const playerNames = (view?.players || []).map((p) => p.name)

  return (
    <div className={`room ${shake ? 'shake' : ''}`}>
      <header className="topbar">
        <span className="code-badge">{code}</span>
        <PlayerList players={view.players} turn={view.turn} phase={view.phase} />
        <span className="meta-info">Deck: {view.deck_count} · Vương miện: {view.stash_count ?? 0}</span>
        <span className="meta-info">
          {connected ? '● Đã kết nối' : connState === 'rejected' || connState === 'closed' ? '⛔ Mất kết nối' : '… Đang kết nối lại'}
        </span>
        <button className="leave" onClick={() => { location.href = '/' }}>Rời phòng</button>
      </header>

      {view.phase === 'lobby' && (
        <div className="lobby-panel">
          <p>{view.players.length}/9 người trong phòng — cần ít nhất 2 người.</p>
          <div className="desk-votes">
            <span>Chọn bộ bài:</span>
            {desks.map((d) => {
              const voters = Object.entries(view.votes || {}).filter(([, v]) => v === d)
              const mine = voters.some(([n]) => n === name)
              return (
                <button key={d} className={`desk-chip ${mine ? 'mine' : ''}`} disabled={!connected}
                        onClick={() => send({ action: 'vote_desk', desk: d })}>
                  {d}{voters.length ? ` · ${voters.length}` : ''}
                </button>
              )
            })}
          </div>
          <p className="desk-hint">Không ai chọn thì random lúc bắt đầu. Được vote nhiều nhất thắng.</p>
          <button className="primary" disabled={view.players.length < 2 || !connected}
                  onClick={() => send({ action: 'start' })}>Bắt đầu ván mới</button>
        </div>
      )}

      {view.phase === 'ended' && (
        <div className="winner-banner">🏆 {view.winner || 'Không ai'} THẮNG!</div>
      )}

      <NopeBar window={view.nope_window} now={nowMs} name={name} send={send}
               alive={me.alive} hasNope={me.blind || (me.hand || []).some((c) => c.type === 'nope')} />

      <div className="main-cols">
      <div ref={tableRef}
           className={`table ${isMyTurn ? 'my-turn' : ''} ${drag ? (drag.over ? 'drag-over' : 'drag-hint') : ''}`}>
        {(view.playmat || []).length > 0 && (
          <div className="playmat-corner">
            {(view.playmat || []).map((e) => (
              <div key={e.card.id} className={`fx-${e.card.type}`}>
                <CardView small card={e.card} label={e.name !== '-' ? e.name : ''} />
              </div>
            ))}
          </div>
        )}
        <div className="table-top">
          <div className="pile-col">
            <div className={`pile deck ${deckGlow ? 'can-draw' : ''}`}
                 title={canDraw ? 'Bấm để rút thẻ' : `Deck còn ${view.deck_count}`}
                 onClick={() => canDraw && send({ action: 'draw' })}>
              {view.deck_top
                ? <CardView small card={view.deck_top} />
                : <div className="card-back" />}
              <span>{view.deck_count}</span>
            </div>
            <div className="pile-label">Deck — bấm để rút</div>
          </div>

          {/* giữa bàn: chỗ thả bài trùng với đống bỏ — lá đánh rơi vào đống scatter */}
          <div className={`midfield ${view.grave?.length ? 'clickable' : ''}`}
               title={view.grave?.length ? 'Bấm để xem các thẻ đã đánh' : ''}
               onClick={() => view.grave?.length && setGraveList(true)}>
            {(view.grave_top || []).map((c, i) => {
              // đống bài rải tự nhiên: góc/vị trí băm từ id lá — ổn định theo lá,
              // lá mới rơi xuống trên cùng mà các lá cũ không nhảy vị trí
              // grave_top[0] = lá mới nhất -> zIndex cao nhất
              const h = [...String(c.id)].reduce((a, ch) => a + ch.charCodeAt(0) * 7, 7)
              const r = (h % 41) - 20
              const dx = ((h >> 2) % 181) - 90   // rải ngang ±90px
              const dy = ((h >> 3) % 49) - 24    // rải dọc ±24px
              return (
                <div key={c.id} className={`grave-card fx-${c.type}`}
                     style={{ transform: `rotate(${r}deg) translate(${dx}px, ${dy}px)`,
                              zIndex: (view.grave_top.length - i) }}>
                  <CardView small card={c} />
                </div>
              )
            })}
            {!(view.grave_top || []).length && !(view.playmat || []).length && (
              <div className="playmat-empty">Kéo bài từ tay ra đây để đánh</div>
            )}
          </div>
        </div>

        {view.revealed?.length > 0 && (
          <div className="revealed-row">
            <span>Lật công khai:</span>
            {view.revealed.map((c) => <CardView key={c.id} card={c} />)}
          </div>
        )}
        {me.bomb_positions?.length > 0 && (
          <div className="bomb-info">💣 Vị trí bom từ đỉnh deck: {me.bomb_positions.join(', ')}</div>
        )}
        {me.illtake_by && (
          <div className="bomb-info">⚠️ Lá rút kế tiếp của bạn thuộc về {me.illtake_by}!</div>
        )}
      </div>

      {/* cột phải: nhật ký + công cụ (peek) */}
      <div className="side-col">
        <details className="log-box" open>
          <summary>Nhật ký ván đấu</summary>
          <ul>{(view.log || []).slice().reverse().map((l, i, arr) => {
            const cls = logClass(l)
            const { icon, rest } = logParts(l)
            return (
              <li key={arr.length - 1 - i} className={cls}>
                {icon && <span className="log-icon">{icon}</span>}
                <span className="log-text">{highlightLog(rest, playerNames)}</span>
              </li>
            )
          })}</ul>
        </details>
        {me.peek?.length > 0 && (
          <div className={`peek-widget ${peekOpen ? 'open' : ''}`}>
            <button type="button" className="peek-toggle"
                    title={peekOpen ? 'Ẩn' : 'Xem thẻ đã nhìn trộm'}
                    onClick={() => setPeekOpen((o) => !o)}>
              👀 {me.peek.length}
            </button>
            {peekOpen && (
              <div className="peek-popup">
                <span className="peek-title">Bạn nhìn thấy (riêng) — thứ tự rút:</span>
                {me.peek.map((c, i) => (
                  <div key={i} className="peek-item">
                    <span className="peek-num">{i + 1}</span>
                    <CardView card={c} secret />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      </div>

      <PendingPanel pending={view.pending} mine={!!myPending} send={send} />
      {/* give pending mà không kéo-thả được (cảm ứng/trợ năng): bấm chọn lá rồi bấm Đưa */}
      {givePending && cards.length > 0 && (
        <div className="actions">
          <button className="primary"
                  onClick={() => send({ action: 'respond', payload: { card_id: cards[0].id } })}>
            Đưa lá đã chọn
          </button>
        </div>
      )}

      {connected && isMyTurn && !myPending && !view.nope_window && (
        <div className="actions">
          {cards.length > 0 && (
            <button className="primary" onClick={tryPlaySelected}>
              {(() => {
                if (cards.length < 2) return 'Đánh thẻ'
                if (cards.length > 3) return 'Chỉ chọn tối đa 3 lá'
                const core = cards.map((c) => c.type).filter((t) => t !== 'feralcat')
                const same = new Set(core).size <= 1
                return same ? `Đánh combo ${cards.length} lá` : `Đánh ${cards.length} lá`
              })()}
            </button>
          )}
        </div>
      )}

      {error && <div className="error-toast">{error}</div>}

      <div className={`hand-area ${me.blind ? 'blind' : ''}`}
           style={view.phase === 'lobby' ? { display: 'none' } : undefined}>
        <h3>Tay bài {me.blind ? '(BỊ MÙ)' : ''} {me.marked ? '— có thẻ bị Mark!' : ''}
          {!isMyTurn && view.phase === 'playing' ? `— chờ ${view.turn.current}` : ''}</h3>
        <div className="hand">
          {(me.hand || []).map((c, i) => {
            const mid = (me.hand.length - 1) / 2
            const off = i - mid
            const n = me.hand.length
            // nhiều bài: overlap chồng hơn, góc quạt + vồng cong nhỏ lại cho gọn
            const overlap = n > 9 ? -58 : n > 6 ? -48 : -34
            const angle = n > 12 ? 1.4 : n > 9 ? 2.0 : n > 6 ? 2.6 : 3.4
            const curve = n > 12 ? 0.6 : n > 9 ? 1.0 : n > 6 ? 1.5 : 2.1
            return (
              <div key={c.id} className="hand-slot"
                   style={{ transform: `rotate(${off * angle}deg) translateY(${off * off * curve}px)`,
                            marginLeft: i ? overlap : 0, zIndex: i }}>
                <div className={`hand-card ${selected.includes(c.id) ? 'selected' : ''}
                                ${dealIds.has(c.id) ? 'dealt' : ''}
                                ${drag?.card.id === c.id ? 'dragging' : ''}`}
                     onPointerDown={(e) => startDrag(e, c)}
                     onMouseMove={tilt}
                     onMouseLeave={untilt}
                     onContextMenu={(e) => { e.preventDefault(); setZoom(c) }}
                     onClick={() => {
                       if (dragStartedRef.current) { dragStartedRef.current = false; return }
                       toggleSelect(c.id)
                     }}>
                  <div><CardView card={c} /></div>
                  {canPlay(c) && c.type !== 'godcat' &&
                    <button className="quick" onClick={(e) => { e.stopPropagation(); send({ action: 'play', card_id: c.id }) }}>Đánh</button>}
                  {(me.alive || c.type === 'clairvoyance' || c.type === 'feedthedead')
                    && ANYTIMES.includes(c.type) && !view.nope_window && !view.pending &&
                    <button className="quick now"
                            onClick={(e) => {
                              e.stopPropagation()
                              if (c.type === 'godcat') {
                                setGodcatNow(true)
                                setGodcatCard(c)
                              } else {
                                send({ action: 'play_now', card_id: c.id })
                              }
                            }}>NOW</button>}
                </div>
              </div>
            )
          })}
        </div>
        {!me.alive && <div className="dead-note">💀 Bạn đã chết — vẫn giữ bài để người khác "tận dụng"</div>}
      </div>

      {/* bản sao bài đang kéo theo con trỏ */}
      {drag && createPortal(
        <div className="drag-ghost" style={{ left: drag.x, top: drag.y }}>
          <CardView card={drag.card} />
        </div>,
        document.body,
      )}

      {/* cutscene bom nổ — mọi người cùng thấy */}
      {boom && createPortal(
        <div className="boom-overlay">
          <div className="boom-dark" />
          <div className="boom-flash" />
          <div className="boom-ring" />
          <div className="boom-text">
            💥<br />{boom ? `${boom.toUpperCase()} NỔ TUNG!` : 'BOOM!'}
          </div>
        </div>,
        document.body,
      )}

      {/* phóng to thẻ khi giữ chuột phải (hoặc bấm lá trong grave list) */}
      {zoom && createPortal(
        <div className="zoom-overlay" onClick={() => setZoom(null)}>
          <figure className="zoom-card">
            {/* CardView có fallback emoji khi thiếu ảnh; img trần để lại overlay trống */}
            <CardView card={zoom} />
          </figure>
        </div>,
        document.body,
      )}

      {/* danh sách các thẻ đã đánh (bấm vào Bỏ đi) — bấm lá để phóng to */}
      {graveList && createPortal(
        <div className="zoom-overlay grave-list-overlay" onClick={() => setGraveList(false)}>
          <div className="grave-list" onClick={(e) => e.stopPropagation()}>
            <h3>Bỏ đi ({view.grave.length})</h3>
            <div className="grave-list-items">
              {(view.grave || []).map((c, i) => (
                <button key={c.id || i} type="button" className="grave-item"
                        onClick={() => setZoom(c)}>
                  <CardView small card={c} />
                  <span>#{view.grave.length - i}</span>
                </button>
              ))}
            </div>
          </div>
        </div>,
        document.body,
      )}

      {/* godcat widget: nhập thẻ để hóa thân (fuzzy match) */}
      {godcatCard && createPortal(
        <div className="zoom-overlay" onClick={() => { setGodcatCard(null); setGodcatNow(false) }}>
          <div className="godcat-panel" onClick={(e) => e.stopPropagation()}>
            <h3>😇 Godcat hóa thân thành thẻ nào?</h3>
            <div className="input-card-row">
              <input
                autoFocus
                placeholder="vd skip, attack2x, favor…"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.target.value.trim()) {
                    send({ action: godcatNow ? 'play_now' : 'play', card_id: godcatCard.id, as_type: e.target.value.trim() })
                    setGodcatCard(null)
                    setGodcatNow(false)
                  }
                }}
                ref={(el) => el && el.focus()}
              />
              <button className="primary" onClick={(e) => {
                const v = e.target.closest('.godcat-panel').querySelector('input').value
                if (v.trim()) {
                  send({ action: godcatNow ? 'play_now' : 'play', card_id: godcatCard.id, as_type: v.trim() })
                  setGodcatCard(null)
                  setGodcatNow(false)
                }
              }}>Đánh</button>
            </div>
            <p className="godcat-hint">Gõ gần đúng cũng được (ví dụ "attack" → Attack 2x).</p>
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
