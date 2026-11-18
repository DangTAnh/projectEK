import React, { useEffect, useState } from 'react'
import { createRoom, listRooms, store } from './api.js'

export default function Home() {
  const [name, setName] = useState(() => store.get('ek_name'))
  const [rooms, setRooms] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    listRooms().then((d) => setRooms(Array.isArray(d) ? d : [])).catch(() => {})
    const t = setInterval(() => listRooms().then((d) => setRooms(Array.isArray(d) ? d : [])).catch(() => {}), 3000)
    return () => clearInterval(t)
  }, [])

  function enter(path) {
    if (!name.trim()) return alert('Nhập tên của bạn trước!')
    store.set('ek_name', name.trim())
    location.href = path
  }

  async function onCreate() {
    if (!name.trim()) return alert('Nhập tên của bạn trước!')
    setBusy(true)
    setError('')
    store.set('ek_name', name.trim())
    try {
      const code = await createRoom()
      location.href = `/?room=${code}`
    } catch (e) {
      setError('Không tạo được phòng — kiểm tra server rồi thử lại.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="home">
      <h1>💥 Exploding Kitty</h1>
      <p className="tagline">Rút thẻ — đừng để nổ!</p>
      <div className="panel">
        <input
          placeholder="Tên của bạn"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={64}
        />
        <div className="row">
          <button onClick={onCreate} disabled={busy}>Tạo phòng mới</button>
        </div>
        {error && <p className="error">{error}</p>}
        <div className="join-row">
          <input
            placeholder="Mã phòng"
            maxLength={4}
            style={{ textTransform: 'uppercase' }}
            onKeyDown={(e) => e.key === 'Enter' && enter(`/?room=${e.target.value.trim().toUpperCase()}`)}
            onChange={(e) => { e.target.value = e.target.value.toUpperCase() }}
            id="code-input"
          />
          <button
            onClick={() =>
              enter(`/?room=${document.getElementById('code-input').value.trim().toUpperCase()}`)
            }
          >
            Vào phòng
          </button>
        </div>
      </div>
      <h2>Phòng đang mở</h2>
      <ul className="room-list">
        {rooms.filter((r) => !r.started).map((r) => (
          <li key={r.code}>
            <span className="code">{r.code}</span>
            <span className="count">{r.player_count ?? 0}/9 người</span>
            <button onClick={() => enter(`/?room=${r.code}`)}>Vào</button>
          </li>
        ))}
        {!rooms.some((r) => !r.started) && <li className="empty">Chưa có phòng nào — hãy tạo!</li>}
      </ul>
    </div>
  )
}
