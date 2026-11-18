// api.js: REST + WebSocket helper cho Exploding Kitty

export async function createRoom() {
  const r = await fetch('/api/rooms', { method: 'POST' })
  if (!r.ok) throw new Error('Không tạo được phòng')
  return (await r.json()).code
}

export async function listRooms() {
  const r = await fetch('/api/rooms')
  if (!r.ok) return []
  return r.json()
}

export function sessionKey(code, name) {
  return `ek_session:${code}:${name}`
}

export function wsUrl(code, name, session = '') {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const query = session
    ? `?name=${encodeURIComponent(name)}&token=${encodeURIComponent(session)}`
    : `?name=${encodeURIComponent(name)}`
  return `${proto}//${location.host}/ws/${code}${query}`
}

// sessionStorage có thể bị chặn bởi trình duyệt -> không được ném exception
export const store = {
  get(key) {
    try { return sessionStorage.getItem(key) || '' } catch { return '' }
  },
  set(key, val) {
    try { sessionStorage.setItem(key, val) } catch { /* bị chặn — cứ chạy tiếp */ }
  },
}
