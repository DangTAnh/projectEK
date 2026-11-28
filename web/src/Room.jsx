import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { listDeskDetails, sessionKey, store, wsUrl } from './api.js'
import CardView from './components/CardView.jsx'
import PlayerList from './components/PlayerList.jsx'
import PendingPanel from './components/PendingPanel.jsx'
import NopeBar from './components/NopeBar.jsx'
import CardPickerModal from './components/CardPickerModal.jsx'
import ZoomModal from './components/ZoomModal.jsx'
import ActionLog from './components/ActionLog.jsx'
import LobbyPanel from './components/LobbyPanel.jsx'
import FutureVisionPanel, { RevealedFutureStrip, BombRadarStrip } from './components/FutureVisionPanel.jsx'
import BoomOverlay from './components/BoomOverlay.jsx'
import EpicCardOverlay, {
  EPIC_CARD_TYPES,
  EPIC_PRELOAD_IMAGES,
  getEpicDuration,
} from './components/EpicCardOverlay.jsx'
import RealIcon from './components/RealIcon.jsx'
import CatCustomizerModal from './components/CatCustomizerModal.jsx'
import { loadSavedAvatar, saveAvatar } from './utils/catAvatar.js'
import CardSlamHand from './components/CardSlamHand.jsx'
import CardTransferFx, { getTransferDuration } from './components/CardTransferFx.jsx'
import ActionCutscene, {
  FX_PRELOAD_IMAGES,
  getActionDuration,
  resolveActionPreset,
} from './components/ActionCutscene.jsx'
import {
  ANYTIME_TYPES,
  UNPLAYABLE_TYPES,
  getCardName,
  useCardCatalog,
  validateCombo,
} from './utils/cardCatalog.js'
import { isMuted, playSfx, setMuted, warmUpSfx } from './utils/sfx.js'

const TERMINAL_CLOSE_CODES = new Set([4001, 4401, 4403, 4404])
const MAX_RETRIES = 20
const LEADING_EMOJI_RE = /^(?:[\p{Extended_Pictographic}\p{Emoji_Presentation}\uFE0F\u200D]+)\s*/u

function stripLeadingEmoji(line) {
  let out = String(line || '').trimStart()
  while (LEADING_EMOJI_RE.test(out)) {
    out = out.replace(LEADING_EMOJI_RE, '')
  }
  return out
}

function UiSvg({ name, size = 16 }) {
  const props = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: '1.9',
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }
  if (name === 'link') {
  return (
      <svg {...props}>
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
      </svg>
    )
  }
  if (name === 'wrench') {
  return (
      <svg {...props}>
        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
      </svg>
    )
  }
  if (name === 'sound-on') {
  return (
      <svg {...props}>
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
      </svg>
    )
  }
  if (name === 'sound-off') {
  return (
      <svg {...props}>
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
        <line x1="22" y1="9" x2="16" y2="15" />
        <line x1="16" y1="9" x2="22" y2="15" />
      </svg>
    )
  }
  if (name === 'log') {
  return (
      <svg {...props}>
        <line x1="8" y1="6" x2="21" y2="6" />
        <line x1="8" y1="12" x2="21" y2="12" />
        <line x1="8" y1="18" x2="21" y2="18" />
        <line x1="3" y1="6" x2="3.01" y2="6" />
        <line x1="3" y1="12" x2="3.01" y2="12" />
        <line x1="3" y1="18" x2="3.01" y2="18" />
      </svg>
    )
  }
  if (name === 'sort') {
  return (
      <svg {...props}>
        <path d="M3 7h11" />
        <path d="M3 12h8" />
        <path d="M3 17h5" />
        <path d="M18 6v12" />
        <path d="m15 15 3 3 3-3" />
      </svg>
    )
  }
  return null
}

function epicSfxForCard(cardType) {
  if (cardType === 'armageddon') return 'armageddon'
  if (cardType === 'towerofpower') return 'tower'
  if (cardType === 'catomicbomb') return 'catomic'
  if (cardType === 'devilcat') return 'hellfire'
  return 'epic'
}

function getSessionToken(roomCode, playerName) {
  const k = sessionKey(roomCode, playerName)
  const s = store.get(k)
  if (s) return s
  try { return localStorage.getItem(k) || '' } catch { return '' }
}

function setSessionToken(roomCode, playerName, token) {
  if (!token) return
  const k = sessionKey(roomCode, playerName)
  store.set(k, token)
  try { localStorage.setItem(k, token) } catch { /* bị chặn — bỏ qua */ }
}

