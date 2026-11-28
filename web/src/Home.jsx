import React, { useEffect, useState } from 'react'
import { createRoom, getHealth, getRoom, listRooms, store } from './api.js'
import RealIcon from './components/RealIcon.jsx'
import CatAvatar from './components/CatAvatar.jsx'
import CatCustomizerModal from './components/CatCustomizerModal.jsx'
import { loadSavedAvatar, saveAvatar } from './utils/catAvatar.js'

export default function Home() {
  const [name, setName] = useState(() => store.get('ek_name'))
  const [avatar, setAvatar] = useState(() => loadSavedAvatar(store.get('ek_name')))
  const [catOpen, setCatOpen] = useState(false)
  const [roomCode, setRoomCode] = useState('')
  const [rooms, setRooms] = useState([])
  const [loadingRooms, setLoadingRooms] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [debugEnabled, setDebugEnabled] = useState(false)

  useEffect(() => {
    let mounted = true
    getHealth()
      .then((h) => {
        if (mounted && h?.debug_enabled) setDebugEnabled(true)
      })
      .catch(() => {})
    const load = () => listRooms()
      .then((d) => {
        if (!mounted) return
        setRooms(Array.isArray(d) ? d : [])
        setLoadingRooms(false)
      })
      .catch(() => {
        if (mounted) setLoadingRooms(false)
      })
    load()
    const t = setInterval(load, 3000)
    return () => { mounted = false; clearInterval(t) }
  }, [])

  function requireName() {
    const clean = name.trim()
    if (!clean) {
      setError('Vui lòng nhập tên của bạn trước!')
      return ''
    }
    store.set('ek_name', clean)
    return clean
  }

  async function joinCode(rawCode, skipCheck = false) {
    const cleanName = requireName()
    if (!cleanName) return
    const cleanCode = (rawCode || '').trim().toUpperCase()
    if (!cleanCode) {
      setError('Vui lòng nhập mã phòng (4 ký tự).')
      return
    }
    setError('')
    if (!skipCheck) {
      setBusy(true)
      try {
        const info = await getRoom(cleanCode)
        if (!info) {
          setError(`Không tìm thấy phòng ${cleanCode}.`)
          return
        }
        const maxPlayers = info.max_players ?? 9
        if (!info.started && (info.player_count ?? 0) >= maxPlayers) {
          setError(`Phòng ${cleanCode} đã đầy (${info.player_count}/${maxPlayers}).`)
          return
        }
      } catch {
        // Nếu endpoint kiểm tra chưa sẵn sàng hoặc lỗi mạng tạm thời, để WS xử lý tiếp
      } finally {
        setBusy(false)
      }
    }
    location.href = `/?room=${encodeURIComponent(cleanCode)}`
  }

  async function onCreate() {
    if (!requireName()) return
    setBusy(true)
    setError('')
    try {
      const code = await createRoom()
      location.href = `/?room=${encodeURIComponent(code)}`
    } catch (e) {
      setError(e?.message || 'Không tạo được phòng — kiểm tra server rồi thử lại.')
    } finally {
      setBusy(false)
    }
  }

  const openRooms = rooms.filter((r) => !r.started)
  const playingRooms = rooms.filter((r) => r.started)

  return (
    <main className="home">
      <header className="home-hero">
        <div className="home-hero-top">
          <div className="home-badge">2–9 người chơi · Trực tuyến</div>
          {debugEnabled && (
            <a className="home-debug-link" href="/?debug=1" title="Mở Debug Studio">
              <RealIcon name="wrench" size={14} /> Debug Studio
            </a>
          )}
        </div>
        <h1>Exploding Kitty</h1>
        <p className="tagline">Rút bài chiến thuật — tránh mèo nổ, sống sót đến cuối cùng.</p>
      </header>

      <section className="panel" aria-label="Tạo hoặc vào phòng">
        <div className="home-cat-row">
          <button
            type="button"
            className="home-cat-preview"
            onClick={() => setCatOpen(true)}
            title="Bấm để tùy chỉnh nhân vật mèo"
          >
            <CatAvatar avatar={avatar} name={name || 'Mèo'} size={66} className="home-cat-svg" />
            <span className="home-cat-plate">{name.trim() || 'Mèo của bạn'}</span>
          </button>
          <div className="home-cat-copy">
            <strong>Mèo đại diện của bạn</strong>
            <button type="button" className="secondary-btn home-cat-btn" onClick={() => setCatOpen(true)}>
              Độ mèo ngay
            </button>
          </div>
        </div>

        <div className="field-group">
          <label className="field-label" htmlFor="player-name-input">Tên người chơi</label>
          <input
            id="player-name-input"
            aria-label="Tên của bạn"
            placeholder="Nhập tên hiển thị…"
            value={name}
            onChange={(e) => { setName(e.target.value); if (error) setError('') }}
            onKeyDown={(e) => { if (e.key === 'Enter' && !busy) onCreate() }}
            maxLength={64}
            autoFocus
          />
        </div>

        <button type="button" className="primary full-btn home-create-btn" onClick={onCreate} disabled={busy}>
          {busy ? 'Đang xử lý…' : 'Tạo phòng mới'}
        </button>

        <div className="home-divider" aria-hidden="true">
          <span>hoặc vào bằng mã phòng</span>
        </div>

        <form
          className="join-row"
          onSubmit={(e) => {
            e.preventDefault()
            joinCode(roomCode)
          }}
        >
          <input
            aria-label="Mã phòng"
            placeholder="MÃ PHÒNG (VD: ABCD)"
            maxLength={4}
            value={roomCode}
            style={{ textTransform: 'uppercase' }}
            onChange={(e) => {
              setRoomCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))
              if (error) setError('')
            }}
          />
          <button type="submit" className="secondary-btn" disabled={busy}>Vào phòng</button>
        </form>

        {error && <p className="error" role="alert" aria-live="assertive">{error}</p>}
      </section>

      <section className="home-section" aria-label="Danh sách phòng">
        <div className="section-head">
          <h2>Phòng đang chờ</h2>
          <span className="section-count">{openRooms.length}</span>
        </div>
        <ul className="room-list">
          {openRooms.map((r) => {
            const maxP = r.max_players ?? 9
            const full = (r.player_count ?? 0) >= maxP
            return (
              <li key={r.code}>
                <span className="code">{r.code}</span>
                <span className="count">
                  <span className="status-dot open" aria-hidden="true" />
                  {r.player_count ?? 0}/{maxP} người · Đang chờ
                </span>
                <button
                  type="button"
                  className="secondary-btn"
                  disabled={busy || full}
                  onClick={() => joinCode(r.code, true)}
                >
                  {full ? 'Đầy' : 'Tham gia'}
                </button>
              </li>
            )
          })}
          {!loadingRooms && openRooms.length === 0 && (
            <li className="empty">Chưa có phòng nào đang chờ — hãy tạo phòng mới để bắt đầu.</li>
          )}
          {loadingRooms && (
            <li className="empty">Đang tải danh sách phòng…</li>
          )}
        </ul>

        {playingRooms.length > 0 && (
          <div className="home-subsection">
            <div className="section-head">
              <h3 className="sub-heading">Đang diễn ra</h3>
              <span className="section-count muted">{playingRooms.length}</span>
            </div>
            <ul className="room-list room-list-playing">
              {playingRooms.map((r) => {
                const displayCode = r.display_code || r.code
                const specCount = r.spectator_count ?? 0
                return (
                  <li key={r.code}>
                    <span className="code">{displayCode}</span>
                    <span className="count">
                      <span className={`status-dot ${r.phase === 'ended' ? 'ended' : 'live'}`} aria-hidden="true" />
                      {r.player_count ?? 0}/{r.max_players ?? 9} người
                      {specCount > 0 ? ` · ${specCount} khán giả` : ''}
                      {' · '}
                      {r.phase === 'ended' ? 'Đã kết thúc' : r.phase === 'loading' ? 'Đang tải bài' : 'Đang chơi'}
                    </span>
                    <button
                      type="button"
                      disabled={busy}
                      title="Vào xem ván đấu hoặc kết nối lại ghế cũ"
                      onClick={() => joinCode(displayCode, true)}
                    >
                      Vào xem / Chơi lại
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        )}
      </section>

      <CatCustomizerModal
        open={catOpen}
        avatar={avatar}
        playerName={name.trim() || 'Mèo của bạn'}
        onClose={() => setCatOpen(false)}
        onSave={(next) => setAvatar(saveAvatar(next))}
      />
    </main>
  )
}
