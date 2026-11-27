// api.js: REST + WebSocket helper cho Exploding Kitty

async function parseApiError(r, fallback) {
  let msg = fallback
  let code = ''
  try {
    const data = await r.json()
    if (data?.message) msg = data.message
    else if (typeof data?.detail === 'string') msg = data.detail
    else if (data?.detail?.message) msg = data.detail.message
    if (data?.code) code = String(data.code)
    else if (data?.detail?.code) code = String(data.detail.code)
  } catch { /* bỏ qua body không phải JSON */ }
  const err = new Error(msg)
  err.status = r.status
  if (code) err.code = code
  return err
}

export async function getHealth() {
  const r = await fetch('/api/health')
  if (!r.ok) throw await parseApiError(r, 'Không kiểm tra được trạng thái server')
  return r.json()
}

export async function debugListRooms() {
  const r = await fetch('/api/debug/rooms')
  if (!r.ok) throw await parseApiError(r, 'Không tải được danh sách phòng debug')
  const data = await r.json()
  return Array.isArray(data) ? data : []
}

export async function debugInspectRoom(code) {
  const r = await fetch(`/api/debug/rooms/${encodeURIComponent(code)}`)
  if (!r.ok) throw await parseApiError(r, `Không kiểm tra được phòng ${code}`)
  return r.json()
}

export async function debugAction(code, payload) {
  const r = await fetch(`/api/debug/rooms/${encodeURIComponent(code)}/action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw await parseApiError(r, 'Thao tác debug thất bại')
  return r.json()
}

export async function createRoom() {
  const r = await fetch('/api/rooms', { method: 'POST' })
  if (!r.ok) throw await parseApiError(r, 'Không tạo được phòng')
  return (await r.json()).code
}

export async function listRooms() {
  const r = await fetch('/api/rooms')
  if (!r.ok) return []
  const data = await r.json()
  return Array.isArray(data) ? data : []
}

export async function getRoom(code) {
  const r = await fetch(`/api/rooms/${encodeURIComponent(code)}`)
  if (r.status === 404) return null
  if (!r.ok) throw new Error('Không kiểm tra được phòng')
  return r.json()
}

export async function listDesks() {
  const r = await fetch('/api/desks')
  if (!r.ok) return []
  const data = await r.json()
  return Array.isArray(data) ? data : []
}

export async function listDeskDetails() {
  try {
    const r = await fetch('/api/desks/details')
    if (r.ok) {
      const data = await r.json()
      if (Array.isArray(data)) return data
    }
  } catch { /* fallback sang /api/desks */ }
  const ids = await listDesks()
  return ids.map((item) => (typeof item === 'string' ? { id: item, title: item } : item))
}

export async function listCards() {
  const r = await fetch('/api/cards')
  if (!r.ok) return null
  const data = await r.json()
  return data && typeof data === 'object' ? data : null
}

export function sessionKey(code, name) {
  return `ek_session:${code}:${name}`
}

export function wsUrl(code, name, session = '') {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const query = session
    ? `?name=${encodeURIComponent(name)}&token=${encodeURIComponent(session)}`
    : `?name=${encodeURIComponent(name)}`
  return `${proto}//${location.host}/ws/${encodeURIComponent(code)}${query}`
}

// sessionStorage có thể bị chặn bởi trình duyệt -> không được ném exception
export const store = {
  get(key) {
    try { return sessionStorage.getItem(key) || '' } catch { return '' }
  },
  set(key, val) {
    try { sessionStorage.setItem(key, val) } catch { /* bị chặn — cứ chạy tiếp */ }
  },
  remove(key) {
    try { sessionStorage.removeItem(key) } catch { /* bị chặn — cứ chạy tiếp */ }
  },
}
