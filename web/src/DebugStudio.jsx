import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  createRoom,
  debugAction,
  debugInspectRoom,
  debugListRooms,
  getHealth,
  listRooms,
} from './api.js'
import BoomOverlay from './components/BoomOverlay.jsx'
import EpicCardOverlay, {
  EPIC_FX_PRESETS,
  EPIC_PRELOAD_IMAGES,
  getEpicDuration,
} from './components/EpicCardOverlay.jsx'
import CardSlamHand from './components/CardSlamHand.jsx'
import CardTransferFx, { getTransferDuration } from './components/CardTransferFx.jsx'
import ActionCutscene, {
  ACTION_FX_PRESETS,
  FX_PRELOAD_IMAGES,
  getActionDuration,
} from './components/ActionCutscene.jsx'
import { CARD_EMOJI, getCardName, useCardCatalog } from './utils/cardCatalog.js'
import { isMuted, playSfx, setMuted, warmUpSfx } from './utils/sfx.js'
import './DebugStudio.css'

const START_DEBUG_CMD = '$env:EK_DEBUG="1"; uvicorn server.main:app --reload'
const QUICK_PLAYERS = ['Alice', 'Bob', 'Charlie']
const BOOM_VARIANTS = [
  { id: 'exploding', label: 'Exploding Kitten', icon: '💥' },
  { id: 'imploding', label: 'Imploding Kitten', icon: '🌌' },
  { id: 'devilcat', label: 'Devilcat', icon: '😈' },
]
const SFX_LIST = [
  { id: 'play', label: 'play' },
  { id: 'draw', label: 'draw' },
  { id: 'nope', label: 'nope' },
  { id: 'turn', label: 'turn' },
  { id: 'implode', label: 'implode' },
  { id: 'hellfire', label: 'hellfire' },
  { id: 'win', label: 'win' },
]
const QUICK_INJECT_TYPES = [
  'defuse',
  'explodingkitten',
  'implodingkitten',
  'devilcat',
  'nope',
  'skip',
  'attack2x',
  'seethefuture3x',
  'godcat',
]

function sfxForActionPreset(preset) {
  const id = preset?.id
  if (id === 'nope' || id === 'yup') return 'nope'
  if (id === 'imploding_arm') return 'implode'
  if (id === 'reverse' || id === 'skip' || id === 'superskip' || id === 'attack2x' || id === 'clone') return 'turn'
  if (id === 'seefuture' || id === 'dig' || id === 'potluck') return 'draw'
  return 'play'
}

function epicSfxForCard(cardType) {
  if (cardType === 'armageddon') return 'armageddon'
  if (cardType === 'towerofpower') return 'tower'
  if (cardType === 'catomicbomb') return 'catomic'
  if (cardType === 'devilcat') return 'hellfire'
  return 'epic'
}

function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(text)
  }
  return new Promise((resolve, reject) => {
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      resolve()
    } catch (e) {
      reject(e)
    }
  })
}

function cardTone(type) {
  if (type === 'explodingkitten' || type === 'implodingkitten' || type === 'devilcat') return 'bomb'
  if (type === 'defuse' || type === 'streakingkitten' || type === 'zombiekitten') return 'defuse'
  if (type === 'nope') return 'nope'
  if (type === 'godcat' || type === 'towerofpower' || type === 'catomicbomb' || type === 'armageddon') {
    return 'special'
  }
  return 'action'
}

function updateUrlRoom(code) {
  try {
    const url = code
      ? `/?debug=1&room=${encodeURIComponent(code)}`
      : '/?debug=1'
    window.history.replaceState(null, '', url)
  } catch { /* bỏ qua nếu history bị giới hạn */ }
}