function removeSessionToken(roomCode, playerName) {
  const k = sessionKey(roomCode, playerName)
  store.remove(k)
  try { localStorage.removeItem(k) } catch { /* bị chặn — bỏ qua */ }
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

export default function Room({ code }) {
  const catalog = useCardCatalog()
  const [name, setName] = useState(() =>
    (new URLSearchParams(location.search).get('name') || store.get('ek_name')).trim())
  const [nameDraft, setNameDraft] = useState('')
  const [nameJoinErr, setNameJoinErr] = useState('')
  const [view, setView] = useState(null)
  const [error, setError] = useState('')
  const [errorNonce, setErrorNonce] = useState(0)
  const [connError, setConnError] = useState('')
  const [infoToast, setInfoToast] = useState('')
  const [connState, setConnState] = useState('connecting')
  const [retryCount, setRetryCount] = useState(0)
  const [connectNonce, setConnectNonce] = useState(0)
  const [selected, setSelected] = useState([])
  const [handOrder, setHandOrder] = useState([])
  const [drag, setDrag] = useState(null)
  const [dealIds, setDealIds] = useState(() => new Set())
  const [shake, setShake] = useState(false)
  const [zoom, setZoom] = useState(null)
  const [graveList, setGraveList] = useState(false)
  const [peekOpen, setPeekOpen] = useState(false)
  const [desks, setDesks] = useState([])
  const [boom, setBoom] = useState(null)
  const [slam, setSlam] = useState(null)
  const [transferFx, setTransferFx] = useState(null)
  const [actionFx, setActionFx] = useState(null)
  const [epicFx, setEpicFx] = useState(null)
  const [deckLit, setDeckLit] = useState(false)
  const [godcatCard, setGodcatCard] = useState(null)
  const [godcatNow, setGodcatNow] = useState(false)
  const [endedDismissed, setEndedDismissed] = useState(false)
  const [mobileLogOpen, setMobileLogOpen] = useState(false)
  const [logCollapsed, setLogCollapsed] = useState(false)
  const [catModalOpen, setCatModalOpen] = useState(false)
  const [myAvatar, setMyAvatar] = useState(() => loadSavedAvatar(
    (new URLSearchParams(location.search).get('name') || store.get('ek_name')).trim(),
  ))
  const [turnBanner, setTurnBanner] = useState(null)
  const [turnSecLeft, setTurnSecLeft] = useState(null)
  const [loadProgress, setLoadProgress] = useState({ loaded: 0, total: 0, done: false })
  const [muted, setMutedState] = useState(() => isMuted())
  const [viewportW, setViewportW] = useState(() => (typeof window !== 'undefined' ? window.innerWidth : 1280))

  const seenSeqRef = useRef(null)
  const seenLogRef = useRef(null)
  const seenBoomSeqRef = useRef(null)
  const seenFxSeqRef = useRef(null)
  const wsRef = useRef(null)
  const retryRef = useRef(0)
  const tableRef = useRef(null)
  const deckRef = useRef(null)
  const handRef = useRef(null)
  const dragStartedRef = useRef(false)
  const dragCleanupRef = useRef(null)
  const prevHandRef = useRef(null)
  const prevRevealedRef = useRef(null)
  const prevPhaseRef = useRef(null)
  const prevTurnKeyRef = useRef(null)
  const turnBannerTimerRef = useRef(null)
  const turnTimerAnchorRef = useRef(null)
  const lastTickKeyRef = useRef('')
  const loadingSentRef = useRef(false)
  const prevNopeKeyRef = useRef('')
  const prevGraveTopIdRef = useRef(undefined)
  const slamTimerRef = useRef(null)
  const transferTimerRef = useRef(null)
  const actionTimerRef = useRef(null)
  const actionQueueRef = useRef([])
  const epicTimerRef = useRef(null)
  const lastLocalPlayAtRef = useRef(0)
  const deckLitTimerRef = useRef(null)
  const boomTimerRef = useRef(null)
  const shakeTimerRef = useRef(null)
  const infoToastTimerRef = useRef(null)
  const lastServerErrRef = useRef({ message: '', code: '' })
  const hasViewRef = useRef(false)
  const leavingRef = useRef(false)
  const connected = connState === 'open'

  useEffect(() => {
    hasViewRef.current = !!view
  }, [view])

  useEffect(() => {
    const onResize = () => setViewportW(window.innerWidth)
    window.addEventListener('resize', onResize)
  return () => window.removeEventListener('resize', onResize)
  }, [])

  // Khởi tạo AudioContext & noise buffer sẵn ở lần tương tác đầu tiên để tránh khựng frame nổ đầu
  useEffect(() => {
    const unlock = () => warmUpSfx()
    window.addEventListener('pointerdown', unlock, { once: true, passive: true })
    window.addEventListener('keydown', unlock, { once: true, passive: true })
  return () => {
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('keydown', unlock)
    }
  }, [])

  // Preload ảnh hiệu ứng tay & cutscene ngay khi vào phòng để không trễ frame đầu
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

  // dọn timer/listener drag khi unmount
  useEffect(() => () => {
    clearTimeout(boomTimerRef.current)
    clearTimeout(slamTimerRef.current)
    clearTimeout(transferTimerRef.current)
    clearTimeout(actionTimerRef.current)
    actionQueueRef.current = []
    clearTimeout(epicTimerRef.current)
    clearTimeout(shakeTimerRef.current)
    clearTimeout(infoToastTimerRef.current)
    clearTimeout(deckLitTimerRef.current)
    clearTimeout(turnBannerTimerRef.current)
    dragCleanupRef.current?.()
  }, [])

  const showInfo = useCallback((msg) => {
    setInfoToast(msg)
    clearTimeout(infoToastTimerRef.current)
    infoToastTimerRef.current = setTimeout(() => setInfoToast(''), 2600)
  }, [])

  const send = useCallback((obj) => {
    if (!connected || !wsRef.current || wsRef.current.readyState !== 1) {
      setError('Mất kết nối tới phòng — thao tác chưa được gửi.')
      return false
    }
    wsRef.current.send(JSON.stringify(obj))
    if (obj.action === 'play' || obj.action === 'play_now' || obj.action === 'combo' || obj.action === 'nope') {
      lastLocalPlayAtRef.current = Date.now()
    }
    if (obj.action === 'draw') playSfx('draw')
    else if (obj.action === 'play' || obj.action === 'play_now' || obj.action === 'combo') playSfx('play')
    return true
  }, [connected])

  useEffect(() => {
    if (!name) return undefined
    let closed = false
    let timer

    function terminalMessage(closeCode) {
      if (closeCode === 4001) return 'Phiên này đã được thay thế ở tab khác.'
      if (closeCode === 4401) return 'Phiên không hợp lệ hoặc tên đã có người dùng.'
      if (closeCode === 4403) return 'Phòng đã đầy hoặc ván đã bắt đầu.'
      if (closeCode === 4404) return 'Phòng không tồn tại.'
      return 'Kết nối bị từ chối.'
    }

    function connect() {
      if (closed) return
      lastServerErrRef.current = { message: '', code: '' }
      setConnState('connecting')
      const session = getSessionToken(code, name)
      const ws = new WebSocket(wsUrl(code, name, session))
      wsRef.current = ws

      ws.onmessage = (ev) => {
        let msg
        try {
          msg = JSON.parse(ev.data)
        } catch {
          return
        }
        if (!msg || typeof msg !== 'object') return

        if (msg.type === 'state') {
          const nextView = msg.view
          const token = nextView?.you?.session
          if (token) {
            setSessionToken(code, name, token)
            if (nextView.display_code && nextView.display_code !== code) {
              setSessionToken(nextView.display_code, name, token)
            }
          }
          lastServerErrRef.current = { message: '', code: '' }

          // Dò dòng log mới theo log_entries.seq (fallback nội dung dòng cuối nếu thiếu log_entries)
          let newLines = []
          const entries = Array.isArray(nextView.log_entries) ? nextView.log_entries : null
          if (entries && entries.length > 0) {
            const lastSeq = seenSeqRef.current
            if (lastSeq !== null) {
              newLines = entries.filter((e) => e.seq > lastSeq).map((e) => String(e.text || ''))
            }
            seenSeqRef.current = entries[entries.length - 1].seq
          } else {
            const log = nextView.log || []
            const lastSeen = seenLogRef.current
            if (lastSeen) {
              const idx = log.lastIndexOf(lastSeen)
              newLines = idx >= 0 ? log.slice(idx + 1) : log.slice(-3)
            }
            seenLogRef.current = log[log.length - 1]
          }

          let triggeredBoom = null
          if ('last_boom' in nextView) {
            const lb = nextView.last_boom
            if (nextView.phase === 'lobby' || nextView.phase === 'loading' || !lb) {
              seenBoomSeqRef.current = 0
            } else if (seenBoomSeqRef.current === null) {
              // Kết nối lần đầu / reconnect vào ván cũ: chỉ ghi nhận seq hiện tại, không phát lại nổ cũ
              seenBoomSeqRef.current = lb.seq || 0
            } else {
              if ((lb.seq || 0) < seenBoomSeqRef.current) {
                // Ván mới (rematch) reset _boom_seq về 1
                seenBoomSeqRef.current = 0
              }
              if ((lb.seq || 0) > seenBoomSeqRef.current) {
                seenBoomSeqRef.current = lb.seq
                triggeredBoom = {
                  who: lb.who || '',
                  variant: lb.variant || 'exploding',
                }
              }
            }
          } else {
            const boomLine = newLines.find((l) => l.includes('BOOM'))
            if (boomLine) {
              const allNew = newLines.join('\n')
              const who = boomLine.match(/BOOM!\s*(.+?)\s+nổ/)?.[1] || ''
              const variant = /imploding/i.test(allNew)
                ? 'imploding'
                : /devilcat/i.test(allNew)
                  ? 'devilcat'
                  : 'exploding'
              triggeredBoom = { who, variant }
            }
          }

          const prevPhase = prevPhaseRef.current
          if (nextView.phase === 'lobby' || nextView.phase === 'loading' || (prevPhase === 'ended' && nextView.phase !== 'ended')) {
            clearTimeout(boomTimerRef.current)
            setBoom(null)
            clearTimeout(slamTimerRef.current)
            setSlam(null)
            clearTimeout(transferTimerRef.current)
            setTransferFx(null)
            actionQueueRef.current = []
            clearTimeout(actionTimerRef.current)
            setActionFx(null)
            clearTimeout(epicTimerRef.current)
            setEpicFx(null)
            clearTimeout(shakeTimerRef.current)
            setShake(false)
          }

          if (triggeredBoom) {
            const { who, variant } = triggeredBoom
            setBoom({ who, variant, key: Date.now() })
            playSfx(variant === 'imploding' ? 'implode' : variant === 'devilcat' ? 'hellfire' : 'boom')
            clearTimeout(boomTimerRef.current)
            boomTimerRef.current = setTimeout(() => setBoom(null), variant === 'exploding' ? 2150 : 2450)
            setShake(true)
            clearTimeout(shakeTimerRef.current)
            shakeTimerRef.current = setTimeout(() => setShake(false), 650)
          }

          // Âm thanh đổi pha / lượt / banner lượt giữa bàn / cửa sổ Nope
          if (prevPhase === 'playing' && nextView.phase === 'ended') {
            playSfx('win')
            setEndedDismissed(false)
          } else if (prevPhase === 'ended' && nextView.phase !== 'ended') {
            setEndedDismissed(false)
          }
          prevPhaseRef.current = nextView.phase

          const nextIsSpectator = !!nextView.you?.spectator
          const nextTurn = nextView.phase === 'playing' ? (nextView.turn?.current || '') : ''
          const nextTurnsLeft = nextView.turn?.turns_left ?? 1
          const nextTurnKey = nextTurn ? `${nextTurn}:${nextTurnsLeft}` : ''
          const enteredPlaying = prevPhase === 'lobby' || prevPhase === 'loading' || prevPhase === 'ended'

          if (nextView.phase === 'playing' && nextTurn) {
            const turnChanged = prevTurnKeyRef.current !== null && prevTurnKeyRef.current !== nextTurnKey
            if (enteredPlaying || turnChanged) {
              const isMine = !nextIsSpectator && nextTurn === name && !!nextView.you?.alive
              setTurnBanner({
                key: `${nextTurnKey}:${Date.now()}`,
                actor: nextTurn,
                isMine,
                turnsLeft: nextTurnsLeft,
              })
              clearTimeout(turnBannerTimerRef.current)
              turnBannerTimerRef.current = setTimeout(() => setTurnBanner(null), 1550)
              if (isMine) {
                playSfx('turn')
              }
            }
            prevTurnKeyRef.current = nextTurnKey
          } else {
            prevTurnKeyRef.current = ''
            clearTimeout(turnBannerTimerRef.current)
            setTurnBanner(null)
          }

          const tt = nextView.phase === 'playing' ? nextView.turn_timer : null
          if (tt && typeof tt === 'object') {
            const remMs = typeof tt.remaining_ms === 'number'
              ? Math.max(0, tt.remaining_ms)
              : typeof tt.ends_ms === 'number'
                ? Math.max(0, tt.ends_ms - (typeof tt.server_now_ms === 'number' ? tt.server_now_ms : Date.now()))
                : 0
            const timerKey = `${tt.actor || ''}:${tt.ends_ms || ''}:${nextTurnKey}`
            turnTimerAnchorRef.current = {
              key: timerKey,
              actor: tt.actor || nextTurn,
              localEndsAt: Date.now() + remMs,
              durationMs: tt.duration_ms || 30000,
            }
            setTurnSecLeft(Math.ceil(remMs / 1000))
          } else {
            turnTimerAnchorRef.current = null
            setTurnSecLeft(null)
            lastTickKeyRef.current = ''
          }

          const nw = nextView.nope_window
          const nwKey = nw ? `${nw.actor}:${nw.card?.id || ''}:${nw.stacked ?? 0}` : ''
          if (nw && nwKey !== prevNopeKeyRef.current && (nw.stacked ?? 0) > 0) {
            playSfx('nope')
          }
          prevNopeKeyRef.current = nwKey

          // Bàn tay đập thẻ xuống chồng bài bỏ khi xuất hiện lá mới ở đỉnh grave
          const nextTop = nextView.grave_top?.[0] || null
          const nextTopId = nextTop?.id ?? null
          if (nextView.phase === 'lobby' || nextView.phase === 'loading') {
            prevGraveTopIdRef.current = null
          } else if (prevGraveTopIdRef.current === undefined) {
            prevGraveTopIdRef.current = nextTopId
          } else if (nextTopId && nextTopId !== prevGraveTopIdRef.current) {
            prevGraveTopIdRef.current = nextTopId
            const recentLocal = Date.now() - lastLocalPlayAtRef.current < 1500
            const newestLine = newLines.length ? stripLeadingEmoji(newLines[newLines.length - 1]) : ''
            const playersList = Array.isArray(nextView.players) ? nextView.players : []
            const matchedActor = playersList
              .map((p) => p.name)
              .filter(Boolean)
              .sort((a, b) => b.length - a.length)
              .find((pn) => newestLine === pn || newestLine.startsWith(`${pn} `) || newestLine.startsWith(`${pn}:`))
            const isMineSlam = matchedActor ? matchedActor === name : recentLocal
            setSlam({ key: Date.now(), isMine: isMineSlam, cardType: nextTop.type })
            clearTimeout(slamTimerRef.current)
            slamTimerRef.current = setTimeout(() => setSlam(null), 720)
          } else if (!nextTopId) {
            prevGraveTopIdRef.current = null
          }

          // Structured FX events feed (rút bài, chuyển bài, đặt vào deck, action cutscenes)
          const fxList = Array.isArray(nextView.fx_events) ? nextView.fx_events : []
          const lastEv = fxList.length > 0 ? fxList[fxList.length - 1] : null
          if (nextView.phase === 'lobby' || nextView.phase === 'loading') {
            seenFxSeqRef.current = 0
            actionQueueRef.current = []
            clearTimeout(actionTimerRef.current)
            setActionFx(null)
          } else if (seenFxSeqRef.current === null) {
            seenFxSeqRef.current = lastEv?.seq || 0
          } else {
            if ((lastEv?.seq || 0) < seenFxSeqRef.current) {
              seenFxSeqRef.current = 0
              actionQueueRef.current = []
            }
            const newFx = fxList.filter((ev) => ev && typeof ev.seq === 'number' && ev.seq > seenFxSeqRef.current)
            if (lastEv && typeof lastEv.seq === 'number' && lastEv.seq > seenFxSeqRef.current) {
              seenFxSeqRef.current = lastEv.seq
            }
            if (newFx.length > 0) {
              let latestTransfer = null
              const newActions = []
              let latestEpic = null
              for (const ev of newFx) {
                if (ev.kind === 'draw' || ev.kind === 'transfer' || ev.kind === 'put_deck' || ev.kind === 'receive') {
                  latestTransfer = ev
                } else if (ev.kind === 'card_fx' && EPIC_CARD_TYPES.has(ev.card_type)) {
                  latestEpic = ev
                } else if (
                  (ev.kind === 'card_fx' || ev.kind === 'nope' || ev.kind === 'defuse')
                  && !EPIC_CARD_TYPES.has(ev.card_type)
                  && resolveActionPreset(ev)
                ) {
                  newActions.push(ev)
                }
              }

              if (latestTransfer) {
                const ev = latestTransfer
                const fxKey = `${ev.seq}-${Date.now()}`
                let deckAnchor = null
                const isMyIlltakeGive = (
                  ev.kind === 'transfer'
                  && ev.card_type === 'illtakethat'
                  && ev.actor === name
                )
                if (ev.kind === 'draw' || ev.kind === 'put_deck' || isMyIlltakeGive) {
                  const tRect = tableRef.current?.getBoundingClientRect()
                  const dRect = deckRef.current?.getBoundingClientRect()
                  if (tRect && dRect && tRect.width > 0 && dRect.width > 0) {
                    deckAnchor = {
                      dx: Math.round((dRect.left + dRect.width / 2) - (tRect.left + tRect.width / 2)),
                      dy: Math.round((dRect.top + dRect.height / 2) - (tRect.top + tRect.height / 2)),
                      w: Math.round(dRect.width),
                      h: Math.round(dRect.height),
                    }
                  }
                }
                let nextTransfer = null
                if (ev.kind === 'draw') {
                  nextTransfer = {
                    key: fxKey,
                    mode: ev.actor === name ? 'draw_mine' : 'draw_other',
                    source: ev.source || 'top',
                    actor: ev.actor,
                    deckAnchor,
                  }
                } else if (ev.kind === 'transfer') {
                  const revealedCard = (
                    isMyIlltakeGive
                    && nextView.you?.peek_meta?.source === 'illtakethat'
                    && Array.isArray(nextView.you?.peek)
                  )
                    ? nextView.you.peek[0] || null
                    : null
                  nextTransfer = {
                    key: fxKey,
                    mode: ev.actor === name ? 'give_out' : ev.target === name ? 'receive_in' : 'transfer_other',
                    reason: ev.card_type,
                    source: ev.source || 'top',
                    actor: ev.actor,
                    target: ev.target,
                    card: revealedCard,
                    deckAnchor: isMyIlltakeGive ? deckAnchor : null,
                  }
                } else if (ev.kind === 'put_deck') {
                  nextTransfer = {
                    key: fxKey,
                    mode: ev.actor === name ? 'give_out' : 'transfer_other',
                    reason: ev.card_type || 'put_deck',
                    toDeck: true,
                    actor: ev.actor,
                    deckAnchor,
                  }
                } else if (ev.kind === 'receive') {
                  nextTransfer = {
                    key: fxKey,
                    mode: ev.actor === name ? 'receive_in' : 'transfer_other',
                    reason: ev.card_type,
                    actor: ev.actor,
                  }
                }
                if (nextTransfer) {
                  setTransferFx(nextTransfer)
                  clearTimeout(transferTimerRef.current)
                  transferTimerRef.current = setTimeout(() => setTransferFx(null), getTransferDuration(nextTransfer))
                }
              }

              if (newActions.length > 0) {
                const capped = newActions.slice(-2)
                actionQueueRef.current = [...capped.slice(1)]
                const playAction = (ev) => {
                  setActionFx({ key: `${ev.seq}-${Date.now()}`, ...ev })
                  clearTimeout(actionTimerRef.current)
                  actionTimerRef.current = setTimeout(() => {
                    const nextQueued = actionQueueRef.current.shift()
                    if (nextQueued) {
                      playAction(nextQueued)
                    } else {
                      setActionFx(null)
                    }
                  }, getActionDuration(ev))
                }
                playAction(capped[0])
              }

              if (latestEpic) {
                setEpicFx({ key: `${latestEpic.seq}-${Date.now()}`, ...latestEpic })
                clearTimeout(epicTimerRef.current)
                epicTimerRef.current = setTimeout(() => setEpicFx(null), getEpicDuration(latestEpic.card_type))
                setShake(true)
                clearTimeout(shakeTimerRef.current)
                shakeTimerRef.current = setTimeout(() => setShake(false), 600)
                playSfx(epicSfxForCard(latestEpic.card_type))
              }
            }
          }

          setView(nextView)
          setError('')
          setConnError('')
          setNameJoinErr('')
        } else if (msg.type === 'error') {
          const errText = msg.message || 'Lỗi'
          const errCode = msg.code || ''
          lastServerErrRef.current = { message: errText, code: errCode }
          setError(errText)
          setErrorNonce((n) => n + 1)
        }
      }

      ws.onclose = (ev) => {
        if (closed || leavingRef.current || ev.code === 1000) return
        if (TERMINAL_CLOSE_CODES.has(ev.code)) {
          const srv = lastServerErrRef.current
          const finalMsg = srv.message || terminalMessage(ev.code)
          const isNameTaken = srv.code === 'NAME_TAKEN'
            || (ev.code === 4401 && /tên đã có người dùng|name/i.test(finalMsg))

          // Nếu tên bị trùng khi đang vào qua link ?room=CODE -> cho đổi tên ngay tại chỗ
          if (!hasViewRef.current && isNameTaken) {
            removeSessionToken(code, name)
            setNameDraft(name)
            setNameJoinErr(finalMsg)
            setError('')
            setConnError('')
            setName('')
            setConnState('rejected')
            return
          }

          setConnState('rejected')
          setConnError(finalMsg)
          setError('')
          return
        }

        retryRef.current += 1
        setRetryCount(retryRef.current)
        if (retryRef.current > MAX_RETRIES) {
          setConnState('closed')
          setConnError('Không kết nối lại được — hãy thử kết nối lại hoặc tải lại trang.')
          return
        }
        setConnState('connecting')
        timer = setTimeout(connect, Math.min(1000 * retryRef.current, 5000))
      }

      ws.onopen = () => {
        retryRef.current = 0
        setRetryCount(0)
        setConnState('open')
        setConnError('')
      }
    }

    const initTimer = setTimeout(connect, 0)
  return () => {
      closed = true
      clearTimeout(initTimer)
      clearTimeout(timer)
      wsRef.current?.close()
    }
  }, [code, name, connectNonce])

  const me = view?.you || null
  const hand = me?.hand
  const lastPeekSigRef = useRef('')
  const peekCardsSig = (me?.peek || []).map((c, idx) => c?.id || `${c?.type || 'x'}-${idx}`).join('|')
  const peekSig = peekCardsSig ? `${me?.peek_meta?.seq ?? ''}:${peekCardsSig}` : ''
  useEffect(() => {
    if (peekSig && peekSig !== lastPeekSigRef.current) {
      lastPeekSigRef.current = peekSig
      setPeekOpen(true)
    } else if (!peekSig) {
      lastPeekSigRef.current = ''
      setPeekOpen(false)
    }
  }, [peekSig])
  const myPlayerEntry = useMemo(
    () => (view?.players || []).find((p) => p.name === name) || null,
    [view?.players, name],
  )
  const blindHandCount = me?.hand_count ?? myPlayerEntry?.count ?? 0

  const blindCards = useMemo(() => {
    if (!me?.blind) return []
    const raw = Array.isArray(me?.hand) ? me.hand : []
    if (raw.length > 0) {
      return raw.map((c, i) => ({
        ...c,
        id: c.id || `blind.${i}`,
        type: 'hidden',
        variant: 0,
        blind_index: typeof c.blind_index === 'number' ? c.blind_index : i,
      }))
    }
    return Array.from({ length: blindHandCount }, (_, i) => ({
      id: `blind.${i}`,
      type: 'hidden',
      variant: 0,
      blind_index: i,
    }))
  }, [me?.blind, me?.hand, blindHandCount])

  const activeHand = useMemo(
    () => (me?.blind ? blindCards : (me?.hand || [])),
    [me?.blind, blindCards, me?.hand],
  )

  // Tự dọn các ID đã rời tay khỏi selected
  useEffect(() => {
    if (!view?.you) {
      setSelected([])
      return
    }
    const ids = new Set(activeHand.map((c) => c.id))
    setSelected((prev) => {
      const next = prev.filter((id) => ids.has(id))
      if (me?.blind && next.length > 1) return next.slice(0, 1)
      return next.length === prev.length ? prev : next
    })
  }, [view?.you, activeHand, me?.blind])

  // bài mới trên tay -> animation "phát bài"
  useEffect(() => {
    if (!hand || me?.blind) {
      prevHandRef.current = null
      return undefined
    }
    const prev = prevHandRef.current
    prevHandRef.current = new Set(hand.map((c) => c.id))
    if (!prev) return undefined
    const fresh = hand.filter((c) => !prev.has(c.id))
    if (!fresh.length) return undefined
    setDealIds(new Set(fresh.map((c) => c.id)))
    const t = setTimeout(() => setDealIds(new Set()), 700)
  return () => clearTimeout(t)
  }, [hand, me?.blind])

  // bom vừa lật ra -> rung màn hình
  useEffect(() => {
    const rev = view?.revealed
    const prev = prevRevealedRef.current
    prevRevealedRef.current = rev ? rev.map((c) => c.id) : null
    if (!rev || !prev) return undefined
    if (rev.some((c) => !prev.includes(c.id)
      && (c.type === 'explodingkitten' || c.type === 'implodingkitten'))) {
      setShake(true)
      clearTimeout(shakeTimerRef.current)
      shakeTimerRef.current = setTimeout(() => setShake(false), 600)
      return undefined
    }
    return undefined
  }, [view?.revealed])

  // toast lỗi hành động tự ẩn sau 5s (lỗi mất kết nối connError giữ cố định không ẩn)
  useEffect(() => {
    if (!error || !view) return undefined
    const t = setTimeout(() => setError(''), 5000)
  return () => clearTimeout(t)
  }, [error, view])

  // Đồng bộ avatar mèo lên server ngay khi kết nối / tái kết nối hoặc khi người chơi vừa lưu mèo mới
  const lastAvatarSyncRef = useRef('')
  useEffect(() => {
    if (connState !== 'open' || !wsRef.current || wsRef.current.readyState !== 1) {
      lastAvatarSyncRef.current = ''
      return
    }
    if (!view || view.you?.spectator) return
    const sig = JSON.stringify(myAvatar)
    if (sig === lastAvatarSyncRef.current) return
    lastAvatarSyncRef.current = sig
    wsRef.current.send(JSON.stringify({ action: 'set_avatar', avatar: myAvatar }))
  }, [connState, myAvatar, view?.you?.spectator, !!view])

  const handleSaveAvatar = useCallback((next) => {
    const clean = saveAvatar(next)
    setMyAvatar(clean)
    showInfo('Đã cập nhật nhân vật mèo!')
  }, [showInfo])

  // list bộ bài để vote ở lobby
  useEffect(() => {
    listDeskDetails().then(setDesks).catch(() => {})
  }, [])

  // Issue #6: đếm ngược turn_timer mượt + tiếng tick ở 3, 2, 1 giây cuối
  const turnTimerKey = view?.phase === 'playing' && view?.turn_timer
    ? `${view.turn_timer.actor || ''}:${view.turn_timer.ends_ms || ''}:${view.turn?.current || ''}:${view.turn?.turns_left ?? 1}`
    : ''

  useEffect(() => {
    if (!turnTimerKey || view?.phase !== 'playing' || !view?.turn_timer) {
      setTurnSecLeft(null)
      return undefined
    }
    const tick = () => {
      const anchor = turnTimerAnchorRef.current
      if (!anchor) {
        setTurnSecLeft(null)
        return
      }
      const remMs = Math.max(0, anchor.localEndsAt - Date.now())
      const sec = Math.ceil(remMs / 1000)
      setTurnSecLeft(sec)
      if (sec >= 1 && sec <= 3) {
        const dedupeKey = `${anchor.key}:${sec}`
        if (lastTickKeyRef.current !== dedupeKey) {
          lastTickKeyRef.current = dedupeKey
          playSfx('tick')
        }
      }
    }
    tick()
    const id = setInterval(tick, 120)
    return () => clearInterval(id)
  }, [turnTimerKey, view?.phase, !!view?.turn_timer])

  // Issue #12: preload đồng bộ toàn bộ ảnh bộ bài trước khi vào ván
  const loadingImagesKey = view?.phase === 'loading'
    ? `${view.loading?.desk || ''}:${(view.loading?.images || []).join('|')}`
    : ''
  const alreadyLoadingReady = Boolean(
    view?.phase === 'loading' && Array.isArray(view.loading?.ready) && view.loading.ready.includes(name),
  )

  useEffect(() => {
    if (!connected) {
      loadingSentRef.current = false
    }
  }, [connected])

  useEffect(() => {
    if (view?.phase !== 'loading') {
      loadingSentRef.current = false
      setLoadProgress({ loaded: 0, total: 0, done: false })
      return undefined
    }

    loadingSentRef.current = false
    const rawImages = Array.isArray(view.loading?.images) ? view.loading.images : []
    const urls = Array.from(new Set(rawImages.filter(Boolean)))
    const total = urls.length

    if (total === 0) {
      setLoadProgress({ loaded: 0, total: 0, done: true })
      return undefined
    }

    let cancelled = false
    let completed = 0
    let finished = false
    setLoadProgress({ loaded: 0, total, done: false })

    const finishAll = () => {
      if (cancelled || finished) return
      finished = true
      setLoadProgress({ loaded: total, total, done: true })
    }

    const markOne = () => {
      if (cancelled || finished) return
      completed += 1
      setLoadProgress({ loaded: Math.min(completed, total), total, done: completed >= total })
      if (completed >= total) {
        finishAll()
      }
    }

    const safetyTimer = setTimeout(finishAll, 10000)

    for (const src of urls) {
      const img = new Image()
      img.decoding = 'async'
      let settled = false
      const settle = () => {
        if (settled) return
        settled = true
        markOne()
      }
      img.onload = () => {
        if (typeof img.decode === 'function') {
          img.decode().then(settle, settle)
        } else {
          settle()
        }
      }
      img.onerror = settle
      img.src = src
      if (img.complete) {
        if (typeof img.decode === 'function') {
          img.decode().then(settle, settle)
        } else {
          settle()
        }
      }
    }

    return () => {
      cancelled = true
      clearTimeout(safetyTimer)
    }
  }, [view?.phase, loadingImagesKey])

  useEffect(() => {
    if (view?.phase !== 'loading' || !loadProgress.done) return
    if (view?.you?.spectator || !connected || alreadyLoadingReady || loadingSentRef.current) return
    if (send({ action: 'assets_ready' })) {
      loadingSentRef.current = true
    }
  }, [view?.phase, loadProgress.done, view?.you?.spectator, connected, alreadyLoadingReady, send])

  const isSpectator = !!me?.spectator
  const roomCodeDisplay = view?.display_code || code

  // Hết lượt: giữ class sáng deck thêm ~450ms để CSS fade-out mượt
  const canDrawEarly = connected && !!view && !isSpectator && view.turn?.current === name
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

  const isMyTurn = !isSpectator && !!view && view.turn?.current === name && !!me?.alive && view.phase === 'playing'
  const myPending = !isSpectator && view?.pending && view.pending.owner === name ? view.pending : null
  const canDraw = connected && isMyTurn && !view?.pending && !view?.nope_window
  const deckGlow = canDraw || deckLit
  const givePending = !!myPending && myPending.kind === 'pick_card'
    && myPending.data?.source === 'own_hand'

  const displayedHand = useMemo(() => {
    const raw = me?.hand || []
    if (!raw.length) return raw
    const byId = new Map(raw.map((c) => [c.id, c]))
    const ordered = []
    for (const id of handOrder) {
      const card = byId.get(id)
      if (card) {
        ordered.push(card)
        byId.delete(id)
      }
    }
    for (const c of byId.values()) ordered.push(c)
    return ordered
  }, [me?.hand, handOrder])

  const selectedCardList = useMemo(
    () => activeHand.filter((c) => selected.includes(c.id)),
    [activeHand, selected],
  )
  const comboCheck = useMemo(() => validateCombo(me?.blind ? [] : selectedCardList), [me?.blind, selectedCardList])

  const canClairvoyance = Boolean(me?.can_clairvoyance)
  const hasClairvoyanceInHand = !me?.blind && (me?.hand || []).some((c) => c.type === 'clairvoyance')

  const canPlay = useCallback((card) => (
    connected && isMyTurn && !view?.pending && !view?.nope_window
      && card.type !== 'nope' && !UNPLAYABLE_TYPES.includes(card.type)
      && (card.type !== 'clairvoyance' || canClairvoyance)
  ), [connected, isMyTurn, view?.pending, view?.nope_window, canClairvoyance])

  const playOne = useCallback((card, forceNow = false) => {
    if (!connected) {
      setError('Mất kết nối tới phòng — thao tác chưa được gửi.')
      return
    }
    if (me?.blind || card.type === 'hidden') {
      if (canDraw) {
        send({ action: 'play', card_id: card.id })
        setSelected([])
      }
      return
    }
    if (card.type === 'godcat') {
      setGodcatNow(forceNow || !canPlay(card))
      setGodcatCard(card)
      setSelected([])
      return
    }
    if (!forceNow && canPlay(card)) send({ action: 'play', card_id: card.id })
    else send({ action: 'play_now', card_id: card.id })
    setSelected([])
  }, [connected, me?.blind, canDraw, canPlay, send])

  const tryPlaySelected = useCallback(() => {
    if (!selectedCardList.length) return
    if (!connected) {
      setError('Mất kết nối tới phòng — thao tác chưa được gửi.')
      return
    }
    if (me?.blind) {
      const picked = selectedCardList[0]
      if (picked) {
        send({ action: 'play', card_id: picked.id })
        setSelected([])
      }
      return
    }
    if (selectedCardList.length >= 2) {
      if (comboCheck.valid && comboCheck.combo) {
        send({
          action: 'combo',
          combo: comboCheck.combo,
          card_ids: selectedCardList.map((c) => c.id),
        })
        setSelected([])
        return
      }
      setError(comboCheck.error || 'Combo không hợp lệ.')
      return
    }
    const only = selectedCardList[0]
    if (only.type === 'nope' || UNPLAYABLE_TYPES.includes(only.type)) {
      setError('Lá này không đánh lẻ được — Nope chỉ dùng trong cửa sổ Nope, mèo đánh theo combo, bom/giải không đánh trực tiếp.')
      return
    }
    playOne(only)
  }, [selectedCardList, connected, me?.blind, comboCheck, send, playOne])

  // Phím tắt: Esc, D (rút), Enter (đánh lá đã chọn), N/P (Nope/Pass)
  useEffect(() => {
    const onKeyDown = (e) => {
      const tag = e.target?.tagName
      const inField = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target?.isContentEditable
      if (e.key === 'Escape') {
        if (zoom || graveList || godcatCard) {
          setZoom(null)
          setGraveList(false)
          setGodcatCard(null)
          setGodcatNow(false)
          return
        }
        if (selected.length > 0) setSelected([])
        return
      }
      if (inField || zoom || graveList || godcatCard || isSpectator) return

      const key = e.key.toLowerCase()
      const nw = view?.nope_window
      if (nw && connected && me?.alive) {
        const isActor = nw.actor === name
        const canActNope = (!isActor || (nw.stacked ?? 0) > 0) && !nw.you_responded
        if (canActNope) {
          const hasNope = me.blind || (me.hand || []).some((c) => c.type === 'nope')
          if (key === 'n' && hasNope) {
            e.preventDefault()
            send({ action: 'nope' })
            return
          }
          if (key === 'p') {
            e.preventDefault()
            send({ action: 'pass_nope' })
            return
          }
        }
      }

      if (key === 'd' && canDraw) {
        e.preventDefault()
        send({ action: 'draw' })
      } else if (e.key === 'Enter' && canDraw && selectedCardList.length > 0 && !givePending) {
        e.preventDefault()
        tryPlaySelected()
      }
    }
    window.addEventListener('keydown', onKeyDown)
  return () => window.removeEventListener('keydown', onKeyDown)
  }, [
    zoom, graveList, godcatCard, isSpectator, selected.length, view?.nope_window, connected,
    me, name, canDraw, selectedCardList.length, givePending, send, tryPlaySelected,
  ])

  const playerNames = useMemo(() => (view?.players || []).map((p) => p.name), [view?.players])

  function handleReconnectNow() {
    retryRef.current = 0
    setRetryCount(0)
    setConnError('')
    setError('')
    setConnectNonce((n) => n + 1)
  }

  function handleLeaveRoom() {
    leavingRef.current = true
    if ((isSpectator || view?.phase === 'lobby' || view?.phase === 'ended') && connected && wsRef.current?.readyState === 1) {
      removeSessionToken(code, name)
      if (roomCodeDisplay !== code) removeSessionToken(roomCodeDisplay, name)
      try {
        wsRef.current.send(JSON.stringify({ action: 'leave' }))
      } catch { /* bỏ qua */ }
      setTimeout(() => { location.href = '/' }, 80)
      return
    }
    location.href = '/'
  }

  function handleCopyCode() {
    copyToClipboard(roomCodeDisplay)
      .then(() => showInfo(`Đã sao chép mã phòng ${roomCodeDisplay}`))
      .catch(() => showInfo(`Mã phòng: ${roomCodeDisplay}`))
  }

  function handleCopyLink() {
    const url = `${location.origin}/?room=${encodeURIComponent(roomCodeDisplay)}`
    copyToClipboard(url)
      .then(() => showInfo('Đã sao chép link mời vào phòng!'))
      .catch(() => showInfo(url))
  }

  function toggleMute() {
    const next = !muted
    setMutedState(next)
    setMuted(next)
    showInfo(next ? 'Đã tắt âm thanh' : 'Đã bật âm thanh')
  }

  // Link phòng mở tab mới (hoặc tên bị trùng 4401) -> hỏi tên ngay tại đây
  if (!name) {
  return (
      <div className="room room-join">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            const v = nameDraft.trim()
            if (!v) {
              setNameJoinErr('Vui lòng nhập tên của bạn.')
              return
            }
            setNameJoinErr('')
            setError('')
            setConnError('')
            store.set('ek_name', v)
            setName(v)
          }}
        >
          <p>Vào phòng <b>{code}</b> — bạn tên gì?</p>
          {nameJoinErr && <p className="error" role="alert">{nameJoinErr}</p>}
          <input
            aria-label="Tên của bạn"
            value={nameDraft}
            onChange={(e) => { setNameDraft(e.target.value); if (nameJoinErr) setNameJoinErr('') }}
            placeholder="Tên của bạn"
            maxLength={64}
            autoFocus
          />
          <div className="room-join-actions">
            <button type="submit" className="primary">Vào phòng</button>
            <button type="button" onClick={() => { location.href = '/' }}>Về trang chủ</button>
          </div>
        </form>
      </div>
    )
  }

  if (!view && !connError && !error) {
  return (
      <div className="room loading" role="status" aria-live="polite">
        Đang kết nối tới phòng <b>{code}</b>…
        {retryCount > 0 && ` (thử lại ${retryCount}/${MAX_RETRIES})`}
      </div>
    )
  }

  if (!view && (connError || error)) {
  return (
      <div className="room loading" role="alert">
        <p className="loading-err">{connError || error}</p>
        <div className="loading-actions">
          <button type="button" className="primary" onClick={handleReconnectNow}>Thử kết nối lại</button>
          <button
            type="button"
            onClick={() => {
              setNameDraft(name)
              setError('')
              setConnError('')
              setNameJoinErr('')
              setName('')
            }}
          >
            Đổi tên
          </button>
          <button type="button" onClick={() => { location.href = '/' }}>Về trang chủ</button>
        </div>
      </div>
    )
  }

  function toggleSelect(id) {
    if (!me?.alive) return
    if (me?.blind) {
      setSelected((sel) => (sel.includes(id) ? [] : [id]))
      return
    }
    setSelected((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]))
  }

  function canPlayToTable(card) {
    if (!connected) return false
    if (givePending) return false
    if (me.blind) return canDraw
    if (card.type === 'clairvoyance') {
      return canClairvoyance && !view.nope_window
    }
    return canPlay(card)
      || (me.alive && ANYTIME_TYPES.includes(card.type) && !view.nope_window && !view.pending)
  }

  function startDrag(e, card) {
    if (e.button !== 0 || drag) return
    const giveMode = !!givePending && !!me.alive
    const blindMode = !!me.blind
    const allowTablePlay = !giveMode && canPlayToTable(card)
    if (!me.alive && !giveMode && !allowTablePlay) return
    // Khi bị mù chỉ kéo để đánh/đưa lá, không đổi thứ tự slot úp
    if (blindMode && !giveMode && !allowTablePlay) return

    const sx = e.clientX
    const sy = e.clientY
    const slots = !blindMode && handRef.current ? Array.from(handRef.current.children) : []
    const slotCenters = slots.map((el) => {
      const b = el.getBoundingClientRect()
      return b.left + b.width / 2
    })
    let currentOrder = displayedHand.map((c) => c.id)

    let started = false
    let overTable = false
    let overHo = false

    const cleanup = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', cancel)
      dragCleanupRef.current = null
    }

    const move = (ev) => {
      if (!started) {
        if (Math.hypot(ev.clientX - sx, ev.clientY - sy) < 7) return
        started = true
        dragStartedRef.current = true
      }
      const r = tableRef.current?.getBoundingClientRect()
      overTable = allowTablePlay && !!r && ev.clientX >= r.left && ev.clientX <= r.right
        && ev.clientY >= r.top && ev.clientY <= r.bottom
      const ho = giveMode ? document.getElementById('handout-drop') : null
      const hr = ho?.getBoundingClientRect()
      overHo = giveMode && !!hr && ev.clientX >= hr.left && ev.clientX <= hr.right
        && ev.clientY >= hr.top && ev.clientY <= hr.bottom

      if (!blindMode && !overTable && !overHo && slotCenters.length > 1) {
        let targetIdx = 0
        let bestDist = Infinity
        for (let k = 0; k < slotCenters.length; k++) {
          const d = Math.abs(ev.clientX - slotCenters[k])
          if (d < bestDist) {
            bestDist = d
            targetIdx = k
          }
        }
        const curIdx = currentOrder.indexOf(card.id)
        if (curIdx !== -1 && targetIdx !== curIdx) {
          const next = currentOrder.slice()
          next.splice(curIdx, 1)
          next.splice(targetIdx, 0, card.id)
          currentOrder = next
          setHandOrder(next)
        }
      }

      setDrag({ card, x: ev.clientX, y: ev.clientY, over: overTable || overHo, overHo })
    }

    const up = () => {
      cleanup()
      if (!started) return
      if (giveMode) {
        if (overHo) {
          send({ action: 'respond', payload: { card_id: card.id } })
          setSelected([])
        }
      } else if (overTable) {
        playOne(card)
      }
      setDrag(null)
    }

    const cancel = () => {
      cleanup()
      dragStartedRef.current = false
      setDrag(null)
    }

    dragCleanupRef.current = cleanup
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', cancel)
  }

  function tilt(e) {
    if (viewportW <= 900 || drag || !me?.alive) return
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

  // Tính overlap linh hoạt theo kích thước thẻ & viewport (khớp --card-w)
  const isMobile = viewportW <= 900
  const cardWidthPx = isMobile ? 92 : 164
  const handCountForLayout = me.blind ? blindCards.length : displayedHand.length
  const maxHandSpan = Math.max(260, viewportW - (isMobile ? 24 : 96))
  let overlapPx = isMobile ? -12 : -24
  if (handCountForLayout > 1) {
    const naturalGap = handCountForLayout > 9 ? -0.32 : handCountForLayout > 6 ? -0.22 : -0.14
    const fitStep = (maxHandSpan - cardWidthPx) / (handCountForLayout - 1)
    const fitOverlap = fitStep - cardWidthPx
    overlapPx = Math.round(Math.min(cardWidthPx * naturalGap, fitOverlap))
    // Không chồng quá 68% chiều rộng thẻ để luôn bấm được
    overlapPx = Math.max(overlapPx, -Math.round(cardWidthPx * 0.68))
  }

  const singleSelected = selectedCardList.length === 1 ? selectedCardList[0] : null
  const singleUnplayable = singleSelected
    && (singleSelected.type === 'nope' || UNPLAYABLE_TYPES.includes(singleSelected.type))
  const canSubmitSelected = selectedCardList.length === 1
    ? !singleUnplayable
    : comboCheck.valid

  const turnsLeft = view.turn?.turns_left ?? 1
  const hasGrave = (view.grave?.length || 0) > 0
  const isOracleOpen = Boolean((me.peek?.length > 0 && peekOpen) || (myPending && view.pending?.kind === 'reorder'))
  const isUnderAttack = Boolean(isMyTurn && turnsLeft > 1)

  const hasDeadAnytime = !me.alive && !me.blind && (me.hand || []).some(
    (c) => (c.type === 'clairvoyance' && canClairvoyance && !view.nope_window)
      || (c.type === 'feedthedead' && !view.pending && !view.nope_window),
  )
  const isDeadLocked = !me.alive && !hasDeadAnytime

  return (
    <div className={`room ${shake ? 'shake' : ''}`}>
      <header className="topbar">
        <div className="room-code-group">
          <button
            type="button"
            className="code-badge"
            title="Bấm để sao chép mã phòng"
            onClick={handleCopyCode}
          >
            {roomCodeDisplay}
          </button>
          <button
            type="button"
            className="icon-btn"
            aria-label="Sao chép link mời"
            title="Sao chép link mời"
            onClick={handleCopyLink}
          >
            <UiSvg name="link" size={16} />
          </button>
        </div>

        <PlayerList
          players={view.players}
          turn={view.turn}
          phase={view.phase}
          meName={name}
          towerWearer={view.tower_wearer}
          catalog={catalog}
          onInspectCard={setZoom}
          onEditAvatar={isSpectator ? null : () => setCatModalOpen(true)}
        />

        <div className="topbar-right">
          {view.phase !== 'lobby' && (view.stash_count ?? 0) > 0 && (
            <span className="meta-info" title="Số lá dưới vương miện Tower of Power">
              <RealIcon name="crown" size={15} /> <b>{view.stash_count}</b>
            </span>
          )}
          <span
            className={`conn-pill ${connected ? 'ok' : connState === 'connecting' ? 'retrying' : 'bad'}`}
            role="status"
            title={connected ? 'Đã kết nối' : connState === 'connecting' ? 'Đang kết nối lại' : 'Mất kết nối'}
          >
            <i className="conn-dot" aria-hidden="true" />
            <span className="conn-label">
              {connected
                ? 'Kết nối'
                : connState === 'connecting'
                  ? `Thử lại${retryCount ? ` (${retryCount})` : ''}`
                  : 'Mất kết nối'}
            </span>
          </span>
          {view?.debug_enabled && (
            <button
              type="button"
              className="icon-btn debug-entry-btn"
              title="Mở Debug Studio (tab mới)"
              aria-label="Mở Debug Studio"
              onClick={() => window.open(`/?debug=1&room=${encodeURIComponent(roomCodeDisplay)}`, '_blank', 'noopener')}
            >
              <UiSvg name="wrench" size={16} />
            </button>
          )}
          <button
            type="button"
            className="icon-btn"
            aria-label={muted ? 'Bật âm thanh' : 'Tắt âm thanh'}
            title={muted ? 'Bật âm thanh' : 'Tắt âm thanh'}
            onClick={toggleMute}
          >
            <UiSvg name={muted ? 'sound-off' : 'sound-on'} size={16} />
          </button>
          {view.phase !== 'lobby' && view.phase !== 'loading' && (
            <>
              <button
                type="button"
                className={`icon-btn desktop-log-btn ${!logCollapsed ? 'active' : ''}`}
                aria-label={logCollapsed ? 'Hiện nhật ký bàn chơi' : 'Thu gọn nhật ký bàn chơi'}
                title={logCollapsed ? 'Hiện nhật ký' : 'Thu gọn nhật ký'}
                onClick={() => setLogCollapsed((c) => !c)}
              >
                <UiSvg name="log" size={16} />
              </button>
              <button
                type="button"
                className={`icon-btn mobile-only-btn ${mobileLogOpen ? 'active' : ''}`}
                aria-label="Mở nhật ký ván đấu"
                title="Nhật ký ván đấu"
                onClick={() => setMobileLogOpen((o) => !o)}
              >
                <UiSvg name="log" size={16} />
              </button>
            </>
          )}
          <button type="button" className="leave" onClick={handleLeaveRoom}>Rời phòng</button>
        </div>
      </header>

      {/* Banner cố định khi mất kết nối sau khi đã vào phòng */}
      {connError && (
        <div className="conn-banner" role="alert" aria-live="assertive">
          <span><RealIcon name="nope" size={18} /> {connError}</span>
          <div className="conn-banner-actions">
            <button type="button" className="primary" onClick={handleReconnectNow}>Kết nối lại</button>
            <button type="button" onClick={() => { location.href = '/' }}>Về trang chủ</button>
          </div>
        </div>
      )}

      {isSpectator && view.phase !== 'lobby' && (
        <div className="spectator-banner" role="status" aria-live="polite">
          <span className="spectator-banner-main">
            <span className="spectator-pill-tag">Khán giả</span>
            <span>Chế độ khán giả — Đang xem ván (sẽ tham gia ở ván sau)</span>
          </span>
          {(view.spectator_count ?? 0) > 0 && (
            <span className="spectator-count-tag">{view.spectator_count} người đang xem</span>
          )}
        </div>
      )}

      {view.phase === 'lobby' && (
        <LobbyPanel
          code={roomCodeDisplay}
          players={view.players}
          desks={desks}
          votes={view.votes}
          name={name}
          connected={connected}
          onVoteDesk={(desk) => send({ action: 'vote_desk', desk })}
          onStart={() => send({ action: 'start', preload: true })}
          onCopyCode={handleCopyCode}
          onCopyLink={handleCopyLink}
          onEditAvatar={() => setCatModalOpen(true)}
        />
      )}

      {view.phase === 'loading' && (() => {
        const loadingPlayers = Array.isArray(view.loading?.players) ? view.loading.players : []
        const loadingReadySet = new Set(Array.isArray(view.loading?.ready) ? view.loading.ready : [])
        const deskMeta = desks.find((d) => d.id === view.loading?.desk)
        const total = loadProgress.total
        const loaded = Math.min(loadProgress.loaded, total)
        const pct = total > 0 ? Math.round((loaded / total) * 100) : 100
        return (
          <section className="loading-stage" aria-label="Đang chuẩn bị ván đấu">
            <div className="loading-card" role="status" aria-live="polite">
              <div className="loading-card-head">
                <span className="lobby-eyebrow">Phòng {roomCodeDisplay} · Chuẩn bị bộ bài</span>
                <h2>Đang tải bộ bài {deskMeta?.title || view.loading?.desk || ''}…</h2>
                <p>
                  {isSpectator
                    ? 'Các người chơi đang tải hình ảnh trước khi bắt đầu ván mới.'
                    : loadProgress.done
                      ? 'Đã tải xong — đang chờ người chơi khác sẵn sàng…'
                      : 'Đang nạp trước hình ảnh thẻ bài để chơi mượt không giật khung.'}
                </p>
              </div>
              <div className="loading-progress-wrap">
                <div className="loading-progress-meta">
                  <span>{total > 0 ? `Đã tải ${loaded} / ${total} ảnh` : 'Sẵn sàng'}</span>
                  <span className="loading-progress-pct">{pct}%</span>
                </div>
                <div className="loading-progress-track" aria-hidden="true">
                  <div className="loading-progress-fill" style={{ width: `${pct}%` }} />
                </div>
              </div>
              {loadingPlayers.length > 0 && (
                <div className="loading-players" aria-label="Trạng thái người chơi">
                  {loadingPlayers.map((pn) => {
                    const ready = loadingReadySet.has(pn)
                    return (
                      <span key={pn} className={`loading-player-pill ${ready ? 'ready' : ''}`}>
                        <i className="loading-player-dot" aria-hidden="true" />
                        {pn}{ready ? ' · Sẵn sàng' : ' · Đang tải…'}
                      </span>
                    )
                  })}
                </div>
              )}
            </div>
          </section>
        )
      })()}

      {view.phase === 'ended' && !endedDismissed && (
        <div className="zoom-overlay ended-overlay" role="dialog" aria-modal="true" aria-label="Kết thúc ván đấu">
          <div className="ended-modal">
            <div className="ended-trophy" aria-hidden="true">
              <RealIcon name="trophy" size={64} />
            </div>
            <h2>{view.winner ? `${view.winner} THẮNG!` : 'Ván đấu kết thúc!'}</h2>
            <p className="ended-sub">
              {isSpectator
                ? 'Bạn đang xem với tư cách khán giả — chờ người chơi bắt đầu ván mới để cùng tham gia.'
                : view.winner === name
                  ? 'Chúc mừng bạn sống sót cuối cùng!'
                  : 'Chọn chơi ván mới ngay hoặc quay về sảnh để đổi bộ bài.'}
            </p>
            <div className="ended-actions">
              {!isSpectator && (
                <>
                  <button
                    type="button"
                    className="primary"
                    disabled={!connected}
                    onClick={() => send({ action: 'rematch', preload: true })}
                  >
                    ↻ Chơi lại
                  </button>
                  <button
                    type="button"
                    disabled={!connected}
                    onClick={() => send({ action: 'return_lobby' })}
                  >
                    ← Về sảnh
                  </button>
                </>
              )}
              <button type="button" onClick={() => setEndedDismissed(true)}>
                <RealIcon name="peek" size={16} /> Xem bàn
              </button>
              <button type="button" className="leave" onClick={handleLeaveRoom}>
                Trang chủ
              </button>
            </div>
          </div>
        </div>
      )}

      {view.phase === 'ended' && endedDismissed && (
        <div className="ended-pill-bar">
          <span><RealIcon name="trophy" size={18} /> {view.winner || 'Không ai'} thắng</span>
          <button type="button" className="primary" onClick={() => setEndedDismissed(false)}>
            Mở bảng kết quả
          </button>
        </div>
      )}

      <NopeBar
        window={view.nope_window}
        name={name}
        send={send}
        alive={!!me.alive && !isSpectator}
        hasNope={me.blind || (me.hand || []).some((c) => c.type === 'nope')}
        isBlind={!!me.blind}
        errorNonce={errorNonce}
        connected={connected}
        catalog={catalog}
        onInspectCard={setZoom}
      />

      {view.phase !== 'lobby' && view.phase !== 'loading' && (
      <div className={`main-cols ${logCollapsed ? 'log-collapsed' : ''} ${isSpectator ? 'is-spectator' : ''}`}>
        <div
          ref={tableRef}
          className={`table ${isMyTurn ? 'my-turn' : ''} ${isUnderAttack ? 'under-attack' : ''} ${view.nope_window ? 'nope-active' : ''} ${isOracleOpen ? 'oracle-active' : ''} ${drag ? (drag.over ? 'drag-over' : 'drag-hint') : ''}`}
        >
          <div className="table-spotlight" aria-hidden="true" />

          {view.phase === 'playing' && view.turn?.current && (
            <div className="turn-hud" role="status" aria-live="polite">
              <span className={`turn-who ${isMyTurn ? 'mine' : ''}`}>
                <i className="turn-dot" aria-hidden="true" />
                {isMyTurn ? 'Lượt của bạn' : `Lượt ${view.turn.current}`}
                {turnsLeft > 1 && <span className="turn-multi">×{turnsLeft}</span>}
              </span>
              <span className="turn-dir">
                {view.turn.direction === -1 ? '← Ngược chiều' : 'Thuận chiều →'}
              </span>
              {(view.stash_count ?? 0) > 0 && view.tower_wearer && (
                <span className="turn-tower">
                  <RealIcon name="crown" size={13} /> {view.tower_wearer}
                </span>
              )}
              {turnSecLeft !== null && (
                <span
                  className={`turn-timer-badge ${turnSecLeft <= 3 ? 'urgent' : turnSecLeft <= 8 ? 'warn' : ''}`}
                  title="Thời gian còn lại của lượt"
                >
                  {turnSecLeft}s
                </span>
              )}
            </div>
          )}

          {turnBanner && view.phase === 'playing' && (
            <div
              key={turnBanner.key}
              className={`turn-banner ${turnBanner.isMine ? 'mine' : 'other'}`}
              aria-live="polite"
            >
              <span className="turn-banner-eyebrow">
                {turnBanner.isMine ? 'YOUR TURN' : 'TURN CHANGE'}
              </span>
              <div className="turn-banner-title">
                {turnBanner.isMine ? 'TỚI LƯỢT BẠN!' : `Tới lượt ${turnBanner.actor}`}
                {turnBanner.turnsLeft > 1 && (
                  <span className="turn-banner-multi">×{turnBanner.turnsLeft} lượt</span>
                )}
              </div>
            </div>
          )}

          {(view.playmat || []).length > 0 && (
            <div className="playmat-corner">
              {(view.playmat || []).map((e) => (
                <button
                  key={e.card.id}
                  type="button"
                  className={`playmat-card-btn fx-${e.card.type}`}
                  title={`Xem chi tiết ${getCardName(catalog, e.card.type, e.card.variant)}`}
                  onClick={() => setZoom(e.card)}
                >
                  <CardView small card={e.card} label={e.name !== '-' ? e.name : ''} catalog={catalog} />
                </button>
              ))}
            </div>
          )}

          <div className="table-top">
            <div className="pile-col">
              <div
                ref={deckRef}
                role="button"
                tabIndex={canDraw ? 0 : -1}
                aria-disabled={!canDraw}
                aria-label={canDraw ? `Rút thẻ từ deck (còn ${view.deck_count} lá). Phím tắt D.` : `Deck còn ${view.deck_count} lá`}
                className={`pile deck ${deckGlow ? 'can-draw' : ''}`}
                title={canDraw ? 'Bấm để rút thẻ (phím D)' : `Deck còn ${view.deck_count}`}
                onClick={() => canDraw && send({ action: 'draw' })}
                onKeyDown={(e) => {
                  if (canDraw && (e.key === 'Enter' || e.key === ' ')) {
                    e.preventDefault()
                    send({ action: 'draw' })
                  }
                }}
              >
                {view.deck_top
                  ? <CardView small card={view.deck_top} catalog={catalog} />
                  : <div className="card-back" />}
                <span>{view.deck_count}</span>
              </div>
              {canDraw && <div className="pile-hotkey">[D]</div>}
              <div className="pile-caption">DECK · {view.deck_count}</div>
            </div>

            <div className="pile-col discard-col">
              <div
                role={hasGrave ? 'button' : undefined}
                tabIndex={hasGrave ? 0 : -1}
                aria-label={hasGrave ? `Mở danh sách ${view.grave.length} thẻ đã đánh` : 'Khu vực đánh bài'}
                className={`midfield ${hasGrave ? 'clickable' : ''}`}
                title={hasGrave ? `Bấm để xem ${view.grave.length} thẻ đã đánh` : ''}
                onClick={() => hasGrave && setGraveList(true)}
                onKeyDown={(e) => {
                  if (hasGrave && (e.key === 'Enter' || e.key === ' ')) {
                    e.preventDefault()
                    setGraveList(true)
                  }
                }}
              >
                {(view.grave_top || []).map((c, i) => {
                  let h = 2166136261
                  const key = `${c.id}-${c.type}`
                  for (let k = 0; k < key.length; k++) {
                    h ^= key.charCodeAt(k)
                    h = Math.imul(h, 16777619)
                  }
                  h = Math.imul(h ^ (h >>> 15), 2246822519) >>> 0
                  const r = (h % 69) - 34
                  const maxDx = isMobile ? 42 : Math.min(130, Math.max(70, Math.round(viewportW * 0.1)))
                  const maxDy = isMobile ? 24 : 58
                  const dx = ((h >>> 8) % (maxDx * 2 + 1)) - maxDx
                  const dy = ((h >>> 16) % (maxDy * 2 + 1)) - maxDy
  return (
                    <div
                      key={c.id}
                      className={`grave-card fx-${c.type}`}
                      style={{
                        transform: `translate(${dx}px, ${dy}px) rotate(${r}deg)`,
                        zIndex: (view.grave_top.length - i),
                      }}
                    >
                      <CardView small card={c} catalog={catalog} />
                    </div>
                  )
                })}
                <CardSlamHand slam={slam} />
              </div>
            </div>
          </div>

          <RevealedFutureStrip cards={view.revealed} catalog={catalog} onInspectCard={setZoom} />

          <BombRadarStrip positions={me.bomb_positions} deckCount={view.deck_count} />
          {me.illtake_by && (
            <div className="bomb-info trap-banner">
              <RealIcon name="trap" size={16} /> Lá rút kế tiếp của bạn thuộc về <b>{me.illtake_by}</b>!
            </div>
          )}
          <FutureVisionPanel
            cards={me.peek}
            peekMeta={me.peek_meta}
            open={peekOpen}
            onToggle={() => setPeekOpen((o) => !o)}
            catalog={catalog}
            onInspectCard={setZoom}
          />
          <CardTransferFx fx={transferFx} catalog={catalog} />
          <ActionCutscene fx={actionFx} />
        </div>

        <div className={`side-col ${mobileLogOpen ? 'mobile-open' : ''}`}>
          <ActionLog
            logEntries={view.log_entries}
            legacyLog={view.log}
            playerNames={playerNames}
            catalog={catalog}
            mobileOpen={mobileLogOpen}
            onCloseMobile={() => setMobileLogOpen(false)}
            onHide={() => setLogCollapsed(true)}
          />
        </div>
      </div>
      )}

      <PendingPanel
        pending={view.pending}
        mine={!!myPending}
        send={send}
        connected={connected}
        overHo={!!drag?.overHo}
        isBlind={!!me.blind}
        canClairvoyance={canClairvoyance && hasClairvoyanceInHand}
        catalog={catalog}
        peekCards={me.peek}
        onInspectCard={setZoom}
      />

      {/* give pending khi bấm chọn lá thay vì kéo-thả (hỗ trợ cả lúc bị mù) */}
      {givePending && selectedCardList.length > 0 && (
        <div className="actions">
          <div className="actions-group">
            <button
              type="button"
              className="primary"
              disabled={!connected}
              onClick={() => {
                send({ action: 'respond', payload: { card_id: selectedCardList[0].id } })
                setSelected([])
              }}
            >
              {myPending?.data?.reason === 'blind_defuse'
                ? `Thử lật lá úp #${(selectedCardList[0].blind_index ?? 0) + 1}`
                : me.blind
                  ? `Đưa lá úp #${(selectedCardList[0].blind_index ?? 0) + 1}`
                  : `Đưa lá đã chọn (${getCardName(catalog, selectedCardList[0].type, selectedCardList[0].variant)})`}
            </button>
            <button type="button" onClick={() => setSelected([])}>Bỏ chọn</button>
          </div>
        </div>
      )}

      {/* Bị mù trên lượt mình: bấm chọn 1 lá úp để đánh */}
      {canDraw && !givePending && me.blind && selectedCardList.length > 0 && (
        <div className="actions">
          <div className="actions-group">
            <button
              type="button"
              className="primary"
              disabled={!connected}
              title="Phím tắt: Enter"
              onClick={() => {
                send({ action: 'play', card_id: selectedCardList[0].id })
                setSelected([])
              }}
            >
              Đánh lá úp #{(selectedCardList[0].blind_index ?? 0) + 1}
            </button>
            <button type="button" onClick={() => setSelected([])}>Bỏ chọn</button>
          </div>
        </div>
      )}

      {/* Thanh hành động chọn bài / combo trên lượt mình */}
      {canDraw && !givePending && !me.blind && selectedCardList.length > 0 && (
        <div className="actions">
          <div className="actions-group">
            <button
              type="button"
              className="primary"
              disabled={!canSubmitSelected}
              title={!canSubmitSelected ? (comboCheck.error || 'Lá này không đánh lẻ được') : 'Phím tắt: Enter'}
              onClick={tryPlaySelected}
            >
              {selectedCardList.length === 1
                ? `Đánh ${getCardName(catalog, selectedCardList[0].type, selectedCardList[0].variant)}`
                : comboCheck.valid
                  ? `Đánh combo ${selectedCardList.length} lá`
                  : selectedCardList.length > 3
                    ? 'Tối đa 3 lá'
                    : 'Combo chưa hợp lệ'}
            </button>
            <button type="button" onClick={() => setSelected([])}>Bỏ chọn</button>
          </div>
          {comboCheck.valid && <span className="combo-hint ok">✓ {comboCheck.hint}</span>}
          {selectedCardList.length >= 2 && !comboCheck.valid && (
            <span className="combo-hint err">{comboCheck.error}</span>
          )}
          {singleUnplayable && (
            <span className="combo-hint err">Lá này không đánh lẻ được (chọn thêm lá cùng loại để đánh combo).</span>
          )}
        </div>
      )}

      {error && (
        <div className="error-toast" role="alert" aria-live="assertive">
          {error}
        </div>
      )}

      {infoToast && (
        <div className="info-toast" role="status" aria-live="polite">
          {infoToast}
        </div>
      )}

      {!isSpectator && view.phase !== 'lobby' && view.phase !== 'loading' && (
      <div
        className={`hand-area ${me.blind ? 'blind' : ''} ${!me.alive ? 'dead' : ''} ${isDeadLocked ? 'dead-locked' : ''}`.trim()}
      >
        {(me.blind || me.marked) && (
          <div className="hand-status-strip">
            {me.blind && (
              <span className="hand-status-badge blind-badge">
                <RealIcon name="blind" size={16} /> BỊ MÙ — tự chọn 1 lá úp để đánh
              </span>
            )}
            {me.marked && (
              <span className="hand-status-badge mark-badge">
                <RealIcon name="pin" size={15} /> Bị Mark: {getCardName(catalog, me.marked.type, me.marked.variant)}
              </span>
            )}
          </div>
        )}
        {!me.alive && (
          <div className="dead-note" role="status">
            <RealIcon name="skull" size={15} /> RIP
          </div>
        )}

        <div ref={handRef} className="hand">
          {me.blind ? (
            blindCards.map((c, i) => {
              const n = blindCards.length
              const mid = (n - 1) / 2
              const off = i - mid
              const angle = isMobile
                ? (n > 8 ? 1.0 : 1.8)
                : (n > 10 ? 1.4 : 2.6)
              const curve = isMobile
                ? (n > 8 ? 0.3 : 0.7)
                : (n > 10 ? 0.6 : 1.5)
              const slotNum = (c.blind_index ?? i) + 1
              const isSelected = selected.includes(c.id)
  return (
                <div
                  key={c.id}
                  className="hand-slot"
                  style={{
                    transform: `rotate(${off * angle}deg) translateY(${off * off * curve}px)`,
                    marginLeft: i ? overlapPx : 0,
                    zIndex: i,
                  }}
                >
                  <div
                    role="button"
                    tabIndex={isDeadLocked ? -1 : 0}
                    aria-disabled={isDeadLocked || undefined}
                    aria-pressed={isSelected}
                    aria-label={`Lá úp #${slotNum}${isSelected ? ' (đã chọn)' : ''}`}
                    className={`hand-card blind-card ${isSelected ? 'selected' : ''} ${drag?.card.id === c.id ? 'dragging' : ''}`}
                    onPointerDown={(e) => startDrag(e, c)}
                    onMouseMove={tilt}
                    onMouseLeave={untilt}
                    onClick={() => {
                      if (dragStartedRef.current) { dragStartedRef.current = false; return }
                      toggleSelect(c.id)
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        toggleSelect(c.id)
                      }
                    }}
                  >
                    <div>
                      <div className="card">
                        <div className="card-back" />
                        <span className="blind-slot-num">#{slotNum}</span>
                      </div>
                    </div>
                    {canDraw && (
                      <button
                        type="button"
                        className="quick"
                        onPointerDown={(e) => e.stopPropagation()}
                        onClick={(e) => {
                          e.stopPropagation()
                          send({ action: 'play', card_id: c.id })
                          setSelected([])
                        }}
                      >
                        Đánh
                      </button>
                    )}
                  </div>
                </div>
              )
            })
          ) : (
            displayedHand.map((c, i) => {
              const n = displayedHand.length
              const mid = (n - 1) / 2
              const off = i - mid
              const angle = isMobile
                ? (n > 8 ? 1.0 : 1.8)
                : (n > 12 ? 1.4 : n > 9 ? 2.0 : n > 6 ? 2.6 : 3.4)
              const curve = isMobile
                ? (n > 8 ? 0.3 : 0.7)
                : (n > 12 ? 0.6 : n > 9 ? 1.0 : n > 6 ? 1.5 : 2.1)
              const isSelected = selected.includes(c.id)
              const playableNow = canPlay(c)
              const anytimeOffTurn = connected && !view.nope_window && (
                c.type === 'clairvoyance'
                  ? (canClairvoyance && !playableNow)
                  : (!isMyTurn && !view.pending && (me.alive || c.type === 'feedthedead') && ANYTIME_TYPES.includes(c.type))
              )
              const isMarkedCard = me.marked?.id === c.id
              const dimOnTurn = canDraw && !playableNow && !isSelected && selected.length === 0
              const cardName = getCardName(catalog, c.type, c.variant)

  return (
                <div
                  key={c.id}
                  className="hand-slot"
                  style={{
                    transform: `rotate(${off * angle}deg) translateY(${off * off * curve}px)`,
                    marginLeft: i ? overlapPx : 0,
                    zIndex: i,
                  }}
                >
                  <div
                    role="button"
                    tabIndex={isDeadLocked ? -1 : 0}
                    aria-disabled={isDeadLocked || undefined}
                    aria-pressed={isSelected}
                    aria-label={`${cardName}${isMarkedCard ? ' (đang bị Mark)' : ''}${isSelected ? ' (đã chọn)' : ''}`}
                    className={`hand-card ${isSelected ? 'selected' : ''} ${dealIds.has(c.id) ? 'dealt' : ''} ${drag?.card.id === c.id ? 'dragging' : ''} ${dimOnTurn ? 'card-dim' : ''}`}
                    onPointerDown={(e) => startDrag(e, c)}
                    onMouseMove={tilt}
                    onMouseLeave={untilt}
                    onContextMenu={(e) => {
                      e.preventDefault()
                      e.currentTarget.blur()
                      setZoom(c)
                    }}
                    onClick={() => {
                      if (dragStartedRef.current) { dragStartedRef.current = false; return }
                      toggleSelect(c.id)
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        toggleSelect(c.id)
                      }
                    }}
                  >
                    <div>
                      <CardView card={c} marked={isMarkedCard} catalog={catalog} />
                    </div>

                    {playableNow && (
                      <button
                        type="button"
                        className="quick"
                        onPointerDown={(e) => e.stopPropagation()}
                        onClick={(e) => { e.stopPropagation(); playOne(c, false) }}
                      >
                        Đánh
                      </button>
                    )}

                    {anytimeOffTurn && (
                      <button
                        type="button"
                        className="quick now"
                        onPointerDown={(e) => e.stopPropagation()}
                        onClick={(e) => { e.stopPropagation(); playOne(c, true) }}
                      >
                        NOW
                      </button>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>
      )}

      {/* bản sao bài đang kéo theo con trỏ */}
      {drag && createPortal(
        <div className="drag-ghost" style={{ left: drag.x, top: drag.y }}>
          {drag.card?.type === 'hidden'
            ? <div className="card"><div className="card-back" /></div>
            : <CardView card={drag.card} catalog={catalog} />}
        </div>,
        document.body,
      )}

      {/* cutscene bom nổ */}
      <BoomOverlay boom={boom} />
      {/* cutscene lá bài huyền thoại */}
      <EpicCardOverlay epic={epicFx} />

      {/* Modal xem chi tiết & luật thẻ */}
      <ZoomModal card={zoom} catalog={catalog} onClose={() => setZoom(null)} />

      {/* Modal tùy chỉnh nhân vật mèo */}
      {!isSpectator && (
        <CatCustomizerModal
          open={catModalOpen}
          avatar={myAvatar}
          playerName={name}
          onClose={() => setCatModalOpen(false)}
          onSave={handleSaveAvatar}
        />
      )}

      {/* danh sách các thẻ đã đánh */}
      {graveList && createPortal(
        <div
          className="zoom-overlay grave-list-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Danh sách thẻ đã đánh"
          onClick={() => setGraveList(false)}
        >
          <div className="grave-list" onClick={(e) => e.stopPropagation()}>
            <div className="grave-list-head">
              <h3>Bỏ đi ({view.grave.length})</h3>
              <button
                type="button"
                className="icon-close"
                aria-label="Đóng"
                onClick={() => setGraveList(false)}
              >
                ✕
              </button>
            </div>
            <div className="grave-list-items">
              {(view.grave || []).map((c, i) => (
                <button
                  key={c.id || i}
                  type="button"
                  className="grave-item"
                  onClick={() => setZoom(c)}
                >
                  <CardView small card={c} catalog={catalog} />
                  <span>#{view.grave.length - i} · {getCardName(catalog, c.type, c.variant)}</span>
                </button>
              ))}
            </div>
          </div>
        </div>,
        document.body,
      )}

      {/* Godcat picker modal */}
      {godcatCard && (
        <CardPickerModal
          mode="godcat"
          excludeTurnEnding={godcatNow}
          catalog={catalog}
          disabled={!connected}
          iconName="crown"
          title={godcatNow ? 'Godcat hóa thân (NOW — ngoài lượt)' : 'Godcat hóa thân thành thẻ nào?'}
          subtitle="Chọn thẻ hành động bên dưới hoặc gõ để tìm nhanh (Enter chọn kết quả đầu)"
          onClose={() => { setGodcatCard(null); setGodcatNow(false) }}
          onSelect={(ctype) => {
            send({
              action: godcatNow ? 'play_now' : 'play',
              card_id: godcatCard.id,
              as_type: ctype,
            })
            setGodcatCard(null)
            setGodcatNow(false)
            setSelected([])
          }}
        />
      )}
    </div>
  )
}