export default function DebugStudio({ initialCode = '' }) {
  const catalog = useCardCatalog()

  const [debugEnabled, setDebugEnabled] = useState(null)
  const [rooms, setRooms] = useState([])
  const [selectedCode, setSelectedCode] = useState(() => (initialCode || '').trim().toUpperCase())
  const [snapshot, setSnapshot] = useState(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [busy, setBusy] = useState(false)
  const [lastSync, setLastSync] = useState('')
  const [toast, setToast] = useState(null)

  // VFX & SFX Sandbox state (works offline / without room or EK_DEBUG=1)
  const [victimName, setVictimName] = useState('Alice')
  const [boomVariant, setBoomVariant] = useState('exploding')
  const [previewBoom, setPreviewBoom] = useState(null)
  const [previewEpic, setPreviewEpic] = useState(null)
  const [studioShake, setStudioShake] = useState(false)
  const [muted, setMutedState] = useState(() => isMuted())
  const [sandboxSlam, setSandboxSlam] = useState(null)
  const [sandboxTransfer, setSandboxTransfer] = useState(null)
  const [sandboxAction, setSandboxAction] = useState(null)
  const [sandboxLastLabel, setSandboxLastLabel] = useState('')

  // Card injector & scenario controls
  const [targetPlayer, setTargetPlayer] = useState('')
  const [cardSearch, setCardSearch] = useState('')
  const [selectedCardType, setSelectedCardType] = useState('defuse')
  const [deckIndex, setDeckIndex] = useState('0')
  const [faceup, setFaceup] = useState(false)

  const previewTimerRef = useRef(null)
  const epicTimerRef = useRef(null)
  const sandboxSlamTimerRef = useRef(null)
  const sandboxTransferTimerRef = useRef(null)
  const sandboxActionTimerRef = useRef(null)
  const shakeTimerRef = useRef(null)
  const toastTimerRef = useRef(null)
  const pollInFlightRef = useRef(false)
  const selectedCodeRef = useRef(selectedCode)

  useEffect(() => {
    selectedCodeRef.current = selectedCode
  }, [selectedCode])

  useEffect(() => () => {
    clearTimeout(previewTimerRef.current)
    clearTimeout(epicTimerRef.current)
    clearTimeout(sandboxSlamTimerRef.current)
    clearTimeout(sandboxTransferTimerRef.current)
    clearTimeout(sandboxActionTimerRef.current)
    clearTimeout(shakeTimerRef.current)
    clearTimeout(toastTimerRef.current)
  }, [])

  useEffect(() => {
    const urls = [
      ...FX_PRELOAD_IMAGES,
      ...EPIC_PRELOAD_IMAGES,
      '/handout.png',
      '/backside.jpg',
      '/ui/play-hand.png',
    ]
    for (const src of urls) {
      const img = new Image()
      img.decoding = 'async'
      img.src = src
    }
  }, [])

  useEffect(() => {
    const unlock = () => warmUpSfx()
    window.addEventListener('pointerdown', unlock, { once: true, passive: true })
    window.addEventListener('keydown', unlock, { once: true, passive: true })
    return () => {
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('keydown', unlock)
    }
  }, [])

  const showToast = useCallback((type, text) => {
    setToast({ type, text })
    clearTimeout(toastTimerRef.current)
    toastTimerRef.current = setTimeout(() => setToast(null), 3800)
  }, [])

  const refreshState = useCallback(async ({ codeOverride, silent = false } = {}) => {
    if (pollInFlightRef.current && silent) return
    pollInFlightRef.current = true
    try {
      const health = await getHealth().catch(() => null)
      const enabled = !!health?.debug_enabled
      setDebugEnabled(enabled)

      if (!enabled) {
        const pubRooms = await listRooms().catch(() => [])
        setRooms(pubRooms)
        setSnapshot(null)
        setLastSync(new Date().toLocaleTimeString('vi-VN'))
        return
      }

      const list = await debugListRooms()
      setRooms(list)

      let code = codeOverride !== undefined ? codeOverride : selectedCodeRef.current
      if (!code && list.length > 0) {
        code = list[0].code
        setSelectedCode(code)
        updateUrlRoom(code)
      }

      if (code) {
        try {
          const snap = await debugInspectRoom(code)
          if (codeOverride !== undefined || selectedCodeRef.current === code) {
            setSnapshot(snap)
          }
        } catch (err) {
          if (err?.status === 404) {
            setSnapshot(null)
            if (!silent) showToast('err', `Phòng ${code} không còn tồn tại.`)
          } else if (!silent) {
            showToast('err', err?.message || 'Không tải được trạng thái phòng.')
          }
        }
      } else {
        setSnapshot(null)
      }
      setLastSync(new Date().toLocaleTimeString('vi-VN'))
    } catch (err) {
      if (!silent) showToast('err', err?.message || 'Không kết nối được tới server.')
    } finally {
      pollInFlightRef.current = false
    }
  }, [showToast])

  useEffect(() => {
    refreshState({ codeOverride: selectedCode })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCode])

  useEffect(() => {
    if (!autoRefresh || !debugEnabled) return undefined
    const id = setInterval(() => {
      refreshState({ silent: true })
    }, 1500)
    return () => clearInterval(id)
  }, [autoRefresh, debugEnabled, refreshState])

  const game = snapshot?.game || null
  const players = useMemo(() => game?.players || [], [game?.players])
  const connectedSet = useMemo(
    () => new Set(snapshot?.connected_players || []),
    [snapshot?.connected_players],
  )

  // Giữ targetPlayer hợp lệ khi danh sách người chơi thay đổi
  useEffect(() => {
    if (!players.length) {
      if (targetPlayer) setTargetPlayer('')
      return
    }
    if (!players.some((p) => p.name === targetPlayer)) {
      setTargetPlayer(game?.turn?.current || players[0].name)
    }
  }, [players, targetPlayer, game?.turn?.current])

  const catalogList = useMemo(() => {
    const items = Object.values(catalog || {})
    items.sort((a, b) => (a.name || a.type).localeCompare(b.name || b.type))
    return items
  }, [catalog])

  const filteredCards = useMemo(() => {
    const q = cardSearch.trim().toLowerCase()
    if (!q) return catalogList
    return catalogList.filter(
      (c) => c.type.toLowerCase().includes(q) || (c.name || '').toLowerCase().includes(q),
    )
  }, [catalogList, cardSearch])

  useEffect(() => {
    if (filteredCards.length > 0 && !filteredCards.some((c) => c.type === selectedCardType)) {
      setSelectedCardType(filteredCards[0].type)
    }
  }, [filteredCards, selectedCardType])

  const runOp = useCallback(async (payload, successMsg) => {
    if (!selectedCode) {
      showToast('err', 'Hãy chọn hoặc tạo một phòng trước.')
      return
    }
    setBusy(true)
    try {
      const updated = await debugAction(selectedCode, payload)
      setSnapshot(updated)
      setLastSync(new Date().toLocaleTimeString('vi-VN'))
      showToast('ok', successMsg)
      debugListRooms().then(setRooms).catch(() => {})
    } catch (err) {
      const codeSuffix = err?.code ? ` [${err.code}]` : ''
      showToast('err', `${err?.message || 'Thao tác thất bại'}${codeSuffix}`)
    } finally {
      setBusy(false)
    }
  }, [selectedCode, showToast])

  async function handleCreateTestRoom() {
    setBusy(true)
    try {
      const newCode = await createRoom()
      setSelectedCode(newCode)
      updateUrlRoom(newCode)
      await refreshState({ codeOverride: newCode })
      showToast('ok', `Đã tạo phòng ${newCode} — bấm + Alice / + Bob để mở tab người chơi.`)
    } catch (err) {
      showToast('err', err?.message || 'Không tạo được phòng test.')
    } finally {
      setBusy(false)
    }
  }

  function handleSelectRoom(nextCode) {
    setSelectedCode(nextCode)
    updateUrlRoom(nextCode)
  }

  function openPlayerTab(playerName) {
    if (!selectedCode) return
    const url = `/?room=${encodeURIComponent(selectedCode)}&name=${encodeURIComponent(playerName)}`
    window.open(url, '_blank', 'noopener')
  }

  function triggerBoomPreview() {
    const who = victimName.trim() || 'Alice'
    const dur = boomVariant === 'exploding' ? 2150 : 2450
    setPreviewBoom({ who, variant: boomVariant, key: Date.now() })
    playSfx(boomVariant === 'imploding' ? 'implode' : boomVariant === 'devilcat' ? 'hellfire' : 'boom')
    clearTimeout(previewTimerRef.current)
    previewTimerRef.current = setTimeout(() => setPreviewBoom(null), dur)

    setStudioShake(false)
    clearTimeout(shakeTimerRef.current)
    requestAnimationFrame(() => {
      setStudioShake(true)
      shakeTimerRef.current = setTimeout(() => setStudioShake(false), 650)
    })
  }

  function resetSandboxStage() {
    clearTimeout(sandboxSlamTimerRef.current)
    clearTimeout(sandboxTransferTimerRef.current)
    clearTimeout(sandboxActionTimerRef.current)
    setSandboxSlam(null)
    setSandboxTransfer(null)
    setSandboxAction(null)
    setSandboxLastLabel('')
  }

  function triggerSandboxSlam() {
    clearTimeout(sandboxTransferTimerRef.current)
    clearTimeout(sandboxActionTimerRef.current)
    setSandboxTransfer(null)
    setSandboxAction(null)
    setSandboxLastLabel('Play Slam')
    setSandboxSlam({ key: Date.now(), isMine: true, cardType: 'skip' })
    playSfx('play')
    clearTimeout(sandboxSlamTimerRef.current)
    sandboxSlamTimerRef.current = setTimeout(() => setSandboxSlam(null), 720)
  }

  function triggerSandboxTransfer(label, fxPayload, sfxKind) {
    clearTimeout(sandboxSlamTimerRef.current)
    clearTimeout(sandboxActionTimerRef.current)
    setSandboxSlam(null)
    setSandboxAction(null)
    setSandboxLastLabel(label)
    setSandboxTransfer({ key: Date.now(), ...fxPayload })
    playSfx(sfxKind)
    clearTimeout(sandboxTransferTimerRef.current)
    sandboxTransferTimerRef.current = setTimeout(
      () => setSandboxTransfer(null),
      getTransferDuration(fxPayload),
    )
  }

  function triggerSandboxAction(preset) {
    clearTimeout(sandboxSlamTimerRef.current)
    clearTimeout(sandboxTransferTimerRef.current)
    setSandboxSlam(null)
    setSandboxTransfer(null)
    setSandboxLastLabel(preset.label)
    setSandboxAction({ key: Date.now(), ...preset.fx })
    playSfx(sfxForActionPreset(preset))
    clearTimeout(sandboxActionTimerRef.current)
    sandboxActionTimerRef.current = setTimeout(
      () => setSandboxAction(null),
      getActionDuration(preset.fx),
    )
  }

  function triggerEpicPreview(preset) {
    resetSandboxStage()
    clearTimeout(previewTimerRef.current)
    setPreviewBoom(null)
    const cardType = preset?.fx?.card_type
    setPreviewEpic({ ...preset.fx, key: Date.now() })
    playSfx(epicSfxForCard(cardType))
    clearTimeout(epicTimerRef.current)
    epicTimerRef.current = setTimeout(() => setPreviewEpic(null), getEpicDuration(cardType))

    setStudioShake(false)
    clearTimeout(shakeTimerRef.current)
    requestAnimationFrame(() => {
      setStudioShake(true)
      shakeTimerRef.current = setTimeout(() => setStudioShake(false), 600)
    })
  }

  function handleToggleMute() {
    const next = !muted
    setMutedState(next)
    setMuted(next)
    showToast('ok', next ? '🔇 Đã tắt âm thanh SFX' : '🔊 Đã bật âm thanh SFX')
  }

  function handleCopyStartCmd() {
    copyToClipboard(START_DEBUG_CMD)
      .then(() => showToast('ok', 'Đã sao chép lệnh khởi động EK_DEBUG=1!'))
      .catch(() => showToast('err', 'Không sao chép được — hãy copy thủ công.'))
  }

  function handleCopyJson() {
    if (!snapshot) return
    copyToClipboard(JSON.stringify(snapshot, null, 2))
      .then(() => showToast('ok', 'Đã sao chép Raw JSON Snapshot!'))
      .catch(() => showToast('err', 'Không sao chép được JSON.'))
  }

  const parsedDeckIndex = Math.max(0, Number.parseInt(deckIndex, 10) || 0)
  const canRunRoomDebug = Boolean(debugEnabled && selectedCode)
  const isPlaying = game?.phase === 'playing'
  const logEntries = useMemo(() => {
    const arr = Array.isArray(game?.log_entries) ? game.log_entries : []
    return arr.slice(-25).reverse()
  }, [game?.log_entries])

  const scenarioTarget = targetPlayer || undefined

  return (
    <div className={`debug-studio ${studioShake ? 'shake' : ''}`}>
      <header className="ds-topbar">
        <div className="ds-brand-group">
          <div className="ds-title-wrap">
            <span className="ds-title-icon" aria-hidden="true">🛠</span>
            <div>
              <h1 className="ds-title">Exploding Kitty · Debug Studio</h1>
              <span className="ds-subtitle">
                VFX Sandbox &amp; Omniscient Room Console
                {lastSync ? ` · Sync ${lastSync}` : ''}
              </span>
            </div>
          </div>

          <span
            className={`ds-status-badge ${debugEnabled === true ? 'on' : debugEnabled === false ? 'off' : 'checking'}`}
            title={debugEnabled ? 'Backend đang bật EK_DEBUG=1' : 'Backend đang tắt chế độ debug'}
          >
            <i className="ds-dot" aria-hidden="true" />
            EK_DEBUG=1: {debugEnabled === true ? 'ON' : debugEnabled === false ? 'OFF' : '…'}
          </span>
        </div>

        <div className="ds-toolbar">
          <div className="ds-room-select-wrap">
            <select
              className="ds-select"
              aria-label="Chọn phòng"
              value={selectedCode}
              onChange={(e) => handleSelectRoom(e.target.value)}
            >
              <option value="">
                {rooms.length ? `— Chọn phòng (${rooms.length}) —` : '— Chưa có phòng —'}
              </option>
              {rooms.map((r) => {
                const whoList = Array.isArray(r.players) && r.players.length
                  ? ` · ${r.players.join(', ')}`
                  : ''
                return (
                  <option key={r.code} value={r.code}>
                    {r.code} ({r.player_count ?? 0}/{r.max_players ?? 9} · {r.phase || (r.started ? 'playing' : 'lobby')}){whoList}
                  </option>
                )
              })}
            </select>
          </div>

          <button
            type="button"
            className="ds-btn"
            onClick={() => refreshState({ codeOverride: selectedCode })}
            disabled={busy}
            title="Làm mới trạng thái ngay"
          >
            ↻ Làm mới
          </button>

          <button
            type="button"
            className={`ds-btn ${autoRefresh ? 'active' : ''}`}
            onClick={() => setAutoRefresh((v) => !v)}
            title="Tự động cập nhật mỗi 1.5 giây"
            aria-pressed={autoRefresh}
          >
            {autoRefresh ? '● Auto 1.5s' : '○ Auto OFF'}
          </button>

          <button
            type="button"
            className="ds-btn primary"
            onClick={handleCreateTestRoom}
            disabled={busy}
          >
            + Tạo phòng test
          </button>

          {selectedCode && (
            <div className="ds-player-launchers" role="group" aria-label="Mở nhanh tab người chơi">
              {QUICK_PLAYERS.map((p) => (
                <button
                  key={p}
                  type="button"
                  className="ds-pill-btn"
                  title={`Mở phòng ${selectedCode} với tên ${p} ở tab mới`}
                  onClick={() => openPlayerTab(p)}
                >
                  + {p}
                </button>
              ))}
            </div>
          )}

          <a className="ds-home-link" href="/">← Trang chủ</a>
        </div>
      </header>

      {debugEnabled === false && (
        <div className="ds-off-banner" role="status">
          <div className="ds-off-banner-text">
            <strong>⚠️ Chế độ Backend Debug đang TẮT (`EK_DEBUG=1` chưa bật).</strong>
            <span>
              VFX &amp; SFX Sandbox bên trái vẫn hoạt động bình thường. Để mở khóa Room Inspector &amp; kịch bản server, hãy chạy backend với:
            </span>
          </div>
          <div className="ds-cmd-box">
            <code>{START_DEBUG_CMD}</code>
            <button type="button" className="ds-btn compact" onClick={handleCopyStartCmd}>
              📋 Copy
            </button>
          </div>
        </div>
      )}

      {toast && (
        <div className={`ds-toast ${toast.type}`} role="status" aria-live="polite">
          <span>{toast.type === 'ok' ? '✓' : '⛔'} {toast.text}</span>
          <button
            type="button"
            className="ds-toast-close"
            aria-label="Đóng thông báo"
            onClick={() => setToast(null)}
          >
            ✕
          </button>
        </div>
      )}

      <main className="ds-grid">
        {/* ════════════ LEFT PANEL: VFX SANDBOX & QUICK CONTROLS ════════════ */}
        <section className="ds-col ds-col-left" aria-label="VFX Sandbox và Điều khiển nhanh">
          {/* 1. Animation & SFX Sandbox (always available) */}
          <article className="ds-card ds-vfx-card">
            <div className="ds-card-head">
              <div>
                <h2>💥 Animation &amp; SFX Sandbox</h2>
                <p className="ds-card-sub">Hoạt động mọi lúc — không cần phòng hay EK_DEBUG=1</p>
              </div>
              <button
                type="button"
                className="ds-btn compact"
                onClick={handleToggleMute}
                title={muted ? 'Đang tắt âm thanh — bấm để bật' : 'Đang bật âm thanh — bấm để tắt'}
              >
                {muted ? '🔇 Muted' : '🔊 SFX ON'}
              </button>
            </div>

            <div className="ds-field">
              <label className="ds-label" htmlFor="ds-victim-input">Tên nạn nhân</label>
              <input
                id="ds-victim-input"
                className="ds-input"
                value={victimName}
                onChange={(e) => setVictimName(e.target.value)}
                placeholder="Alice"
                maxLength={40}
              />
            </div>

            <div className="ds-field">
              <span className="ds-label">Biến thể bom</span>
              <div className="ds-variant-pills" role="radiogroup" aria-label="Biến thể bom">
                {BOOM_VARIANTS.map((v) => (
                  <button
                    key={v.id}
                    type="button"
                    role="radio"
                    aria-checked={boomVariant === v.id}
                    className={`ds-variant-pill ${boomVariant === v.id ? 'active' : ''} v-${v.id}`}
                    onClick={() => setBoomVariant(v.id)}
                  >
                    <span>{v.icon}</span> {v.label}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="button"
              className="ds-boom-trigger"
              onClick={triggerBoomPreview}
            >
              💥 Test Animation Nổ
            </button>

            <div className="ds-sfx-row">
              <span className="ds-label-inline">Test SFX:</span>
              <div className="ds-sfx-pills">
                {SFX_LIST.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    className="ds-btn compact"
                    onClick={() => playSfx(s.id)}
                  >
                    🔊 {s.label}
                  </button>
                ))}
              </div>
            </div>
          </article>

          {/* 1b. Action & Hand VFX Sandbox (always available offline) */}
          <article className="ds-card ds-fx-sandbox-card">
            <div className="ds-card-head">
              <div>
                <h2>🎬 Action &amp; Hand VFX Sandbox</h2>
                <p className="ds-card-sub">Bấm 1 lần để xem thử hiệu ứng tay &amp; cutscene lá bài (chạy offline)</p>
              </div>
              <button
                type="button"
                className="ds-btn compact"
                onClick={resetSandboxStage}
                title="Xóa hiệu ứng đang chạy trên sân khấu"
              >
                ↺ Reset
              </button>
            </div>

            <div className="ds-fx-stage" aria-label="Sân khấu xem trước hiệu ứng bài">
              <div className="ds-fx-stage-hud">
                <span className="ds-fx-stage-badge">Live Stage</span>
                {sandboxLastLabel && <span className="ds-fx-stage-last">{sandboxLastLabel}</span>}
              </div>
              <div className="ds-fx-stage-felt" aria-hidden="true">
                <div className="ds-fx-prop-deck">Deck</div>
                <div className="ds-fx-prop-grave">Discard</div>
              </div>
              <div className="ds-fx-stage-hint">Chọn thao tác tay hoặc thẻ bên dưới để phát</div>
              <CardSlamHand slam={sandboxSlam} />
              <CardTransferFx fx={sandboxTransfer} />
              <ActionCutscene fx={sandboxAction} />
            </div>

            <div className="ds-fx-group">
              <span className="ds-label">Hand Operations</span>
              <div className="ds-fx-btn-grid">
                <button type="button" className="ds-fx-btn" onClick={triggerSandboxSlam}>
                  Play Slam
                </button>
                <button
                  type="button"
                  className="ds-fx-btn"
                  onClick={() => triggerSandboxTransfer(
                    'Draw Top',
                    { mode: 'draw_mine', source: 'top', actor: victimName.trim() || 'Alice' },
                    'draw',
                  )}
                >
                  Draw Top
                </button>
                <button
                  type="button"
                  className="ds-fx-btn"
                  onClick={() => triggerSandboxTransfer(
                    'Draw Bottom',
                    { mode: 'draw_mine', source: 'bottom', actor: victimName.trim() || 'Alice' },
                    'draw',
                  )}
                >
                  Draw Bottom
                </button>
                <button
                  type="button"
                  className="ds-fx-btn"
                  onClick={() => triggerSandboxTransfer(
                    'Give Out',
                    { mode: 'give_out', actor: victimName.trim() || 'Alice', target: 'Bob' },
                    'play',
                  )}
                >
                  Give Out
                </button>
                <button
                  type="button"
                  className="ds-fx-btn"
                  onClick={() => triggerSandboxTransfer(
                    'Favor Handout',
                    { mode: 'give_out', reason: 'favor', actor: victimName.trim() || 'Alice', target: 'Bob' },
                    'play',
                  )}
                >
                  Favor Handout
                </button>
                <button
                  type="button"
                  className="ds-fx-btn"
                  onClick={() => triggerSandboxTransfer(
                    'Receive In',
                    { mode: 'receive_in', reason: 'favor', actor: 'Bob', target: victimName.trim() || 'Alice' },
                    'draw',
                  )}
                >
                  Receive In
                </button>
                <button
                  type="button"
                  className="ds-fx-btn"
                  onClick={() => triggerSandboxTransfer(
                    'Put Into Deck',
                    { mode: 'give_out', reason: 'bury', toDeck: true, actor: victimName.trim() || 'Alice' },
                    'play',
                  )}
                >
                  Put Into Deck
                </button>
                <button
                  type="button"
                  className="ds-fx-btn"
                  onClick={() => triggerSandboxTransfer(
                    'Opponent Draw',
                    { mode: 'draw_other', source: 'top', actor: 'Bob' },
                    'draw',
                  )}
                >
                  Opponent Draw
                </button>
              </div>
            </div>

            <div className="ds-fx-group">
              <span className="ds-label">Card Action Cutscenes ({ACTION_FX_PRESETS.length})</span>
              <div className="ds-fx-btn-grid">
                {ACTION_FX_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    className="ds-fx-btn preset"
                    onClick={() => triggerSandboxAction(preset)}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="ds-fx-group ds-fx-epic-group">
              <span className="ds-label ds-fx-label-epic">
                LEGENDARY CUTSCENES (FULL-SCREEN)
              </span>
              <div className="ds-fx-btn-grid">
                {EPIC_FX_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    className={`ds-fx-btn epic epic-${preset.id}`}
                    onClick={() => triggerEpicPreview(preset)}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>
          </article>

          {/* 2. 1-click Scenarios */}
          <article className="ds-card">
            <div className="ds-card-head">
              <div>
                <h2>⚡ Kịch bản nhanh</h2>
                <p className="ds-card-sub">
                  {canRunRoomDebug
                    ? `Phòng ${selectedCode} · ${game ? `Pha: ${game.phase}` : 'Đang ở sảnh'}`
                    : 'Chọn phòng & bật EK_DEBUG=1 để kích hoạt'}
                </p>
              </div>
              {game && players.length > 0 && (
                <select
                  className="ds-select compact"
                  aria-label="Mục tiêu kịch bản"
                  value={targetPlayer}
                  onChange={(e) => setTargetPlayer(e.target.value)}
                >
                  {players.map((p) => (
                    <option key={p.name} value={p.name}>
                      🎯 {p.name}{p.name === game.turn?.current ? ' (lượt)' : ''}{!p.alive ? ' 💀' : ''}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="ds-scenario-grid">
              <button
                type="button"
                className="ds-scenario-btn danger"
                disabled={!canRunRoomDebug || !isPlaying || busy}
                onClick={() => runOp(
                  { op: 'scenario_boom', target: scenarioTarget, keep_defuse: false, auto_draw: true },
                  `Đã kích nổ ngay cho ${scenarioTarget || 'người đang tới lượt'}!`,
                )}
              >
                <span className="ds-sc-title">💥 Nổ ngay (tự rút)</span>
                <span className="ds-sc-desc">Xóa Defuse, đặt Exploding lên đỉnh &amp; tự rút</span>
              </button>

              <button
                type="button"
                className="ds-scenario-btn warn"
                disabled={!canRunRoomDebug || !isPlaying || busy}
                onClick={() => runOp(
                  { op: 'scenario_boom', target: scenarioTarget, keep_defuse: true, auto_draw: false },
                  `Đã đặt Exploding lên đỉnh & giữ Defuse cho ${scenarioTarget || 'lượt hiện tại'}.`,
                )}
              >
                <span className="ds-sc-title">💣 Đặt Bom đỉnh + giữ Defuse</span>
                <span className="ds-sc-desc">Test luồng cứu nguy &amp; chèn lại bom vào deck</span>
              </button>

              <button
                type="button"
                className="ds-scenario-btn imploding"
                disabled={!canRunRoomDebug || !isPlaying || busy}
                onClick={() => runOp(
                  {
                    op: 'scenario_boom',
                    target: scenarioTarget,
                    bomb_type: 'implodingkitten',
                    faceup: true,
                    keep_defuse: false,
                    auto_draw: false,
                  },
                  'Đã đặt Imploding Kitten NGỬA lên đỉnh deck.',
                )}
              >
                <span className="ds-sc-title">☢️ Imploding ngửa (đỉnh)</span>
                <span className="ds-sc-desc">Không thể Defuse khi rút lá tiếp theo</span>
              </button>
            </div>

            <div className="ds-lifecycle-row">
              {!game ? (
                <button
                  type="button"
                  className="ds-btn primary"
                  disabled={!canRunRoomDebug || busy}
                  onClick={() => runOp({ op: 'start' }, 'Đã bắt đầu ván đấu!')}
                >
                  🚀 Bắt đầu ván
                </button>
              ) : (
                <button
                  type="button"
                  className="ds-btn"
                  disabled={!canRunRoomDebug || busy}
                  onClick={() => runOp({ op: 'return_lobby' }, 'Đã đưa phòng về sảnh chờ.')}
                >
                  🏠 Về sảnh
                </button>
              )}

              <button
                type="button"
                className="ds-btn"
                disabled={!canRunRoomDebug || !game?.nope || busy}
                onClick={() => runOp({ op: 'resolve_nope' }, 'Đã chốt cửa sổ Nope ngay lập tức.')}
              >
                ⏱️ Chốt Nope
              </button>

              <button
                type="button"
                className="ds-btn"
                disabled={!canRunRoomDebug || !game?.pending || busy}
                onClick={() => runOp({ op: 'clear_pending' }, 'Đã xóa trạng thái Pending.')}
              >
                🧹 Xóa Pending
              </button>
            </div>
          </article>

          {/* 3. Card Injector */}
          <article className="ds-card">
            <div className="ds-card-head">
              <div>
                <h2>🃏 Bơm thẻ (Card Injector)</h2>
                <p className="ds-card-sub">Đưa thẻ vào tay người chơi hoặc chèn chính xác vào Deck</p>
              </div>
            </div>

            <div className="ds-form-row">
              <div className="ds-field">
                <label className="ds-label" htmlFor="ds-target-select">Người chơi mục tiêu</label>
                <select
                  id="ds-target-select"
                  className="ds-select"
                  value={targetPlayer}
                  onChange={(e) => setTargetPlayer(e.target.value)}
                  disabled={!players.length}
                >
                  {!players.length && <option value="">— Chưa có người chơi —</option>}
                  {players.map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.name}{p.alive ? '' : ' (💀 Đã chết)'}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="ds-field">
              <label className="ds-label" htmlFor="ds-card-search">Chọn loại thẻ ({filteredCards.length}/{catalogList.length})</label>
              <input
                id="ds-card-search"
                className="ds-input"
                type="search"
                value={cardSearch}
                onChange={(e) => setCardSearch(e.target.value)}
                placeholder="Tìm nhanh: defuse, exploding, nope, godcat…"
              />
              <select
                className="ds-select"
                aria-label="Danh sách thẻ"
                value={selectedCardType}
                onChange={(e) => setSelectedCardType(e.target.value)}
              >
                {filteredCards.map((c) => (
                  <option key={c.type} value={c.type}>
                    {CARD_EMOJI[c.type] || '🃏'} {c.name} ({c.type})
                  </option>
                ))}
              </select>
              <div className="ds-quick-cards" aria-label="Chọn nhanh thẻ phổ biến">
                {QUICK_INJECT_TYPES.map((t) => (
                  <button
                    key={t}
                    type="button"
                    className={`ds-chip-pick tone-${cardTone(t)} ${selectedCardType === t ? 'active' : ''}`}
                    onClick={() => {
                      setCardSearch('')
                      setSelectedCardType(t)
                    }}
                  >
                    {CARD_EMOJI[t] || '🃏'} {getCardName(catalog, t)}
                  </button>
                ))}
              </div>
            </div>

            <div className="ds-deck-opts">
              <div className="ds-field ds-field-inline">
                <label className="ds-label" htmlFor="ds-deck-idx">Vị trí Deck (0 = đỉnh)</label>
                <input
                  id="ds-deck-idx"
                  className="ds-input ds-num-input"
                  type="number"
                  min={0}
                  max={Math.max(0, game?.deck_count ?? 100)}
                  value={deckIndex}
                  onChange={(e) => setDeckIndex(e.target.value)}
                />
              </div>
              <label className="ds-checkbox">
                <input
                  type="checkbox"
                  checked={faceup}
                  onChange={(e) => setFaceup(e.target.checked)}
                />
                <span>👁️ Face-up (lật ngửa)</span>
              </label>
            </div>

            <div className="ds-inject-actions">
              <button
                type="button"
                className="ds-btn primary"
                disabled={!canRunRoomDebug || !game || !targetPlayer || !selectedCardType || busy}
                onClick={() => runOp(
                  { op: 'give', target: targetPlayer, ctype: selectedCardType },
                  `Đã đưa ${getCardName(catalog, selectedCardType)} vào tay ${targetPlayer}.`,
                )}
              >
                + Đưa vào tay
              </button>
              <button
                type="button"
                className="ds-btn"
                disabled={!canRunRoomDebug || !game || !selectedCardType || busy}
                onClick={() => runOp(
                  { op: 'put_deck', ctype: selectedCardType, index: 0, faceup },
                  `Đã đặt ${getCardName(catalog, selectedCardType)} lên đỉnh Deck${faceup ? ' (ngửa)' : ''}.`,
                )}
              >
                ⬆ Lên đỉnh Deck
              </button>
              <button
                type="button"
                className="ds-btn"
                disabled={!canRunRoomDebug || !game || !selectedCardType || busy}
                onClick={() => runOp(
                  { op: 'put_deck', ctype: selectedCardType, index: parsedDeckIndex, faceup },
                  `Đã chèn ${getCardName(catalog, selectedCardType)} vào Deck vị trí #${parsedDeckIndex}.`,
                )}
              >
                ⬇ Chèn vào Deck
              </button>
            </div>
          </article>
        </section>

        {/* ════════════ RIGHT PANEL: OMNISCIENT LIVE ROOM INSPECTOR ════════════ */}
        <section className="ds-col ds-col-right" aria-label="Omniscient Live Room Inspector">
          {!debugEnabled ? (
            <article className="ds-card ds-empty-inspector">
              <div className="ds-empty-icon">🔒</div>
              <h2>Room Inspector đang khóa</h2>
              <p>
                Bật biến môi trường <code>EK_DEBUG=1</code> khi chạy backend để soi toàn bộ tay bài, thứ tự Deck, Pending/Nope và điều khiển ván đấu theo thời gian thực.
              </p>
              <div className="ds-cmd-box">
                <code>{START_DEBUG_CMD}</code>
                <button type="button" className="ds-btn compact" onClick={handleCopyStartCmd}>
                  📋 Copy
                </button>
              </div>
            </article>
          ) : !selectedCode || !snapshot ? (
            <article className="ds-card ds-empty-inspector">
              <div className="ds-empty-icon">🧪</div>
              <h2>Chưa chọn phòng để kiểm tra</h2>
              <p>
                Chọn một phòng ở thanh trên hoặc bấm <strong>+ Tạo phòng test</strong>, sau đó mở tab <strong>+ Alice</strong> và <strong>+ Bob</strong> để bắt đầu test ngay.
              </p>
              <button type="button" className="ds-btn primary" onClick={handleCreateTestRoom} disabled={busy}>
                + Tạo phòng test ngay
              </button>
            </article>
          ) : !game ? (
            <article className="ds-card">
              <div className="ds-card-head">
                <div>
                  <h2>🏠 Phòng {snapshot.code} — Đang ở sảnh chờ</h2>
                  <p className="ds-card-sub">
                    {snapshot.connected_players?.length || 0} người đang kết nối (cần tối thiểu 2 người để bắt đầu)
                  </p>
                </div>
                <button
                  type="button"
                  className="ds-btn primary"
                  disabled={busy || (snapshot.connected_players?.length || 0) < 2}
                  onClick={() => runOp({ op: 'start' }, 'Đã bắt đầu ván đấu!')}
                >
                  🚀 Bắt đầu ván
                </button>
              </div>

              <div className="ds-lobby-roster">
                {(snapshot.connected_players || []).length === 0 ? (
                  <p className="ds-muted-line">
                    Chưa có ai trong phòng. Bấm <strong>+ Alice</strong> và <strong>+ Bob</strong> trên thanh công cụ để mở tab người chơi!
                  </p>
                ) : (
                  (snapshot.connected_players || []).map((p) => (
                    <div key={p} className="ds-lobby-chip">
                      <span className="ds-online-dot" />
                      <strong>{p}</strong>
                      {snapshot.votes?.[p] && (
                        <span className="ds-vote-tag">vote: {snapshot.votes[p]}</span>
                      )}
                    </div>
                  ))
                )}
              </div>

              <details className="ds-json-details">
                <summary>
                  <span>📦 Raw JSON Snapshot</span>
                  <button
                    type="button"
                    className="ds-btn compact"
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleCopyJson() }}
                  >
                    📋 Copy JSON
                  </button>
                </summary>
                <pre className="ds-json-pre">{JSON.stringify(snapshot, null, 2)}</pre>
              </details>
            </article>
          ) : (
            <>
              {/* 1. Summary KPI Strip */}
              <div className="ds-kpi-strip">
                <div className="ds-kpi">
                  <span className="ds-kpi-label">Phase</span>
                  <strong className={`ds-kpi-val phase-${game.phase}`}>
                    {game.phase}{game.winner ? ` · 🏆 ${game.winner}` : ''}
                  </strong>
                </div>
                <div className="ds-kpi">
                  <span className="ds-kpi-label">Bộ bài</span>
                  <strong className="ds-kpi-val">{game.desk_name || '—'}</strong>
                </div>
                <div className="ds-kpi">
                  <span className="ds-kpi-label">Lượt hiện tại</span>
                  <strong className="ds-kpi-val accent">
                    {game.turn?.current || '—'} ×{game.turn?.turns_left ?? 1}{' '}
                    {game.turn?.direction === -1 ? '↺' : '↻'}
                  </strong>
                </div>
                <div className="ds-kpi">
                  <span className="ds-kpi-label">Deck</span>
                  <strong className="ds-kpi-val">{game.deck_count ?? 0} lá</strong>
                </div>
                <div className="ds-kpi">
                  <span className="ds-kpi-label">Pending</span>
                  <strong className={`ds-kpi-val ${game.pending ? 'warn' : 'muted'}`}>
                    {game.pending ? `${game.pending.kind} (${game.pending.owner})` : 'None'}
                  </strong>
                </div>
                <div className="ds-kpi">
                  <span className="ds-kpi-label">Nope</span>
                  <strong className={`ds-kpi-val ${game.nope ? 'danger' : 'muted'}`}>
                    {game.nope ? `${game.nope.actor} · ×${game.nope.stacked ?? 0}` : 'None'}
                  </strong>
                </div>
              </div>

              {/* 2. All Players & Full Hands */}
              <article className="ds-card">
                <div className="ds-card-head">
                  <div>
                    <h2>👥 Tất cả người chơi &amp; Tay bài đầy đủ ({players.length})</h2>
                    <p className="ds-card-sub">Bấm × trên từng lá bài để bỏ ngay khỏi tay (remove_card)</p>
                  </div>
                </div>

                <div className="ds-players-list">
                  {players.map((p) => {
                    const isTurn = game.turn?.current === p.name && game.phase === 'playing'
                    const isOnline = connectedSet.has(p.name)
                    const isTower = game.tower_wearer === p.name
                    return (
                      <div
                        key={p.name}
                        className={`ds-player-row ${isTurn ? 'is-turn' : ''} ${!p.alive ? 'is-dead' : ''}`}
                      >
                        <div className="ds-player-head">
                          <div className="ds-player-ident">
                            <span
                              className={`ds-conn-dot ${isOnline ? 'online' : 'offline'}`}
                              title={isOnline ? 'Đang kết nối' : 'Offline'}
                            />
                            <strong className="ds-player-name">{p.name}</strong>
                            {isTurn && <span className="ds-tag turn">🎯 Lượt</span>}
                            {!p.alive && <span className="ds-tag dead">💀 Đã nổ</span>}
                            {p.blind && <span className="ds-tag warn">🙈 Mù</span>}
                            {isTower && <span className="ds-tag accent">👑 Tower ({game.stash_count ?? 0})</span>}
                            {p.extra_turns > 0 && <span className="ds-tag info">+{p.extra_turns} lượt</span>}
                            {p.illtake_by && <span className="ds-tag warn">🫳 {p.illtake_by}</span>}
                            <span className="ds-hand-count">{p.count ?? p.hand?.length ?? 0} lá</span>
                          </div>

                          <div className="ds-player-actions">
                            <button
                              type="button"
                              className="ds-btn compact"
                              disabled={!isPlaying || !p.alive || busy}
                              title={`Chuyển lượt sang ${p.name}`}
                              onClick={() => runOp(
                                { op: 'set_turn', target: p.name, turns_left: 1 },
                                `Đã chuyển lượt cho ${p.name}.`,
                              )}
                            >
                              🎯 Đặt lượt
                            </button>
                            <button
                              type="button"
                              className={`ds-btn compact ${p.blind ? 'active' : ''}`}
                              disabled={busy}
                              title="Bật / tắt trạng thái mù (Curse of the Cat Butt)"
                              onClick={() => runOp(
                                { op: 'toggle_blind', target: p.name },
                                `Đã đổi trạng thái mù của ${p.name}.`,
                              )}
                            >
                              🙈 Mù
                            </button>
                            <button
                              type="button"
                              className="ds-btn compact"
                              disabled={!isPlaying || !p.alive || busy}
                              title={`Ép ${p.name} rút 1 lá từ đỉnh Deck`}
                              onClick={() => runOp(
                                { op: 'force_draw', target: p.name },
                                `Đã ép ${p.name} rút bài!`,
                              )}
                            >
                              🃏 Rút
                            </button>
                          </div>
                        </div>

                        <div className="ds-hand-chips">
                          {(p.hand || []).length === 0 ? (
                            <span className="ds-muted-line">Tay bài trống</span>
                          ) : (
                            (p.hand || []).map((c) => {
                              const tone = cardTone(c.type)
                              const isMarked = p.marked_id && p.marked_id === c.id
                              return (
                                <span
                                  key={c.id}
                                  className={`ds-card-chip tone-${tone} ${isMarked ? 'is-marked' : ''}`}
                                  title={`ID: ${c.id}${isMarked ? ' · Đang bị Mark' : ''}`}
                                >
                                  <span className="ds-chip-emoji">{CARD_EMOJI[c.type] || '🃏'}</span>
                                  <span className="ds-chip-name">{getCardName(catalog, c.type)}</span>
                                  {c.faceup && <span className="ds-chip-flag">👁️</span>}
                                  {isMarked && <span className="ds-chip-flag">📌</span>}
                                  <button
                                    type="button"
                                    className="ds-chip-rm"
                                    disabled={busy}
                                    aria-label={`Bỏ ${getCardName(catalog, c.type)} khỏi tay ${p.name}`}
                                    title="Bỏ lá bài này khỏi tay"
                                    onClick={() => runOp(
                                      { op: 'remove_card', target: p.name, card_id: c.id },
                                      `Đã bỏ ${getCardName(catalog, c.type)} khỏi tay ${p.name}.`,
                                    )}
                                  >
                                    ×
                                  </button>
                                </span>
                              )
                            })
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </article>

              {/* 3. Deck Order Viewer (Top 30) */}
              <article className="ds-card">
                <div className="ds-card-head">
                  <div>
                    <h2>📚 Thứ tự Deck (Top {Math.min(30, game.deck?.length || 0)} / {game.deck_count ?? 0})</h2>
                    <p className="ds-card-sub">#1 là lá trên đỉnh sẽ bị rút kế tiếp</p>
                  </div>
                </div>
                <div className="ds-deck-pills">
                  {(game.deck || []).length === 0 ? (
                    <span className="ds-muted-line">Deck trống</span>
                  ) : (
                    (game.deck || []).slice(0, 30).map((c, idx) => {
                      const tone = cardTone(c.type)
                      return (
                        <span
                          key={c.id || idx}
                          className={`ds-deck-pill tone-${tone} ${c.faceup ? 'faceup' : ''}`}
                          title={`Vị trí #${idx + 1} · ID: ${c.id}${c.faceup ? ' · Đang lật ngửa' : ''}`}
                        >
                          <span className="ds-deck-num">#{idx + 1}</span>
                          <span>{CARD_EMOJI[c.type] || '🃏'} {getCardName(catalog, c.type)}</span>
                          {c.faceup && <span className="ds-faceup-tag">NGỬA</span>}
                        </span>
                      )
                    })
                  )}
                </div>
              </article>

              {/* 4. Live Log (last 25) + Collapsible Raw JSON Snapshot */}
              <article className="ds-card">
                <div className="ds-card-head">
                  <div>
                    <h2>📜 Nhật ký trực tiếp (25 dòng gần nhất)</h2>
                  </div>
                </div>
                <ul className="ds-log-list">
                  {logEntries.length === 0 ? (
                    <li className="ds-muted-line">Chưa có nhật ký nào.</li>
                  ) : (
                    logEntries.map((entry) => (
                      <li
                        key={entry.seq}
                        className={`ds-log-item ${entry.text?.includes('BOOM') ? 'is-boom' : ''} ${entry.text?.includes('[debug]') ? 'is-debug' : ''}`}
                      >
                        <span className="ds-log-seq">#{entry.seq}</span>
                        {entry.private && <span className="ds-log-priv" title={`Riêng: ${entry.private}`}>🔒 {entry.private}</span>}
                        <span className="ds-log-text">{entry.text}</span>
                      </li>
                    ))
                  )}
                </ul>

                <details className="ds-json-details">
                  <summary>
                    <span>📦 Raw JSON Snapshot</span>
                    <button
                      type="button"
                      className="ds-btn compact"
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleCopyJson() }}
                    >
                      📋 Copy JSON
                    </button>
                  </summary>
                  <pre className="ds-json-pre">{JSON.stringify(snapshot, null, 2)}</pre>
                </details>
              </article>
            </>
          )}
        </section>
      </main>

      {/* VFX Sandbox Explosion & Epic Cutscene Preview Overlays */}
      <BoomOverlay boom={previewBoom} />
      <EpicCardOverlay epic={previewEpic} />
    </div>
  )
}
